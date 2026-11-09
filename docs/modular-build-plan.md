# SynthScan module structure

Agreed direction, 2026-11-09. One app, independently selected feature packs, and a separate live-mining recognition add-on. The unified alpha installer and signed package manager implement this selection structure. See [installation and module behavior](modules.md). Standard/Full remain internal engine variants and legacy update channels, not separate choices for new users.

| Module | Scope | Screen reading |
| --- | --- | --- |
| Core | App shell, local records, shared game-data catalogs, module management and verified updates | No |
| SynthStrings & Reputation | Text improvements, verified corporation reputation labels and blueprint ownership labels from the shared ownership ledger | No; discloses account access and game-text changes |
| Mining Tools | Planner, diary, rock bookmarks, manual refinery records, material/price calculations | No |
| Live Mining Recognition | Rock signatures, detailed rock composition, SCU/quality/value readings and supported refinery screen imports; requires Mining Tools | Yes, explicitly installed add-on |
| Crafting & Blueprints | Library, manual/log ownership, recipes, quality effects and acquisition information | No |
| Item & Ship Finder | Search, specifications, locations and market information | No |
| Server HUD | Log-based region, shard/session identity and supported non-OCR readings | No |
| Server History | Session timestamps, visits, notes and hop history | No |
| People | Player list, tags, relationships and supported alerts | No |
| Piracy | Log-derived reports, manual wait timer and future piracy features | No |
| Missions | Observed contracts, supported payouts/participants/reputation and planning | No |
| Hangars | Community schedule estimates and compboard inventory | No |
| Day/Night Forecast | Destination selection and daylight predictions | No |
| Automatic Acceptance | Notification acceptance helper | No; discloses automated input |
| Personal Notes | Local notes | No |

Account access, internet access, game-text modification and automated input are separate capability notices. The screen-reading notice belongs to Live Mining Recognition. Refinery OCR is part of that add-on, not a hidden dependency of the manual Mining Tools pack. Unknown source values remain unknown; removing OCR does not create another population/FPS source.

## HUD behavior

- Populate tabs and mode menus from installed capabilities. Lay remaining tabs out across the available width, without gaps or disabled placeholder buttons.
- The Mining recognition tab requires both Mining Tools and Live Mining Recognition. General planning/manual records remain desktop features without recognition.
- Keyboard tab cycling skips absent modules. Restore a saved selection only if still installed; otherwise use the first available HUD mode.
- Hide the server ribbon's HUD expansion control when no activity-HUD module is installed.
- Preserve the existing movable/collapsible HUD behavior; module changes must not introduce game-control automation.
- The current foundation reads an optional `modules` array in the installed `release.json`. Existing packages without it retain their supported tabs, with recognition unavailable in the screen-free native build. This array is an availability contract, not a download/installation system or a security sandbox. Package activation should restart the app to reload capabilities.
- HUD mode IDs: `mining_recognition`, `piracy`, `missions`, `hangars`, `item_finder`. Mining recognition additionally requires `mining_tools`. An explicit empty list means no activity HUD.

The module manager filters desktop/HUD navigation, gates optional service startup, resolves dependencies, authenticates catalogs/packages and assembles fresh version directories with activation rollback. Shared native UI and calculations stay in Core. Small native-only packs are capability declarations rather than separate DLLs; complete code isolation or a memory saving for every checkbox is not claimed. Capture/OCR providers and dependencies are physically excluded when recognition is unchecked.

## Fabricator blueprint OCR status and retirement

The previous reader detected high-confidence exact item names in a fabricator/blueprint context. It did not interpret lock/owned icons. It queued candidates for manual review; a visible item name never proved ownership. Source inspection establishes that limitation, not an accuracy percentage from live testing.

The native scan button and capture/decoding path have been retired. Old bridge scan commands return an explanatory response without opening an image or frame mapping. Legacy Python capture entry points are also retired. Existing scan candidates and ownership records are preserved for review; no record is cleared by retirement. Pure historical parsing tests remain available, but the parser is not an active acquisition feature.

Use ownership checkboxes and supported game-log imports. Blueprint ownership in the shared ledger can still drive SynthStrings labels independently of screen reading.

## Piracy OCR retirement

The runtime piracy service no longer launches the DisplayInfo capture worker or imports its reader. The HUD no longer renders the screen-derived population, server FPS, ping, population-change deltas or history graph. It retains the manual wait timer, log-derived interdiction/crime reports and jurisdiction information. Logged reports are not reliable detection of every catch, particularly in lawless conditions.

The regular server ribbon and historical session records use their existing non-OCR sources and are not removed. The old population validation utility remains historical code; no runtime piracy capture service uses it.
