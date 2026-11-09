# Choose your SynthScan features

Download **SynthScan-Setup-Windows-x64.exe** from the official GitHub release.
There is one installer. Every feature starts checked. Uncheck anything you do not
want, then install. The installer already contains the packages; you do not need
to download them separately or supply a UEX token for normal public prices.

**Live Mining Recognition [SCREEN READING]** is the only screen-reading add-on.
It covers signatures, detailed rock composition/quality and supported refinery
imports. It needs Mining Tools, which the feature cards select automatically.
Unchecked recognition archives are not extracted by the installer. The resulting
app uses the screen-free engine with no capture providers, OCR models, ONNX
runtime or mining reader worker. Planning and manual records work without it.
Server HUD, hangars, reputation, blueprint ownership and piracy do not use OCR.
Fabricator blueprint OCR and DisplayInfo-derived piracy statistics are retired.

Automatic Acceptance is separately marked **AUTOMATED INPUT**, and remains off
until enabled. Account access and game-text changes have their own explanations.
Installing a feature is not consent to every optional action inside it.

## Change your choices

Open **Feature modules** in SynthScan's sidebar. Check or uncheck features and
choose **Download & apply selected features**. This retrieves Core and the
selected packages from the pinned signed release catalog. Close the game and
SynthScan desktop windows so the verified selection can activate. Do not download
or unzip module assets yourself. Saved ownership, tags, ledgers, board
counts and other player records remain in AppData when modules are removed.

Updates preserve the installed selection. New features are not silently added.
Core and selected features are version-compatible parts of one release. Catalog
signatures, hashes, limits and paths are checked before extraction and again by
the detached updater. A fresh app tree replaces the old selection; failed
readiness restores the previous app. Removing the reader also removes old Full
version trees and its cached package after the new app passes readiness. That
deliberate removal limits rollback to a screen-free version.

Removing SynthStrings restores its managed text changes while the game is closed.
Externally edited or unowned legacy text is preserved and reported for review.
Use **Setup → Remove SynthStrings** if cleanup cannot finish. Recovery journals
stay in AppData.

## What is shared

HUDs and navigation show only installed features. Mining HUD also requires Live
Mining Recognition; Mining Tools alone provides planning and manual records.
The server ribbon requires Server HUD, and its visit-history dropdown separately
requires Server History. No installed activity HUD means no activity toggle,
cycle shortcut or empty HUD window. Saved modes fall back to an installed mode.

Removing SynthStrings also stops patch watching and hides its old notifications.
Retained session records remain readable in Core without suggesting that an
uninstalled account feature is still collecting information.

Core retains native UI, common catalogs/calculations, profile storage, cleanup
and the updater. Optional Python providers and resources are separate packages.
Native interfaces use signed capability declarations and shared UI; they are
not independent DLLs. Their checkbox controls
availability, not complete code isolation. Download/resource savings are largest
for recognition; no saving is promised for every checkbox.

## Privacy and Windows

No usage tracking, telemetry consent screen or analytics beacon is added. The
publisher can view GitHub's asset download counts; these count downloads, not
unique users or active players. `tools/release_downloads.py` reads public counters
without contacting a player installation.

Update signing verifies our release packages. Windows publisher signing is
separate: this alpha has no trusted Authenticode certificate, so Windows may
still display a reputation warning. Branding does not remove that warning or
constitute an independent security audit. Download only from the official
repository; do not disable antivirus to install SynthScan.
