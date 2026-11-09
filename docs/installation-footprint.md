# Installation footprint audit

**Amended 2026-11-09 for the unified modular alpha.** Scope: guided Windows setup, native SynthStrings generation, blueprint/reputation updates, permission repair, module removal and uninstall. This is a source review with local regression and real installer tests, not an independent security certification. Previously downloaded installers do not acquire these fixes merely because this report changed.

## Normal game-folder footprint

| Path relative to LIVE/PTU | Behavior |
| --- | --- |
| `Data/Localization/english/global.ini` | Optional loose localization override: blueprint ownership, reputation labels and shortened names. Native generation preserves existing foreign packs; annotation uses the same ownership journal. |
| `user.cfg` | Adds `g_language = english` only if no language is configured. Keeps unrelated settings; refuses to silently switch another configured language. Windows may display this as `USER.cfg`. |
| `.synthscan-*.tmp` beside the target | Temporary atomic replacement file. Normal completion/failure removes it. Interrupted update recovery recognizes the recorded filename and file identity; unknown temporary files are preserved. |

**Two persistent text targets; no persistent backups inside LIVE.** Normal setup does not patch archives, executables, anti-cheat binaries, personal control maps or launcher files. It does not install a packet-capture driver, service, console pulse config, extracted artwork or catalogs into LIVE.

The game-text option is visible before first setup. Uncheck it for HUD/library use without new game-text writes. An existing legacy override is preserved and reported for review; HUD-only setup does not silently delete an older pack.

## Outside the game

- `%LOCALAPPDATA%/Programs/SynthScan`: per-user app/runtime, a screen-free recovery Core and selected versioned feature assemblies. Legacy edition-specific installations may use a corresponding suffix.
- `%LOCALAPPDATA%/SynthScan/native`: this Windows account's settings, ownership, reputation snapshots, diary, notes, refinery records, caches and status files. An explicitly configured development/portable profile can change this root.
- `native/game_text/<channel-path-hash>/journal.json`: original existence/hashes, owned versions, created directories, cleanup outcomes and recorded discretionary permissions.
- The same directory holds original and recovery copies. Repeated updates retain only the latest referenced full written copy, avoiding a new full localization backup on every reputation change. Original recovery copies and explicit legacy archives remain available.
- `%LOCALAPPDATA%/SynthScan/reference/<build-id>` and `reference/active`: locally extracted records/artwork, outside LIVE. Reference generations can use substantial disk space.
- Ordinary per-user shortcuts, optional Startup watcher shortcut and Windows uninstall registration. Launch-with-game uses a user process, not a service.

Player records and restoration journals are excluded from public source/package staging and retained during uninstall so the library and recovery evidence are not lost.

The unified installer defaults all feature checkboxes on. Unchecking **Live Mining Recognition — SCREEN READING** keeps its native capture/OCR engine out of the installed tree and component cache. Other modules do not depend on screen reading. Removing this add-on also removes previous managed Full assemblies and its downloaded archive. Small features share Core UI/runtime code; optional provider resources and services are selected separately. The one installer contains all components, but extracts only the selected archives. See [modules](modules.md).

No usage analytics, beacon, crash uploader or analytics consent page is installed. Publisher-side GitHub release download counts measure asset downloads, not unique users or active usage.

## Removal and recovery

Launcher opening and installation-file events trigger patch protection before
play. Automatic checks pause during play and when the launcher is closed.
Outdated, exclusively owned SynthStrings packs are quarantined in AppData before
rebuilding against fresh game text. Home provides specific results and direct
Text settings controls, including an explicit backed-up switch from an existing
pack to generated SynthStrings. See [patch protection](synthstrings-patch-protection.md)
for ownership rules, checks and timing limits.

Native generation, blueprint annotation, reputation annotation and older Python editors now use one managed transaction layer. It records originals **before** changing game text and rejects linked/hard-linked targets.

Setup provides **Remove SynthStrings** separately from uninstall. Uninstall also cleans recorded channels:

