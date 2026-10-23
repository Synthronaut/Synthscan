param(
    [ValidateRange(10,300)][int]$Seconds = 60,
    [ValidatePattern('^[a-zA-Z0-9_-]{1,60}$')][string]$Label = 'baseline',
    [ValidateRange(0,60)][int]$DelaySeconds = 0,
    [switch]$Elevate
)
$ErrorActionPreference = 'Stop'
$taskAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $taskAdmin) {
    if (-not $Elevate) { throw 'PresentMon needs ETW access. Run this script with -Elevate to request the Windows administrator prompt. No game or system settings are changed.' }
    $taskArguments = @('-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Seconds',[string]$Seconds,'-Label',$Label,'-DelaySeconds',[string]$DelaySeconds)
    Start-Process -FilePath 'powershell.exe' -ArgumentList $taskArguments -Verb RunAs -WindowStyle Hidden
    return
}
$taskGame = @(Get-Process -Name StarCitizen -ErrorAction SilentlyContinue)
if ($taskGame.Count -ne 1) { throw 'Expected one running StarCitizen.exe. Launch the game and enter the test scene first.' }
$taskPresentMon = Join-Path $env:LOCALAPPDATA 'SynthScan\tools\PresentMon-2.6.0-x64.exe'
if (-not (Test-Path -LiteralPath $taskPresentMon)) { throw 'The existing standalone PresentMon executable was not found. Nothing was installed.' }
$taskOutputDirectory = Join-Path $PSScriptRoot '..\research\performance\runs'
[IO.Directory]::CreateDirectory($taskOutputDirectory) | Out-Null
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$taskOutput = [IO.Path]::GetFullPath((Join-Path $taskOutputDirectory ($taskStamp+'-'+$Label+'-frames.csv')))
$taskSessionName = 'SynthScanPerformance.'+$PID+'.'+$taskGame[0].Id
$taskMetadata = [ordered]@{label=$Label;game_pid=$taskGame[0].Id;seconds_requested=$Seconds;delay_seconds=$DelaySeconds;started_at=(Get-Date).ToUniversalTime().ToString('o');session=$taskSessionName;csv=$taskOutput;source='PresentMon application presents';frame_generation='unverified';runtime_settings='verify through game menu'}
$taskMetadata | ConvertTo-Json | Set-Content -LiteralPath ($taskOutput+'.meta.json') -Encoding utf8
& $taskPresentMon --process_id $taskGame[0].Id --session_name $taskSessionName --output_file $taskOutput --v1_metrics --qpc_time --no_console_stats --no_track_input --no_track_gpu --no_track_display --delay $DelaySeconds --timed $Seconds --terminate_after_timed --terminate_on_proc_exit 2> ($taskOutput+'.log')
if ($LASTEXITCODE -ne 0) { throw ('PresentMon failed with exit '+$LASTEXITCODE+'; inspect '+$taskOutput+'.log') }
if (-not (Test-Path -LiteralPath $taskOutput)) { throw 'PresentMon did not produce a CSV. No frame measurements are available.' }
