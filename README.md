# SynthScan

A Windows companion for Star Citizen: mining assistance, blueprints, SynthStrings,
reputation labels, a server HUD, and Mining / Piracy / Missions activity tabs.

## Download and start

Download **SynthScan-Windows-x64.zip** from
[GitHub Releases](https://github.com/Synthronaut/Synthscan/releases).
Choose the release ZIP, rather than GitHub's automatic source-code archive.

1. Extract the **entire ZIP** into a folder you can write to, such as Documents/SynthScan.
   Keep the runtime and other folders beside SynthScan.exe.
2. Open **SynthScan.exe**. Python and the required libraries are included.
3. Setup finds your Star Citizen channel, or asks you to select the folder with
   Data.p4k. It reads your own game files to build item, artwork, blueprint,
   mining and reputation references. First setup can take several minutes and
   needs several GB of free space. References rebuild when the game build changes.
4. Sign in and enter the game normally. No password is entered into SynthScan.
5. Open **More → Startup & HUD settings** to enable launch with Star Citizen,
   choose the HUD hotkey, and configure visibility/scanning. The default hotkey
   is **Ctrl+Alt+H**. The server HUD's **HUD + / −** opens or closes the movable
   activity HUD; its tabs select Mining, Piracy and Missions.

Keep the extracted folder in place after enabling automatic launch. To move or
remove it, disable automatic launch first, then enable it from the new location.
Settings and player records live under `%LOCALAPPDATA%/SynthScan`, separately from
this download. An update does not replace that profile.

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

The private `native/reputation_labels_status.json` file under the local profile
records whether labels were written. If account verification is unavailable, the
app does not invent numbers. Setup and labels currently support English text.
Existing third-party language packs are preserved by SynthStrings setup; review
its setup message if marks cannot be installed. Reputation name edits preserve
other text and keep restoration backups locally.

## Included features and current limits

- Native mining recognition, rock composition/quality, equipment advice, refining,
  blueprint tracking, mission text marks, and searchable game references.
- Server/shard identity, region, session history, server hopping history, and a
  compact activity overlay. Drag and lock controls are available in HUD settings.
- The Piracy tab reads shard population, server population, server FPS and ping
  from the game's **visible DisplayInfo** panel using local OCR. Keep DisplayInfo
  enabled for those readings. Stale/unreadable values expire. These fields are
  not obtained through a hidden game API.
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