1. Disable further managed writes.
2. Verify recovery hashes. Restore unchanged owned files byte for byte, or remove a file SynthScan created when it still matches the owned version.
3. Preserve later user.cfg settings; remove only SynthScan's added language line when applicable.
4. For pre-existing localization files, undo unchanged owned key lines while keeping unrelated later edits. Preserve/report same-key conflicts. Do not delete a newly created override later edited by another tool.
5. Restore recorded permissions only if the current ACL matches the recorded grant. Preserve externally changed permissions. Remove only recorded directories that are empty.

Interrupted updates retain a durable pending record. Cleanup conflicts prevent silent re-enablement. Permission restoration may require elevation; Setup offers **Restore text permissions** when needed. Uninstall records unresolved cleanup in `native/uninstall_result.json`, rather than claiming all changes were removed.

## Permission repair

The per-user installer requests no administrator rights by default. **Allow game-text access** is a separate explicit elevation request for protected Program Files installations. It records the original and granted discretionary ACLs in AppData. New grants target the English localization directory and relevant text files; they are not recursive or inheritable across unrelated content. Alternate-administrator credentials are refused to avoid mixing Windows accounts' journals.

Historical broad grants without a recorded original ACL cannot safely be represented as automatically reversible.

## Older installations and local cleanup

Older versions created `global.ini.synthscan-blueprints.bak` and `global.ini.synthscan_bak` beside game text. The old developer experiment also left `synthscan_pulse_test.cfg` in LIVE. Those **three artifacts were archived in AppData with SHA-256 records and removed from their old locations** during this cleanup. The active localization override and user.cfg were retained so gameplay and SynthStrings remain available.

Generic `global.ini.bak`, `global.ini.bak_before_hud_shortening` and `global.ini.pre_weight_backup` files were preserved: their names do not establish ownership. The new installer does not create them.

An older generated override has no trustworthy pre-install baseline. The removal UI explains this and offers explicit archival of the complete marked legacy override before removing it. Custom content remains recoverable in the archive; this is not exact restoration of an unknown original file. The old language line is also retained when its ownership is unknown.

## Validation and limits

Unified-alpha validation on 9 November: **960 Python tests passed (12 skipped)**. A real per-user validation installer completed three successive selections (server ribbon + Hangars, all features, then all without recognition), removed the reader, and uninstalled while preserving the fixture's saved records. The validation installer uses a separate registration identity to protect the developer's installed copy; the release workflow repeats the production identity on a fresh hosted Windows runner. Packaged-runtime checks also exercise the real native host/bridge with synthetic game files and account access disabled. Release-specific CI evidence is attached to the GitHub release; this is not a claim that every live game feature has been re-tested on another person's PC.

- Earlier managed-text cleanup validation: **807 tests, 23 skipped**, passed. The subsequent interrupted-temp-recovery and package-exclusion cases also passed in the **23-case cleanup suite**. Tests use temporary fixture game folders, not live player files.
- Coverage: fresh install/removal, exact originals, later settings/foreign edits, same-key conflicts, failed replacement, crash recovery, opt-out, repeated enable/remove, backup retention, legacy archival, hard-link refusal, tampered recovery copies and a Windows ACL roundtrip on a private temporary fixture.
- Native rebuild and all 512 self-tests passed. A synthetic ZIP64 game installation exercised the actual native-to-Python setup bridge, confirmed the pre-write journal, and restored the original game-folder contents without sidecar backups. The public checkout passed 753 Python tests (56 skipped). Regression tests do not replace an elevated install/uninstall exercise on a clean Windows account.
- Unknown backups, old unrecorded ACLs and externally edited files are not deleted blindly. The app is contained and reversible for recorded changes; it is not a zero-footprint application.

## Reviewed implementation

- [Managed transaction/recovery](../game_text_lifecycle.py)
- [Setup/removal controls](../app_launcher.py), [setup](../community_setup.py)
- [Native delegation](../native/synthscan/include/ManagedGameTexts.h), [generation](../native/synthscan/src/GameTexts.cpp)
- [Blueprint updates](../blueprint_strings.py), [reputation updates](../tools/sync_reputation_names.py)
- [Permission repair](../game_text_access.py), [uninstall](../community_uninstall.py)
- [Paths](../installation.py), [package exclusions](../tools/package_community.py)
- [Cleanup tests](../tests/test_game_text_lifecycle.py)
