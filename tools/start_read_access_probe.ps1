$ErrorActionPreference = 'Stop'
$probeScript = Join-Path $PSScriptRoot 'probe_game_read_rights.py'
$launchArguments = '"{0}"' -f $probeScript
Start-Process -FilePath 'C:\Python314\pythonw.exe' -ArgumentList $launchArguments -Verb RunAs -WindowStyle Hidden
