<#
.SYNOPSIS
  Build and publish a SynthScan release to your Oracle server (website + auto-updater).
#>
param(
    [string]$Version = "",
    [string]$KeyPath = "C:\Users\Dev\Documents\ssh-key-2026-05-16.key",
    [string]$Server = "ubuntu@158.101.88.35",
    [string]$RemoteReleases = "/var/www/synthscan/releases/"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $Version) {
    $Version = (python -B tools\compute_update_version.py).Trim()
}
Write-Host "Publishing SynthScan version $Version ..."

# 0. Push tracked code changes to private GitHub repo if connected
if (Test-Path (Join-Path $PSScriptRoot ".git")) {
    git add -u
    $dirty = git status --porcelain
    if ($dirty) {
        git commit -m "Release $Version"
    }
    git push origin main
}

# 1. Build installer & signed update channel artifacts
python -B tools\build_modular_installer.py --version $Version
if ($LASTEXITCODE -ne 0) { throw "Installer build failed." }

# 2. Locate built release artifacts
$outDir = Join-Path $PSScriptRoot "release\$Version"
if (-not (Test-Path $outDir)) {
    $latest = Get-ChildItem (Join-Path $PSScriptRoot "release") -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { throw "No release output directory found." }
    $outDir = $latest.FullName
}

$artifacts = Get-ChildItem $outDir -File | Where-Object { $_.Extension -in ".exe", ".zip", ".json" }
if (-not $artifacts) { throw "No .exe/.zip/.json release artifacts found in $outDir" }

# 3. Upload to Oracle server and refresh manifest.json
foreach ($file in $artifacts) {
    Write-Host "Uploading $($file.Name)..."
    & scp -i $KeyPath -o StrictHostKeyChecking=no $file.FullName "${Server}:${RemoteReleases}"
    if ($LASTEXITCODE -ne 0) { throw "Upload failed for $($file.Name)" }
}

& ssh -i $KeyPath -o StrictHostKeyChecking=no $Server "sudo chmod -R a+rX /var/www/synthscan/releases && python3 /home/ubuntu/synthscan/scripts/sync_data.py"
if ($LASTEXITCODE -ne 0) { throw "Remote manifest refresh failed." }

Write-Host "Done! Live at https://synthscan.158-101-88-35.sslip.io/"
