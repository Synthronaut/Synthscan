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

$verInfo = (python -B tools\compute_update_version.py | ConvertFrom-Json)
if (-not $Version) {
    $Version = $verInfo.version
}
$Sequence = $verInfo.sequence
$env:SYNTHSCAN_VERSION = $Version
$env:SYNTHSCAN_SEQUENCE = "$Sequence"
Write-Host "Publishing SynthScan version $Version (sequence $Sequence) ..."

# 0. Push tracked code changes to private GitHub repo if connected
if (Test-Path (Join-Path $PSScriptRoot ".git")) {
    git add -u
    if (Test-Path (Join-Path $PSScriptRoot "data\custom_synthstrings.json")) {
        git add data\custom_synthstrings.json
    }
    $dirty = git status --porcelain | Where-Object { $_ -notmatch '^\?\?' }
    if ($dirty) {
        git commit -m "Release $Version"
    }
    git push origin main
}

# 1. Prepare clean output directory
$outDir = Join-Path $PSScriptRoot "release\$Version"
if (Test-Path $outDir) {
    Remove-Item -Recurse -Force $outDir
}
New-Item -ItemType Directory -Path $outDir | Out-Null

# 2. Build Standard and Full native engines + intermediate packages
foreach ($edition in @("standard", "full")) {
    Write-Host "Building $edition native engine & intermediate package..."
    $env:SYNTHSCAN_EDITION = $edition
    $nativeOut = Join-Path $outDir "native-$edition"
    $env:SYNTHSCAN_BUILD_OUT = $nativeOut
    python -B tools\build_native_app.py
    if ($LASTEXITCODE -ne 0) { throw "Native build failed for $edition." }

    $srcStage = Join-Path $outDir "source-$edition"
    $pkgStage = Join-Path $outDir "SynthScan-$edition-engine"
    python -B tools\package_community.py --edition $edition --source $srcStage --package $pkgStage --native $nativeOut
    if ($LASTEXITCODE -ne 0) { throw "Package community failed for $edition." }
}
Remove-Item Env:\SYNTHSCAN_EDITION -ErrorAction SilentlyContinue
Remove-Item Env:\SYNTHSCAN_BUILD_OUT -ErrorAction SilentlyContinue

# 3. Package signed feature modules
$urlBase = "https://synthscan.158-101-88-35.sslip.io/releases"
$modulesDir = Join-Path $outDir "modules"
Write-Host "Packaging signed feature modules..."
python -B tools\package_modules.py --standard (Join-Path $outDir "SynthScan-standard-engine") --full (Join-Path $outDir "SynthScan-full-engine") --output $modulesDir --url-base $urlBase
if ($LASTEXITCODE -ne 0) { throw "package_modules.py failed." }

# 4. Build branded modular installer
$installerDir = Join-Path $outDir "installer"
Write-Host "Building modular installer..."
python -B tools\build_modular_installer.py --payload $modulesDir --output $installerDir
if ($LASTEXITCODE -ne 0) { throw "build_modular_installer.py failed." }

# 5. Build migration update packages & sign update channel manifests
$migrationDir = Join-Path $outDir "migration"
$signedDir = Join-Path $outDir "signed"
New-Item -ItemType Directory -Path $signedDir | Out-Null
Write-Host "Building migration update packages..."
python -B tools\package_modular_updates.py --payload $modulesDir --output $migrationDir
if ($LASTEXITCODE -ne 0) { throw "package_modular_updates.py failed." }

foreach ($edition in @("standard", "full")) {
    $zipName = "SynthScan-$edition-Windows-x64.zip"
    $zipPath = Join-Path $migrationDir $zipName
    $outJson = Join-Path $signedDir "synthscan-update-$edition.json"
    python -B tools\sign_release.py --archive $zipPath --url "$urlBase/$zipName" --output $outJson
    if ($LASTEXITCODE -ne 0) { throw "sign_release.py failed for $edition." }
}
Copy-Item (Join-Path $signedDir "synthscan-update-full.json") (Join-Path $signedDir "synthscan-update.json")

# 6. Collect all public artifacts to upload (installer .exe LAST so mtime makes it latest_release in manifest.json)
$uploadFiles = @()
$uploadFiles += Get-ChildItem $modulesDir -Filter "SynthScan-module-*.zip"
$uploadFiles += Get-ChildItem $migrationDir -Filter "SynthScan-*-Windows-x64.zip"
$uploadFiles += Get-Item (Join-Path $modulesDir "synthscan-modules.json")
$uploadFiles += Get-Item (Join-Path $signedDir "synthscan-update-standard.json")
$uploadFiles += Get-Item (Join-Path $signedDir "synthscan-update.json")
$uploadFiles += Get-Item (Join-Path $installerDir "SynthScan-Setup-Windows-x64.exe")

# 7. Upload to Oracle server and refresh manifest.json
foreach ($file in $uploadFiles) {
    Write-Host "Uploading $($file.Name)..."
    & scp -i $KeyPath -o StrictHostKeyChecking=accept-new $file.FullName "${Server}:${RemoteReleases}"
    if ($LASTEXITCODE -ne 0) { throw "Upload failed for $($file.Name)" }
}

# Upload live data catalogs to /var/www/synthscan/data/
$dataDir = Join-Path $PSScriptRoot "data"
if (Test-Path (Join-Path $dataDir "custom_synthstrings.json")) {
    Write-Host "Uploading custom_synthstrings.json to data hub..."
    & scp -i $KeyPath -o StrictHostKeyChecking=accept-new (Join-Path $dataDir "custom_synthstrings.json") "${Server}:/var/www/synthscan/data/custom_synthstrings.json"
}
if (Test-Path (Join-Path $PSScriptRoot "blueprints_catalog.json")) {
    Write-Host "Uploading blueprints_catalog.json to data hub..."
    & scp -i $KeyPath -o StrictHostKeyChecking=accept-new (Join-Path $PSScriptRoot "blueprints_catalog.json") "${Server}:/var/www/synthscan/data/blueprints_catalog.json"
}
foreach ($extraCatalog in @("ship_catalog.json", "knick_knacks_catalog.json")) {
    if (Test-Path (Join-Path $dataDir $extraCatalog)) {
        Write-Host "Uploading $extraCatalog to data hub..."
        & scp -i $KeyPath -o StrictHostKeyChecking=accept-new (Join-Path $dataDir $extraCatalog) "${Server}:/var/www/synthscan/data/$extraCatalog"
    }
}

& ssh -i $KeyPath -o StrictHostKeyChecking=accept-new $Server "touch /var/www/synthscan/releases/SynthScan-Setup-Windows-x64.exe && sudo chmod -R a+rX /var/www/synthscan/releases && python3 /home/ubuntu/synthscan/scripts/sync_data.py"
if ($LASTEXITCODE -ne 0) { throw "Remote manifest refresh failed." }

Write-Host "Done! Live at https://synthscan.158-101-88-35.sslip.io/"
