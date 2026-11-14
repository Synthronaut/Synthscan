# SynthScan Updating & Release Protocol

This document is the operational runbook for keeping SynthScan's game data, localization strings, website, and client builds in sync across Star Citizen patches and local code iterations.

---

## 1. Architecture Overview

| Component | Location | Purpose |
| :--- | :--- | :--- |
| **Public Website & Update Hub** | `https://synthscan.158-101-88-35.sslip.io/` | Serves installer downloads (`/releases/`), SHA-256 data manifest (`/data/manifest.json`), and landing page (`index.html`). |
| **Oracle Server Paths** | `/var/www/synthscan/` (web root)<br>`/home/ubuntu/synthscan/` (scripts, logs, upstream) | Isolated from all other projects on `158.101.88.35`. Nginx config: `/etc/nginx/sites-available/synthscan-app`. |
| **Server Auto-Sync Timer** | `synthscan-sync.timer` (every 6h) | Runs `/home/ubuntu/synthscan/scripts/sync_data.py` to check `SC-Ravaxx/Bedrock`, merge `isReward: true` blueprints, and republish `/var/www/synthscan/data/manifest.json`. |
| **Client Data Updater** | `data_updates.py` (`sync_oracle_hub()`) | Automatically downloads changed catalogs from `/data/manifest.json`, verifies SHA-256 hashes, and runs `synthstrings_sync.py`. |
| **Client App Updater** | `app_updates.py` + `update_trust.json` | Automatically downloads and stages signed app updates from `https://synthscan.158-101-88-35.sslip.io/releases/`. |

### Server Access & Isolation Rules
- **Host**: `ubuntu@158.101.88.35`
- **SSH Key**: `C:\Users\Dev\Documents\ssh-key-2026-05-16.key`
- **Strict Isolation**: Never touch, restart, or modify any files, Docker containers, or Nginx configs belonging to **BTD**, **AXEN**, or **Embers** on the same VM.

---

## 2. Publishing a Code / UI Iteration (Desktop -> Website -> All Users)

Because the GitHub repository is private, all public downloads and auto-updates flow through the Oracle server:

1. Verify `update_trust.json` points to `https://synthscan.158-101-88-35.sslip.io/releases/` (never GitHub).
2. Run the one-command publisher from the repo root:
   ```powershell
   .\publish_release.ps1
   ```
   This script:
   - Computes the version (`tools/compute_update_version.py`) or uses `-Version <ver>`.
   - Builds the modular installer and signed update channel artifacts (`tools/build_modular_installer.py`).
   - Uploads `.exe`, `.zip`, and `.json` files to `/var/www/synthscan/releases/`.
   - Runs `python3 /home/ubuntu/synthscan/scripts/sync_data.py` to update `manifest.json` and the website's Download button.
3. Verify `https://synthscan.158-101-88-35.sslip.io/data/manifest.json` lists the new `latest_release` and returns HTTP 200.

---

## 3. Updating Data & Strings After a Star Citizen Patch

### Local Game Reference Rebuild (StarBreaker CLI)
When Star Citizen updates locally, run:
```powershell
python -B tools/refresh_game_reference.py
```
This rebuilds `data/local_game_catalog.json`, `data/local_game_library.json`, and `data/local_mining_catalog.json` from `Data.p4k`. (At runtime, `reference_update.py` also triggers this automatically when the game is closed.)

### Blueprint Catalog Rules (`blueprints_catalog.json`)
- **Only** include obtainable reward blueprints (`isReward: true`).
- **Never** bulk-import `isReward: false` records from `blueprints_source.json` (which contains 900+ unobtainable/dev/legacy variants).
- Deduplicate using `blueprint_strings.item_key()`.

### `global.ini` / SynthStrings Rules
- Run `python -B synthstrings_sync.py` to sync `[OWNED]` / `[  ]` markers and `[ALL BP OWNED]` / `[BP: X LEFT]` title tags.
- **Title Bloat Guard**: Mission `_title` / `_name` keys must **never** contain `\n\n<EM4>Potential Blueprints</EM4>` or `<EM4>Multiple Blueprint Pools</EM4>` lists — those belong strictly in `_desc` keys. `synthstrings_sync.py` enforces this automatically.

### Pushing Updated Catalogs to All Users
To push updated catalogs (`blueprints_catalog.json`, `crafting_recipes.json`, `data/mining_hardware.json`, `data/material_qualities.json`, `data/wikelo_data.json`, `data/executive_hangar_schedule.json`, `data/daylight_catalogue.json`) to every installed user:
1. Upload the validated JSON files to `/var/www/synthscan/data/` on `158.101.88.35`.
2. Update `game_version` and `recent_changes` in `/home/ubuntu/synthscan/scripts/sync_data.py` if the patch number changed.
3. Run on the server:
   ```bash
   python3 /home/ubuntu/synthscan/scripts/sync_data.py
   ```
4. Every SynthScan client will pick up the changes automatically on its next `sync_oracle_hub()` check.
