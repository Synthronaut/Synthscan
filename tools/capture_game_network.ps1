# Capture only the current Star Citizen server's UDP traffic for offline research.
# Run in an administrator PowerShell. No game input, process-memory access, or
# network probes are performed. Raw captures remain outside the project folder.
param([ValidateRange(10, 120)][int]$Seconds = 60, [switch]$Elevate)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if ($Elevate) {
        $launchArguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Seconds {1}' -f $PSCommandPath, $Seconds
        Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList $launchArguments
        return
    }
    throw 'Packet capture needs an administrator PowerShell. Nothing was changed.'
}
$gameProcesses = @(Get-Process -Name StarCitizen -ErrorAction SilentlyContinue)
if ($gameProcesses.Count -ne 1) { throw 'Expected exactly one running StarCitizen.exe.' }
$gameProcessId = $gameProcesses[0].Id
$gameLogPath = 'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log'
$join = Select-String -LiteralPath $gameLogPath -Pattern 'address\[([^]]+)\].*?port\[(\d+)\].*?shard\[([^]]+)\]' | Select-Object -Last 1
if (-not $join) { throw 'No server join endpoint in Game.log.' }
$serverAddress = $join.Matches[0].Groups[1].Value
$serverPort = [int]$join.Matches[0].Groups[2].Value
$null = [System.Net.IPAddress]::Parse($serverAddress)
$localPorts = @(Get-NetUDPEndpoint -OwningProcess $gameProcessId | Select-Object -ExpandProperty LocalPort -Unique)
if (-not $localPorts.Count) { throw 'The game has no UDP sockets.' }
$labRoot = Join-Path $env:LOCALAPPDATA 'SynthScan\network-research'
$captureDirectory = Join-Path $labRoot (Get-Date -Format 'yyyyMMdd-HHmmss')
$null = New-Item -ItemType Directory -Path $captureDirectory -Force
$transcriptPath = Join-Path $captureDirectory 'capture-status.txt'
Start-Transcript -LiteralPath $transcriptPath | Out-Null
$captureStarted = $false
$filterAdded = $false
try {
    # Never stop another capture or erase someone else's filters.
    $statusText = (& pktmon status 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw $statusText }
    if ($statusText -notmatch '(?i)not running|stopped|disabled' -or $statusText -match '(?im)^.*:\s*(running|enabled|on)\s*$') { throw "Existing or unrecognized PktMon state; refusing to change it: $statusText" }
    $filterText = (& pktmon filter list 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw $filterText }
    if ($filterText -match '(?m)^\s*\d+\s+\S') { throw 'Existing packet filters found; refusing to alter them.' }
    $etlPath = Join-Path $captureDirectory 'game-udp.etl'
    $pcapPath = Join-Path $captureDirectory 'game-udp.pcapng'
    & pktmon filter add SynthScanGameUDP -t UDP -i $serverAddress -p $serverPort
    if ($LASTEXITCODE -ne 0) { throw 'Could not add the game-only filter.' }
    $filterAdded = $true
    & pktmon start --capture --comp nics --pkt-size 0 --file-name $etlPath --file-size 64 --log-mode circular
    if ($LASTEXITCODE -ne 0) { throw 'Packet capture failed to start.' }
    $captureStarted = $true
    Write-Host "Capturing the game server UDP flow for $Seconds seconds. Keep playing normally."
    Start-Sleep -Seconds $Seconds
    & pktmon stop
    if ($LASTEXITCODE -ne 0) { throw 'PktMon stop failed; inspect capture-status.txt.' }
    $captureStarted = $false
    & pktmon etl2pcap $etlPath --out $pcapPath
    if ($LASTEXITCODE -ne 0) { throw 'Capture saved, but pcapng conversion failed.' }
    $result = [ordered]@{
        captured_at = (Get-Date).ToUniversalTime().ToString('o')
        game_pid = $gameProcessId
        server_address = $serverAddress
        server_port = $serverPort
        local_udp_ports = $localPorts
        seconds = $Seconds
        pcapng = $pcapPath
        etl = $etlPath
        transcript = $transcriptPath
    }
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $labRoot 'latest.json') -Encoding UTF8
    Write-Host "Capture ready: $pcapPath"
} finally {
    if ($captureStarted) { & pktmon stop | Out-Null }
    if ($filterAdded) { & pktmon filter remove | Out-Null }
    Stop-Transcript | Out-Null
}
