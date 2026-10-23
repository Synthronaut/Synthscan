# Launch packet RTT and PresentMon collectors elevated; the app stays unelevated.
$ErrorActionPreference = 'Stop'
$probeScript = Join-Path $PSScriptRoot 'live_network_probe.py'
$pythonPath = 'C:\Python314\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Expected Python runtime not found.' }
$launchArguments = '"{0}" --seconds 0' -f $probeScript
Start-Process -FilePath $pythonPath -ArgumentList $launchArguments -Verb RunAs -WindowStyle Hidden
