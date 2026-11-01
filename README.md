# SynthScan

A Windows companion for Star Citizen: mining assistance, blueprints, SynthStrings,
reputation labels, a server HUD, and Mining / Piracy / Missions activity tabs.

## Download and start

Download **SynthScan-Setup-Windows-x64.exe** from
[GitHub Releases](https://github.com/Synthronaut/Synthscan/releases).

1. Open the installer and choose **Install**. Python and app dependencies are included.
2. Leave **Open SynthScan** selected. Setup detects your game and builds your local
   references automatically. The progress screen explains what is happening.
3. Enter Star Citizen normally. When your account has been verified, SynthScan
   shows **Your reputation is ready — restart Star Citizen**. Fully restart the
   game when convenient. SynthScan never closes the game for you.

Start Menu and desktop shortcuts are created. **Launch with Star Citizen** is
selected by default; untick it in the installer or change it later under
**More → Startup & HUD settings**. SynthScan reserves no global hotkeys. Use the HUD buttons and tray menu.

**More → Setup & reputation status** shows login, sync and restart status. It
offers Retry, Repair setup, Choose game folder, and a Windows permission repair
if game text is read-only. Normal setup requires no console commands, Python
installation, configuration editing or JSON-file inspection. First setup can
take several minutes and needs several GB of free disk space.

Run a newer installer over the existing installation to upgrade. Your player
records stay under `%LOCALAPPDATA%/SynthScan`; upgrades and uninstall keep them.
Uninstall removes this installation's startup entry and restores reputation name
edits when it can do so without overwriting someone else's changes.

The ZIP remains available for advanced portable deployment. The installer is
unsigned, so Windows may show its normal security prompt. Regular installation
uses your Windows account without administrator access. A separate permission
prompt appears only if you choose to repair access to game text files.

## Reputation beside corporation names

SynthScan reads **your verified signed-in character's reputation balances** from
the game's authenticated service and combines them with locally extracted rank
thresholds. It adds text such as `Corporation (249 / 800)` to that organization's
specific English name. Shared labels such as "Neutral" are not globally edited.
Only returned, verified balances are annotated; absent balances are not assumed 0.

The numerator is the **absolute reputation balance** and the denominator is the
**next configured standing threshold**. These are not points earned since the
start of the current rank. Gated ranks can require additional prerequisites.

**Star Citizen loads localization at process startup.** After SynthScan first
verifies your character and writes labels, fully exit and relaunch Star Citizen.
Returning to the menu or logging out is insufficient. Numbers visible in the game
remain a snapshot until the next full restart; the external Missions HUD can
refresh balances while playing. Reputation polling works in every HUD mode.

The in-app **Setup & reputation status** screen shows whether labels were written.
If account verification is unavailable, the
app does not invent numbers. Setup and labels currently support English text.
Existing third-party language packs are preserved by SynthStrings setup; review
its setup message if marks cannot be installed. Reputation name edits preserve
other text and keep restoration backups locally.

## Included features and current limits

The local development build includes scanned-rock value estimates in the mining
HUD: raw terminal sale, modeled refined sale, and quality-band player buy-ad
averages where suitable current quotes exist. No UEX account, token, or extra
setup is needed. This addition has not yet been published in the community installer.
Values assume 100% collection of the scanned SCU/composition, exclude inert, and
are estimates rather than confirmed cargo/sales. Raw and refined totals each
use one destination, preferring the current system. The selected refinery method
is used; the modeled refinery is named. Fees are subtracted only where the model
has complete cost data; otherwise the HUD explicitly says **before fees**.
Transport costs, terminal capacity and actual collection losses are excluded.
The refinery factors are the existing 4.10.0 reference model, pending fresh
in-game calibration. Player estimates use same-patch active buy averages with
at least three contributing listings in SCU/cSCU and a matching quality band.
Partial market coverage is labeled **Player portion** and shows the percentage
of refined ore priced. Missing, stale or incompatible quotes do not become zero.
The expanded mining **Rows** view lists each material/quality separately, with
raw SCU and model-estimated refined SCU, plus a separate inert amount. Material
abbreviations in the installed SynthStrings file are resolved to full names.
The detailed rock reader works from the mining scan panel; it does not require
a radiation-signature hit before showing composition.
When overlapping cockpit text leaves a small unread share, the HUD can show a
**Partial OCR** estimate with the percentage read. Prices use only identified
material amounts; the unread remainder is excluded. Unknown materials or a
larger discrepancy keep valuation pending. Partial scans continue to be retried.

- Native mining recognition, rock composition/quality, equipment advice, refining,
  blueprint tracking, mission text marks, and searchable game references.
- Server/shard identity, region, session history, server hopping history, and a
  compact activity overlay. During gameplay, the HUD body passes mouse input
  through. Only the small ribbon **HUD +/−** and docked **−** collapse controls
  accept clicks, without taking focus. To use menus or reposition the HUD,
  switch out of the game and open SynthScan from the Windows tray. Returning to
  the game restores input protection automatically. No hotkey is required.
- The Piracy tab reads shard population, server population, server FPS and ping
  from the game's **visible DisplayInfo** panel using local OCR. Keep DisplayInfo
  enabled for those readings. Stale/unreadable values expire. These fields are
  not obtained through a hidden game API.
- Optional Executive Hangar strip: enable **Executive Hangar timer** in the
  tray menu or **More → Startup & HUD settings**. Five lights and countdowns
  follow the shared PYAM schedule alongside Mining/Piracy. Charging, usable
  green-light time, and the all-off reset are separate phases. The strip is
  read-only and click-through; it does not know which local hangar is available
  or whether another crew has already claimed it. Source sync and patch are shown.
- Compboard inventory: open **Compboard inventory** from the tray menu or
  **Startup & HUD**. Set quantities for boards 1–7 with +/− or typed counts.
  **Use one set** subtracts one of each only when a full set is available;
  **Undo last set** restores that use until counts are edited. Counts save on
  this PC and appear on the click-through hangar strip. These are manual records;
  the button does not operate the in-game hangar or claim a ship.
- Missions observations and configured rewards. Party splits are estimates, not
  guaranteed awards. Only authenticated balances count as verified reputation.
- Mining diary, personal records and deliberate share exports. Refinery/inventory
  recognition can require review; observations are not a guaranteed sale or haul.
- Lawless interdiction detection and coordinate return guidance remain
  experimental. Crime notifications cannot prove every successful snare catch;
  missing catch reports do not prove nobody was caught. Planet navigation needs
  calibrated reference data and is not a dependable rock recovery system yet.

This is a community **alpha**, initially validated against game build 12913470.
Game patches, account-service changes and localization permissions can affect
features. No game process memory reading, input automation, or anti-cheat bypass
is used by the normal app.

## Privacy, source and licensing

There is no shared SynthScan player database or automatic upload. Each PC builds
its own references and keeps its own profile. See [PRIVACY.md](PRIVACY.md) for the
account-service connection, local file permissions, optional integrations and
shared game-installation limitations. Do not post raw profiles or game logs.

SynthScan's native application is a modified GPL-3.0-or-later fork of
[SC-Ravaxx/Bedrock](https://github.com/SC-Ravaxx/Bedrock), commit
`8fd809d84ff614d466447dd8b370cee86a7822ce`. Its original copyright, component
licenses and corresponding source are retained. StarBreaker provides local game
file extraction under its MIT license. Game content belongs to Cloud Imperium
Games; this app is an independent community project.

See [LICENSE](LICENSE), [LICENSES.md](LICENSES.md), [BUILDING.md](BUILDING.md), and
[SECURITY.md](SECURITY.md). The older Python desktop interface remains as source
for development; **SynthScan.exe is the supported community entry point**.
