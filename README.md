# SynthScan

[Download SynthScan for Windows](https://github.com/Synthronaut/Synthscan/releases/latest/download/SynthScan-Setup-Windows-x64.exe) · [Release notes](https://github.com/Synthronaut/Synthscan/releases)

One installer, with every feature selected by default. Uncheck anything you do
not want. **Live Mining Recognition [SCREEN READING]** is the only reader add-on;
leaving it unchecked installs the screen-free engine without capture/OCR
components. Change your selection later in **Feature modules**.
See [feature choices](docs/modules.md).

A Windows companion for Star Citizen: mining assistance, blueprints, SynthStrings,
reputation labels, a server HUD, and Mining / Piracy / Missions / Hangars / Finder activity tabs.

**People** in the desktop sidebar shows reported shard members and handle search,
with separate friend/party actions, multiple preset/custom player tags and
optional appearance alerts. **Buyer alerts** saves UEX material/quality watches
and checks for new matching buy ads every 30 minutes. Both use background data
reads without additional OCR. See [People and buyer-alerts guide](docs/people-and-buyer-alerts.md)
for first-use steps, coverage and validation limits.

The desktop and HUD use a navy/cyan theme and an original spacecraft/scanner
brand mark. The same multi-size icon is embedded in the application, tray,
bootstrap launcher and installer; desktop shortcuts use that artwork. The
editable SVG lives in `assets/branding/synthscan.svg`.

**More → Dock HUD top right** puts the pop-out flush with the game viewport's
top-right edge. Turn off **Lock HUD position** to drag it elsewhere; the saved
placement preserves the nearer screen edge across tab sizes and restarts.

Opening SynthScan starts at **Home**, with a fixed sidebar for the item
and ship finder, People, server history, blueprints, mining planning, personal
records, refinery orders and settings. Rock bookmarks are inside Mining Diary;
Day/Night Forecast plans destination lighting. Sidebar tabs switch the content inside the same desktop window; they do not open separate tool windows or resize the desktop. Larger pages scroll inside that area. The explicit HUD buttons still open the pop-out. **Full** on the pop-out opens Home; **Home** on the Mining window returns
there. The session recap separates this game run from the previous run, records
actual blueprint and contract notifications, and shows reputation changes since
the first verified balance read in that run. Missed history is not reconstructed
from configured rewards. **Live on/off** controls automatic mining screen reading;
the other background tools continue to work.

**Mission & Wallet Log** retains mission outcomes, reputation gains/losses and
observed aUEC balance changes. Filter activity, compare configured rewards with
recent participant counts, review session recaps, classify known wallet changes,
and export CSV, JSON or a readable HTML report. Unknown changes stay visible;
balance polling cannot recover every individual transaction. See
[mission and wallet history](docs/mission-wallet-log.md).

Finder expands with the desktop: wide windows put results beside purchase details;
narrower windows stack them. Inline item icons preserve the existing type/category
labels. Click a result-column header to sort ascending or descending. Different
shop prices use green for the lowest listed price and red for higher prices;
equal prices stay neutral. Ship-weapon detail cards show available stock direct-hit
alpha, nominal RPM, calculated full-rate burst DPS, projectile speed, and
separate distortion damage. Unsupported firing models show unavailable values.
These are game-file base values, not sustained damage or crafted-item bonuses.
Directory publication validates display names, unique row IDs, categories, and
linked recipe quantities; unresolved unnamed recipes remain diagnostic records
and are excluded from search. Updating an older extractor triggers a background
reference rebuild while the game is closed.

The **Refinery** page starts with a yield planner, not stored ore. Enter each raw
material's SCU to compare estimated total output and the material breakdown at
each station. Green/white/red indicate positive/neutral/negative station yield
bonuses. **Work orders** contains orders read from the game terminal; **Collected
stock** retains confirmed collection receipts with quantities and qualities.
These receipts record output collected, not a continuously reconciled cargo
inventory after subsequent sales or transfers. Estimated completion alone never
adds stock. With Live Mining Recognition installed and enabled, terminal OCR can
run while the game is being viewed. Without that add-on, records remain manual.

Automatic HUD display requires the game window; the launcher alone does not show
it. Explicit HUD buttons or the tray's Show HUD action can preview it without the
game. That preview lasts for this app run and ends when an observed game closes.

Confirmed refinery-completion notifications are retained in a small Mining HUD
line and on Home until dismissed. This records the game's notice; it does not
claim that the ore is still uncollected. Reading a terminal remains necessary
for full order details. Fullscreen is supported when Windows supplies a valid
game image; the app suggests a window-mode change only after capture fails.

The server HUD and server log show personal shard history: first recorded visit,
recorded visits and a **HISTORY** span. Open the region dropdown for the exact
first-recorded time. These observations do not establish server creation or
continuous uptime; see [server-history limits](SERVER_HISTORY.md).

**More → Item directory** searches items, recipes and blueprint mission rewards.
Item pages put UEX shop locations/prices and linked crafting blueprints before
flavor text. Blueprint entries skip purchase listings and show crafting and
acquisition information instead. Shop reports show their patch and age, cache offline and refresh
daily when viewed. Select **Blueprints for this item** for the exact item's
recipes and known unlock missions. Unknown sources remain labelled unknown.
The directory reloads after background game-reference refreshes without an app
restart. The fifth **Finder** HUD tab provides autocomplete and inline purchase
locations, prices and crafting materials. Unrecorded blueprints show known unlock
missions; confirmed owned blueprints keep their recipes visible.
Select **Player market** in Finder for public UEX sellers, buy requests and
clickable listing pages. The quality dropdown uses exact values extracted for
the selected material from the installed game, with **Any quality** available.
The [material quality reference](docs/material-quality-values.md) lists the
bundled build's 62 quantization tables. Those values are material-specific;
there is not a separate output value for every hundred quality points.
See [organization distribution and updates](DISTRIBUTION.md) for signed automatic
application updates and the release-channel publication steps.

The Type filter also includes **Ship**, **Vehicle** and **Component**. Ships show
in-game aUEC purchase prices and dealerships from UEX's vehicle-purchase feed.
Components include mining heads/modules, ship weapons, shields, coolers and
drives, using their exact game item IDs. The vehicle index and purchase-price
cache refresh every 12 hours; equipment prices refresh daily. Missing purchase
offers remain unknown rather than being inferred from another variant.

See the [installation footprint audit](docs/installation-footprint.md) for the two optional game-text targets, AppData recovery journal, safe removal, HUD-only setup and legacy-install limitations.

## Download and start

SynthStrings shortens juvenile creature tags to **Vlk Jr** and irradiated
juveniles to **Irr Vlk Jr**. Fully restart Star Citizen to load prepared labels.
Adult names, mission prose and item descriptions retain their existing text.

**More → Automatic acceptance** opens automatic acceptance settings.
Its background watcher starts with SynthScan, reads only new Game.log events,
and keeps automatic acceptance **off** until explicitly enabled. Your choice is
saved on this PC and retained across window closes and game sessions. It waits for
the matching queued notification's `Next` event. Shared contracts, party invitations
and friend requests have separate saved toggles; party and friend acceptance default off.
**Hide global chat after joining (F12)** is a separate saved toggle, off by default.
It waits for the game's final loading-screen completion, then presses F12 once
per join while Star Citizen is the foreground window. If you are tabbed out,
it waits until you return; disconnecting cancels that pending join. It applies
to loads completed after enabling, including reconnects and server changes,
and never retries F12 because another press would show chat again. Keep the
game's chat toggle bound to F12. Chat visibility itself is not read.
Ordinary notifications never qualify. Normal movement and mouse activity do not block acceptance; held modifiers
or the accept key do. An ignored key press stays pending: the helper retries
every 750 ms while the exact logged contract prompt is active, stopping on
acceptance confirmation, fade/removal/replacement or a 30-second maximum.
A fresh reshare can be tried again if an earlier attempt was unconfirmed.
Stale log events and ambiguous shares cancel eligibility. Menus that block
the game's accept key may still require closing; the helper retries when input
becomes available and does not close menus. The window shows queued shares, attempts,
and acceptance confirmations. Closing it hides the window; untick the checkbox
to disable. Stale session data pauses input without resetting your choice.
It uses the **Notifications → Accept Prompt** binding, rather than the legacy
Invite Accept binding. Letters, digits and common punctuation are supported;
unsupported/disabled bindings fail closed without changing your game settings.
Live queue/input timing is still unverified, especially in menus/chat. Keep
automation off until a parked test; a key sent does not prove game acceptance.

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

The small **AFK ○** button beside the activity HUD's top-left **−** control
toggles the mouse jiggler directly. **AFK ●** glows green when armed; click again
to turn it off. The last ten seconds before a pulse appear on the button;
**AFK ↔** means a pulse is being sent and **AFK ✓** briefly confirms it was sent
to Windows. **AFK !** indicates an input error. The same toggle is available
under **More → AFK mouse jiggler** and in the tray menu, whose tooltip shows
whether it is waiting or paused. It starts off every time SynthScan launches.
The first pulse waits ten idle seconds in a connected, foreground Star Citizen
session; subsequent pulses wait four idle minutes. Each pulse sends three
five-count mouse movements, pauses, and sends the inverse movements over at
least 280 ms, with no clicks or keys. Real activity,
held keys/buttons, other windows and unavailable session data pause it. Input
or a focus change during a pulse cancels the remaining movement immediately.
Turning
it off, closing SynthScan or exiting the game stops it. It does not require
administrator access; a failed input send disables it and shows **AFK !**.
The checkmark confirms Windows accepted the input; it does not confirm the
game reset its AFK timer. There is no verified minimum mouse distance for the
current game build. Avoiding an inactivity kick still needs a parked in-game
idle-session test; a subtle twitch alone does not establish success or failure.

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
HUD: raw terminal sale, modeled refined sale, and general player-market price
ranges from buy/sell references and recent listing history. No UEX account, token, or extra
setup is needed. This addition has not yet been published in the community installer.
Values assume 100% collection of the scanned SCU/composition, exclude inert, and
are estimates rather than confirmed cargo/sales. Raw and refined totals each
use one destination, preferring the current system. The selected refinery method
is used; the modeled refinery is named. Fees are subtracted only where the model
has complete cost data; otherwise the HUD explicitly says **before fees**.
Transport costs, terminal capacity and actual collection losses are excluded.
The refinery factors are the existing 4.10.0 reference model, pending fresh
in-game calibration. Market ranges combine matching same-patch buy/sell references
and up to 30 days of listing history. Each listing contributes its latest snapshot
once. Exact quality is preferred when there are at least two references; otherwise
the matching quality band is shown. Seven-day samples are preferred when sufficient;
older and removed advertisements carry less weight. With five or more references,
the range uses weighted central percentiles to reduce extreme-price distortion.
Sparse and historical-only estimates are labeled. These are general market estimates,
including asking prices, rather than guaranteed proceeds or verified final deals.
The quick value shows the main material's modeled refined SCU and market range per SCU.
Hand and ROC minerals use matching **per-piece** ranges with the quality or quality
band shown. Scanner SCU and composition percentages never become a piece count;
without a known count, the HUD shows a price per piece rather than a total.
Gem price scanning has a tracked name/quality path: it verifies the heading,
material name and a valid game quality without waiting for full composition.
Unknown mass and volume remain unknown. Rock-panel OCR runs independently of
signature OCR so a difficult cockpit panel does not block signature updates.
Partial market coverage is labeled **Market portion** and shows the percentage
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
- **Hangars HUD tab**: select Hangars beside Mining/Piracy/Missions, from the
  tray HUD-mode menu, or **Open Hangars HUD** in **Startup & HUD**. The compact
  card shows five lights, the opening/closing countdown and a small complete-set
  total. The earlier strip beneath the server bar has been replaced by this tab.
  Game-build changes and CIG's announced server resets invalidate older timing.
  The card shows **UNVERIFIED** and an estimated countdown until suitable revised
  community timing arrives. Data refreshes automatically; no app update is needed
  for timing changes. A successful download of unchanged old timing is not a new
  sync. Unannounced resets and individual hangar claims cannot be inferred.
- Compboard inventory: click **Boards** beside **More** and **Full** in the
  Hangars pop-out. Add or subtract each of boards 1–7, see the **full sets**
  total, or choose **+ full set**, **Use full set**, and **Undo last use**.
  **Timer** returns to the hangar countdown in the same HUD. The desktop sidebar's
  **Executive Hangar** tab combines a larger timer with the inventory, typed counts
  and **Save counts**. The old standalone inventory window and Settings/tray
  inventory shortcuts have been removed.
  Both views share the same saved inventory; conflicting edits refresh before retrying.
  **Use full set** subtracts one of each only when a full set is available;
  **Undo set** restores that use until counts are edited. Counts save on
  this PC; the Hangars HUD shows the number of complete sets. These are manual records;
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

## Data updates (development build)

Open **More → Setup & reputation status → Data updates** to see the installed
game, local-reference status, community-source checks, and hangar sync status.
**Check for updates** requests fresh checks; repeated clicks are rate-limited.
The window also works without the activity HUD. Source links open SCMDB or
SynthScan Releases for updates that need a reviewed application release.

Public release/source checks run in the background every six hours, retrying
failed checks after five minutes. Bedrock comparisons use a single upstream
commit and compare the mining, hardware, crafting, and refinery tables. A newer
upstream application revision is reported separately from changed data tables.
GitHub's public feeds require no account or API token. Download failures retain
the last known references and show freshness as unconfirmed.

Missing or outdated local catalogs rebuild automatically while SynthScan remains
open and Star Citizen is closed. Game-file extraction detects build changes
during a refresh. Catalogs are published as one complete generation, retaining
the previous generation; partial writes cannot mix recipe and mining versions.
Restart SynthScan after a completed rebuild to load the new library and planner.
Changed recipe quantities no longer prevent identity matching, and newly decoded
recipes are included with unknown unlock sources explicitly labelled. Unsupported
recipes and unmatched older community annotations remain visible as incomplete
reference coverage, rather than a claim that every recipe was verified.

SCMDB's public JSON data is imported for the exact installed patch, build and
LIVE/PTU channel. Blueprint mission sources and numeric mining hardware stats
refresh automatically with source dates and schema validation. Failed or mismatched
imports retain previous references. New hardware identities and calculation changes
arrive through signed application releases. Complete app packages stage in the
background and activate while the game is closed and SynthScan is idle; readiness
failure restores the previous version. Player profiles remain outside the app.

Executive Hangar timing checks continue across HUD modes: normally every ten
minutes, or every two minutes while timing needs verification. CIG's official
reset feed is checked independently at least every five minutes while the app
is running, so a timing-site outage cannot suppress reset discovery. Unavailable
reset checks, patch/channel mismatches, and announced resets keep the countdown
**UNVERIFIED**. Re-downloading unchanged timing does not validate a new build.
This remains a community schedule estimate; unannounced resets and individual
hangar availability cannot be established from these sources.

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


### Daylight planner

Open **More → Daylight planner** on the activity HUD, or use the SynthScan tray menu.
Choose a system, planet/moon and searchable destination, then forecast now, in a
number of real minutes, or at a local date/time (`YYYY-MM-DD HH:MM`). It shows light
on arrival, next sunrise/sunset, and upcoming daylight windows. All displayed
clock times use the PC's local timezone. It does not require visiting the location
or reading the clipboard.

The initial catalogue covers Stanton and Pyro. Public body/POI data refreshes in
the background without an application update; the bundled copy works offline.
Forecasts remain labelled community estimates until calibrated locally. A saved
sunrise/sunset observation expires after seven days or a client build/catalogue
change. A successful download alone does not verify the body's clock. Terrain,
buildings, weather, eclipses and unsurveyed locations can affect visible light.
The Siege of Orison entry uses an explicitly labelled Orison city reference;
precise platform positions and current instance alignment still need validation.
Personal destination preferences and observations stay on this PC.


### Ship profiles and crafted heads (development build)

**More → Ship profiles** and the tray's **Ship profiles** menu switch directly
between your named setups, including multiple ships of the same model. The
current profile is checked. **Add / manage ship profiles** opens the existing
ship picker; add a ship at the bottom and rename it in its loadout card. Each
profile retains its own lasers, modules and crafting bonuses. Each MOLE turret
has a separate configuration. Picking a profile resets the firing selection to
all of that profile's heads; select the crewed heads for the current rock.

**Heads / craft** in the main window, or **Ship profiles → Heads, modules &
crafting**, opens the loadout editor. Enter the item's final bonus under
**CRAFTED LASER POWER**: for a Helix I showing +25%, enter `25`, not `125`.
Use the **final combined Laser Power bonus** displayed by the finished item;
the game has already combined the two power-affecting crafting materials.
Click the field to replace its old value, or paste a value such as `+17.6%`.
Valid edits update the power preview and advice immediately; Enter or leaving
the field saves them, and Escape cancels the edit. **Stock** restores zero.
Incomplete or unsupported entries are marked as not applied. The HUD's ship
summary shows each head's active power bonus, or its stock-power assumption.
Remembered bonuses for swapped-out MOLE lasers are kept separately for each
turret, including when two turrets use the same laser model.
This multiplies the reference head's power by 1.25; configured module effects,
range and rock resistance are applied separately. It is not a promise that
every rock 25% heavier will break. The Golem now accepts interchangeable S1
heads in the configuration, including Helix I, while retaining Pitman as the
default for a new profile. MOLE head tabs show their individual stock/crafted
status. These are player-entered item bonuses, not automatically verified item
stats. Integrity is outside the HUD's mining-power model; it does not need an
input here.

### Mining values and head ranges

Mining values use the scanned **COMP. volume in SCU**, each material's percentage
and its quality. Material SCU is total SCU × percentage / 100; the mass figure
alone cannot provide that volume. Raw/refined estimates assume collection of the
scanned material and use public UEX prices; the HUD labels fee and quote limits.
The reader now distinguishes an unread volume from unconfirmed material rows.

The compact mining HUD also shows each configured head's full-power distance.
These are laser-to-rock ranges from the selected loadout. Pilot-seat parking
guidance needs the deployed turret/muzzle geometry and marker-distance reference
to be validated; the app does not present a guessed cockpit offset as exact.

## Choose your features

The single installer starts with every feature checked. Uncheck **Live Mining
Recognition [SCREEN READING]** to leave out the capture engine and recognition
models. Other tools remain independently selectable. Automatic updates preserve
your choice; change it later in **Feature modules**. See [module details](docs/modules.md).
