# Deployment readiness — 9 November 2026

Amended for **0.1.0-alpha.11**. This supersedes the earlier assessment that
modular packaging had not been built. The GitHub release identifies its exact
commit and includes machine-readable validation reports. This is not an
independent security audit or a guarantee of compatibility with future patches.

## Implemented release

- One per-user Windows installer, all 14 optional features checked by default.
  Feature choices use two spacious, clickable card pages with a visible OCR
  capability badge and an all-without-screen-reading shortcut.
  No Python, build tools or separate downloads are required from users. Initial
  game-reference extraction can take several minutes.
- Live Mining Recognition is the only SCREEN READING component. Omitting it
  installs the screen-free native engine without capture providers/models.
  Server ribbon, reputation, blueprints, People, Missions and Hangars do not
  depend on OCR. Retired fabricator/DisplayInfo readers are not shipped.
- Feature modules can be changed in the app. Signed catalogs and SHA-256
  inventories authenticate packages and enforce matching versions, paths,
  sizes and dependencies. Updates preserve the choices. Services, desktop
  navigation and HUD tabs follow the installed selection.
- Shared native UI/calculations and common catalogs remain in Core. Small
  native-only features use capability declarations, not separate DLLs.
- Activation waits for the game and desktop work to finish, verifies readiness
  and rolls back on failure. The stable recovery Core stays screen-free.
  Removing recognition prunes older managed Full assemblies and its cache.
  Removing SynthStrings restores recorded managed changes; external edits
  block destructive cleanup and remain recoverable.
- First-run configuration, relocated startup shortcuts, independent People
  alerts and missing optional preference files were corrected during testing.
- No analytics, usage beacon, crash uploads or telemetry consent prompts.
  GitHub asset counters measure downloads, not active or unique users.

## Validation evidence

- Local Python suite: **962 tests, 12 skipped, passed**. Unavailable private/live
  fixtures are skipped; this is not a claim of live verification.
- Real per-user validation installer: server ribbon + Hangars, all features,
  then all without recognition. Installed modules, reader removal and retained
  fixture records verified. Uninstall passed and retained records. A separate
  registration identity protects the developer's installed app.
- Interactive validation builds default to a separate empty profile and
  shortcut names. A local receipt anchors that profile across version switches.
  Game-text writes/restoration and permission repair are blocked in test mode.
  Tests verify that an inherited personal-profile environment cannot redirect
  the test into the normal profile. Reference extraction may read game files;
  it does not replace the production user's game text.
- Packaged verifier checks Core only, ribbon + Hangars, People, SynthStrings,
  all without recognition and all features. It imports each selection with
  bundled Python, runs native self-tests and starts the real native host/bridge
  against synthetic game files with account access disabled.
- A separate, file-free Inno harness exercises the real card event handlers
  for all 14 features through six targets each (card surface, status button,
  title, description, badge and icon). It checks inclusion/exclusion, visible
  dimming, dependency rules, the reader-free preset, page persistence and a
  Core-only selection. This caught a selection API mistake that silent
  command-line installation tests did not cover: excluded components require
  explicit `!name` instructions. Both forms of validation are release gates.
- The **Unified modular release** workflow repeats builds, regression checks,
  signed package checks, the six selections and the actual production installer
  identity on a fresh Windows runner. Publishing requires all gates to pass.
  Release assets include both validation JSON reports.
- Allowlisted staging excludes profiles, credentials, logs, captured images,
  private extracted data and signing keys. Original licenses and corresponding
  modified GPL source remain available.

## Updates and game-folder hygiene

Native generation, blueprint ownership and reputation annotations share one
ownership journal. Two persistent game-text targets are used:
`Data/Localization/english/global.ini` and, if required, a language line in
`user.cfg`. Backups, extraction and records stay in AppData. Game archives and
executables are not patched. See [installation audit](installation-footprint.md).

Launcher/install-file events drive patch checks while not playing. The guard
fingerprints the build/archive, quarantines an exactly owned stale override,
waits for quiet files, extracts fresh text and rechecks identity around activation.
Foreign packs and later edits are preserved/reported. The watcher must be running
and cannot delay RSI's game launch. A patch race or already loaded text can
require another full game restart. New schemas and compiled mappings may need
an app update. See [patch protection](synthstrings-patch-protection.md).

## Distribution limits

The protected release-signing secret is configured for CI. Update metadata is
checked against the pinned release key. This is separate from Authenticode:
**there is no trusted Windows publisher certificate**. Windows reputation
warnings may remain; never disable antivirus to install SynthScan. Protected
game-text access can require a separate explicit permission-repair action.

This is a tested **community alpha**, ready for controlled deployment after its
release gates pass. It does not certify all live OCR layouts, every account's
service access or future patches. Configured estimates must remain distinct
from observed reputation/money changes. Use one immutable tester release before
broad distribution.
