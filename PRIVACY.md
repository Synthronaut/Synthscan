# Privacy and local data

This describes the updated source and builds verified against it. It is not a
certification of previously published installers; check the release's build and
validation evidence before distributing it as privacy-hardened.

Windows screen reading targets the Star Citizen window surface, not a monitor
or desktop rectangle. The process name and game window class are checked, and
off-game crop areas are zero-filled. If window capture is unavailable, screen
reading waits; it does not fall back to desktop screenshots.

Open **Privacy & capture** in the sidebar, or Settings → Privacy & capture.
Pause stops new captures. Automatic pause on focus loss is enabled by default;
the game's own HUD and SynthScan's windows remain usable. A recent result or
request already in progress may finish. The page previews a game image in memory;
leaving the page clears that preview. Only its explicit Save action writes a PNG.
Normal community builds do not automatically save OCR/debug images, even if an
older recording setting remains in the profile. Existing saved images are not
silently deleted. Manual imports and explicit capture/export commands are separate
user actions.

Game-account access is a separate permission. New profiles require opt-in before
session credentials are loaded. Disabling it prevents subsequent account requests;
an already-running request may finish. OCR does not require this permission.

These controls describe implemented behavior, not an OS sandbox around the whole
application. The current release must not be advertised as independently audited
or as having OS-enforced offline OCR. See [verification and remaining requirements](docs/privacy-review.md).

SynthScan has no SynthScan account server, shared player database, analytics,
crash upload, or automatic sharing service in this release.

Home keeps a local recap of current and previous game sessions: received
blueprint and contract notifications, verified reputation balance comparisons,
and refinery-completion reminders. These records are stored in the player
profile, are not uploaded, and are excluded from community source and packages.

- Each Windows user stores settings, inventory, blueprint ownership, reputation
  snapshots, mining diary, bookmarks and session history under
  `%LOCALAPPDATA%\SynthScan`. The download contains an empty player profile.
- Game definitions, icons and service schemas are generated locally from the
  selected installation. `loginData.json`, game logs and personal screenshots
  are never included in a distribution.
- To read reputation, active missions and optional social information, the app uses the existing signed-in
  game's credential in memory, over TLS, directly to the game's
  `*.cloudimperiumgames.com` service. It does not request your password, sign in,
  refresh credentials, or accept another player's identity as an input.
  Returned reputation subjects must exactly match the locally verified character.
  Social requests identify the selected recipient to CIG. Friend/party actions
  require an explicit action; incoming-request automation has separate controls.
- Credentials are not written to SynthScan's snapshots or diagnostics. Service
  errors shown by the app contain only the exception category.
- The OCR overlay processes frames locally. Clipboard coordinates are read only
  when you arm coordinate capture. Explicit diary/bookmark exports include the
  information you choose to share; review those files before posting them.
  Manual clipboard-image import also requires a user action. Terminal image
  transfers between SynthScan processes use bounded memory, not temporary PNGs.
- Mining valuations fetch public commodity, terminal and marketplace-average
  lists from UEX over HTTPS without an account or token. Quotes are cached
  locally. These requests do not send your rock scans, location, game credentials
  or inventory. The normal network connection exposes your IP to UEX.
  Set `uex=0` in the local native settings file to disable UEX requests.
- The optional Hangars HUD reads public timing definitions from
  `https://exec.xyxyll.com/` over HTTPS when enabled and caches them locally.
  Requests contain no account, shard, inventory or game credentials. The site
  receives the normal connection IP. No remote JavaScript is executed.
- Optional UEX account/reporting features use credentials you enter locally.
  No UEX credential or refinery community service is bundled in this distribution.
- Optional Windows timing/network diagnostics may request administrator access.
  Normal setup, reputation, game-log monitoring and OCR do not require it.

The optional game-text permission repair grants your Windows identity modify
access only to the English localization folder and user.cfg. It does not grant
access to game executables or read account credentials.

Local profile files are ordinary files protected by your Windows account's file
permissions, not separately encrypted. People using the same Windows account,
administrators, backups and malware may access those files. Use separate Windows
accounts to isolate different people on one PC. Different PCs do not exchange data
through SynthScan. Do not publish your profile folder, game login files or raw logs.

Manual compboard quantities are saved in `compboard_inventory.sqlite3` under the
local player profile. They are not uploaded, synchronized to another PC or
included in community packages. Reading the hangar HUD does not change counts.

English localization modifications live in the selected game's folder and are
therefore shared by people who share that exact game installation. Corporation
numbers are a snapshot for the last verified character, not a live in-game value.
Switching accounts requires a fresh verified read and a full game restart before
the new labels are loaded. Separate game installations are recommended for shared
PC accounts that need independent text files.

The Hangars HUD also reads CIG’s public Persistent Universe status RSS feed to
flag announced server resets. Requests to this feed and the public timer include
no player, account, shard or inventory data. Verification state stays in the
local player profile.
