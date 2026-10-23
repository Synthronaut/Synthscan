# Privacy and local data

SynthScan has no SynthScan account server, shared player database, analytics,
crash upload, or automatic sharing service in this release.

- Each Windows user stores settings, inventory, blueprint ownership, reputation
  snapshots, mining diary, bookmarks and session history under
  `%LOCALAPPDATA%\SynthScan`. The download contains an empty player profile.
- Game definitions, icons and service schemas are generated locally from the
  selected installation. `loginData.json`, game logs and personal screenshots
  are never included in a distribution.
- To read reputation and active missions, the app uses the existing signed-in
  game's credential in memory, over TLS, directly to the game's
  `*.cloudimperiumgames.com` service. It does not request your password, sign in,
  refresh credentials, or accept another player's identity as an input.
  Returned reputation subjects must exactly match the locally verified character.
- Credentials are not written to SynthScan's snapshots or diagnostics. Service
  errors shown by the app contain only the exception category.
- The OCR overlay processes frames locally. Clipboard coordinates are read only
  when you arm coordinate capture. Explicit diary/bookmark exports include the
  information you choose to share; review those files before posting them.
- Optional native UEX integration uses credentials you enter locally and contacts
  that service. It is not needed for reputation or the HUD. No UEX credential or
  refinery community service is configured in this distribution.
- Optional Windows timing/network diagnostics may request administrator access.
  Normal setup, reputation, game-log monitoring and OCR do not require it.

Local profile files are ordinary files protected by your Windows account's file
permissions, not separately encrypted. People using the same Windows account,
administrators, backups and malware may access those files. Use separate Windows
accounts to isolate different people on one PC. Different PCs do not exchange data
through SynthScan. Do not publish your profile folder, game login files or raw logs.

English localization modifications live in the selected game's folder and are
therefore shared by people who share that exact game installation. Corporation
numbers are a snapshot for the last verified character, not a live in-game value.
Switching accounts requires a fresh verified read and a full game restart before
the new labels are loaded. Separate game installations are recommended for shared
PC accounts that need independent text files.
