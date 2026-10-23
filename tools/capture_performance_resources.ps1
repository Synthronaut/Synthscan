param(
    [ValidateRange(5,300)][int]$Seconds = 20,
    [string]$OutputPath,
    [string]$Label = 'idle'
)
$ErrorActionPreference = 'Stop'
if (-not $OutputPath) {
    $taskDirectory = Join-Path $PSScriptRoot '..\research\performance'
    $OutputPath = Join-Path $taskDirectory ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-resources.json')
}
$taskResolvedOutput = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($taskResolvedOutput)) | Out-Null
$taskStart = (Get-Date).ToUniversalTime().ToString('o')
$taskProcessesBefore = @(Get-Process | Select-Object ProcessName,Id,CPU,
    @{n='WorkingSetBytes';e={$_.WorkingSet64}},@{n='PrivateBytes';e={$_.PrivateMemorySize64}})
$taskGpuBefore = @(& nvidia-smi --query-gpu=name,driver_version,utilization.gpu,utilization.decoder,utilization.encoder,memory.used,memory.total,temperature.gpu,power.draw,clocks.current.graphics,clocks.current.memory --format=csv,noheader,nounits 2>$null)
$taskCounterErrors = @()
$taskCounters = Get-Counter -Counter @(
    '\Processor(_Total)\% Processor Time', '\Memory\Available MBytes',
    '\Memory\% Committed Bytes In Use', '\Memory\Pages Input/sec',
    '\PhysicalDisk(_Total)\% Disk Time', '\GPU Engine(*)\Utilization Percentage'
) -SampleInterval 1 -MaxSamples $Seconds -ErrorAction SilentlyContinue -ErrorVariable taskCounterErrors
$taskSummaries = @($taskCounters.CounterSamples | Group-Object Path | ForEach-Object {
    $taskMean = ($_.Group.CookedValue | Measure-Object -Average).Average
    $taskMaximum = ($_.Group.CookedValue | Measure-Object -Maximum).Maximum
    if ($_.Name -notmatch 'gpu engine' -or $taskMaximum -gt 0.1) {
        [ordered]@{counter=$_.Name; mean=[math]::Round($taskMean,3); max=[math]::Round($taskMaximum,3)}
    }
})
$taskSamples = @($taskCounters | ForEach-Object {
    $taskValues = [ordered]@{}
    foreach ($taskCounter in $_.CounterSamples) {
        if ($taskCounter.Path -notmatch 'gpu engine' -or $taskCounter.CookedValue -gt 0.1) {
            $taskValues[$taskCounter.Path] = [math]::Round($taskCounter.CookedValue,3)
        }
    }
    [ordered]@{at=$_.Timestamp.ToUniversalTime().ToString('o');values=$taskValues}
})
$taskMachine = Get-CimInstance Win32_ComputerSystem
$taskReport = [ordered]@{
    schema=1;label=$Label;started_at=$taskStart;finished_at=(Get-Date).ToUniversalTime().ToString('o')
    sample_interval_seconds=1;summaries=$taskSummaries;samples=$taskSamples
    counter_errors=@($taskCounterErrors | ForEach-Object {$_.ToString()})
    cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
    physical_ram_bytes=$taskMachine.TotalPhysicalMemory
    memory_modules=@(Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,ConfiguredClockSpeed,PartNumber)
    motherboard=Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product
    os=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,LastBootUpTime
    disks=@(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size,HealthStatus)
    volumes=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace)
    processes_before=$taskProcessesBefore
    processes_after=@(Get-Process | Select-Object ProcessName,Id,CPU,
        @{n='WorkingSetBytes';e={$_.WorkingSet64}},@{n='PrivateBytes';e={$_.PrivateMemorySize64}})
    gpu_snapshot_columns='name,driver_version,gpu_pct,decoder_pct,encoder_pct,vram_used_mib,vram_total_mib,temp_c,power_w,graphics_mhz,memory_mhz'
    gpu_before=$taskGpuBefore
    gpu_after=@(& nvidia-smi --query-gpu=name,driver_version,utilization.gpu,utilization.decoder,utilization.encoder,memory.used,memory.total,temperature.gpu,power.draw,clocks.current.graphics,clocks.current.memory --format=csv,noheader,nounits 2>$null)
    limits='Read-only OS samples include collector overhead. GPU power/clocks are endpoint snapshots. Page reads include mapped files, not just the pagefile. Utilization does not prove a bottleneck by itself.'
}
$taskReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskResolvedOutput -Encoding utf8
[ordered]@{output=$taskResolvedOutput;summaries=$taskSummaries;counter_errors=$taskReport.counter_errors} | ConvertTo-Json -Depth 5
