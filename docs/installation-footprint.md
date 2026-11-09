# Installation footprint audit — 2026-11-09

Scope: the guided Windows community installer and its normal startup/setup paths. This is a source and filesystem footprint review, not an independent security audit. Experimental developer scripts are distinguished from automatic setup.

## Files inside the selected Star Citizen channel

| Path relative to LIVE/PTU | What SynthScan does |
| --- | --- |
| `Data/Localization/english/global.ini` | Creates or updates the loose English localization override used by SynthStrings for blueprint markers, shortened labels and organization reputation numbers. Guided setup enables it by default. |
| `user.cfg` | Creates the file or appends `g_language = english` when no language is configured. Existing unrelated settings are retained. Another configured language is rejected rather than silently switched. Windows may display the filename as `USER.cfg`. |
| `Data/Localization/english/global.ini.synthscan-blueprints.bak` | A one-time backup before the Python blueprint annotator's first change. Its size is approximately one copy of the localization file. |
| Temporary siblings of `global.ini` | Setup, reputation and blueprint updates write replacement files beside the destination, then replace it. Names include `.synthscan`, `.synthscan-reputation.tmp`, and `.synthscan-bp-*.tmp`. Normal completion removes/replaces them; an interrupted process can leave a temporary file. |

The legacy Python text editor can also create `global.ini.synthscan_bak`; it is not the normal guided native setup path. It remains relevant when reviewing older installations.

Game archives, the Star Citizen executable and anti-cheat binaries are read, not patched or replaced, by these setup paths. Extracted game records, artwork and service definitions are not unpacked into LIVE. The normal installer does not install the developer's console pulse configuration, replace personal action maps, install a packet-capture driver or register a Windows service.

## Files outside Star Citizen

- `%LOCALAPPDATA%/Programs/SynthScan`: application, bundled Python/runtime libraries, OCR models and normal signed-update version directories.
- `%LOCALAPPDATA%/SynthScan/native`: settings, ownership, reputation snapshots, tags, diary, refinery records, caches and diagnostic/status files.
- `%LOCALAPPDATA%/SynthScan/reference/<build-id>` and `reference/active`: locally extracted records, artwork and generated catalogs. Build generations may occupy substantial disk space here; they are outside LIVE.
- `native/localization_backups`: setup and reputation restoration copies are kept inside the user's SynthScan profile.
- Ordinary per-user Start Menu/desktop shortcuts and the optional Startup shortcut. Inno Setup also creates the usual Windows uninstall registration. Launch-with-game is a user-process watcher, not a Windows service.

The installer is per-user and requests no administrator rights by default. There is a separate, user-invoked elevated text-permission repair if Program Files prevents localization updates. It grants that Windows user Modify permission on the English localization directory and relevant text files, including user.cfg. It rejects linked text targets and does not grant broader rights to the game directory, executable or archive.

## Current uninstall limitation

Uninstall removes installed application files and the owned startup shortcut, and preserves player records. Its localization cleanup currently restores recorded organization-name reputation annotations only. It does **not** fully remove the SynthStrings override, blueprint/shortened-text changes, the language line, localization backups, or previously granted text-file permissions. Generic foreign localization edits are deliberately not deleted blindly.

Therefore this release has a contained game-folder footprint, but it is **not** a zero-footprint install or a complete automatic restoration of the original game folder.

## Recommended cleanup work

1. Record an installation ownership journal: pre-existing files, pre-install hashes, exact changes and original permissions.
2. Keep persistent backups under AppData; leave only atomic replacement files temporarily beside game text.
3. Offer explicit removal of SynthStrings on uninstall. Restore only unchanged, owned changes; preserve third-party edits and unrelated user.cfg settings.
4. Make the game's text-file changes visible in setup and provide a HUD-only choice.
5. Remove abandoned temporary files only when their ownership and inactivity can be established. Do not delete generic game backups based on their filenames alone.

This audit made no changes to the user's game installation.

## Reviewed implementation

- [Installer](../installer/SynthScan.iss)
- [Setup and backups](../community_setup.py)
- [Native localization writer/removal](../native/synthscan/src/GameTexts.cpp)
- [Blueprint localization updates](../blueprint_strings.py)
- [Reputation updates](../tools/sync_reputation_names.py)
- [Text permission repair](../game_text_access.py)
- [Uninstall cleanup](../community_uninstall.py)
- [Application/profile/reference locations](../installation.py)
