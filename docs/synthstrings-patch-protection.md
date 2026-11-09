# SynthStrings patch protection

The resident Windows watcher opens SynthScan when RSI Launcher opens. The app's
bridge provides launcher event handling when the startup watcher is not enabled.
One guard consumes the queued checks at a time. Ordinary app/bridge restarts do
not request another check for the same launcher session. No path launches,
delays, kills or restarts Star Citizen.

Checks are event driven: one at launcher opening, one when a patch starts
changing installation files, and one after those file changes settle. Windows
directory-change notifications provide the installation events while the
launcher is open. Unrelated root-file changes are ignored. There are no recurring
three-second scans or five-minute rebuild retries. The lifecycle watcher still
observes process names so it can open the app; that is not a game-file scan.

Automatic checks and installation watches pause during play and when the launcher
is closed. A player can explicitly request Check now in Text settings at any time.
An already-running operation can finish and record a restart requirement if the
game starts before its text is activated.

## Patch sequence

1. Compare the manifest contents, canonical installation path, archive identity,
   size, nanosecond modification/creation times and hashes of its first/last 64 KiB.
   This also detects manifest-only and same-size patches. It is not a hash of the
   entire archive; changes that preserve every observed fact can evade it.
2. Immediately quarantine an outdated complete SynthStrings override in AppData,
   before waiting for stable files or running extraction. Preserve the player's
   enabled preference. Without a loose override the game uses its packaged text.
3. Use a single completion event after 120 seconds of quiet installation-file
   notifications and archive age. A quiet interval
   alone does not prove patch completion, so extraction and activation also check
   that the observed game identity has not changed.
4. Extract the current game's English text directly from Data.p4k, bypassing the
   native cache. The renderer returns both its baseline and generated candidate.
5. Reject invalid UTF-8, NUL bytes, duplicate keys or aliases, an
   implausibly small baseline, missing/reordered keys or changed original values.
   Preserve original comments, blank lines and CIG's physical continuation rows.
   Annotations may append to CIG's current values; all original formatting tokens
   are therefore retained. Record baseline/output SHA-256 digests in the journal.
6. Recheck the game identity, atomically install the candidate, and check again.
   On extraction/validation/activation failure, quarantine the exclusively owned
   override and keep defaults. Retry on a new launcher/patch event or when the
   player chooses Check now; there is no timed retry loop.

All known channels receive their quick protection check before slow rebuild work
begins. New installation events can be handled on a separate worker during an
extraction, and a stopped watcher cancels only its owned renderer. Other writers
share the channel lock and cannot recreate a suspended pack
or commit against a different recorded build. Existing manual-off preferences and
cleanup conflicts remain in force.

## Ownership and recovery

Automatic quarantine requires the explicit `bedrock_game_texts` ownership key and,
when journaled, an exact match to the last owned file hash. A blueprint heading
alone is insufficient. Unrelated packs and externally edited files are preserved
and reported for review. Failed access/removal is an attention state, never a
claim that defaults have been restored.

An unchanged pre-existing language pack without generated-pack/build metadata is
an informational state, not evidence of broken strings or a failed recovery.
The journal records the first observed build separately from a validated native
baseline. A later build change is reported specifically as a potentially outdated
pack; it is not silently deleted or represented as verified.

Quarantine copies, pending-removal recovery, status, a bounded transition history
and build fingerprints live under the profile's `game_text/<channel-path-hash>`.
No recovery copies are written beside Data.p4k. A quarantined legacy full pack is
not reinstalled by later cleanup. user.cfg and unrelated settings are retained.

## Player feedback

Home displays persistent adaptation, fallback and specific failure results, with
Text settings and Patch details buttons. No action requires the tray menu.
Text settings provides Check now and an explicit Use generated SynthStrings
choice, which archives the selected existing pack before replacing it. The exact
file hash is checked again before removal; a concurrent edit cancels replacement.
Removing generated SynthStrings later does not reinstall that older full pack.
History records explanations, not just repeated generic "needs attention" titles;
old entries that never recorded a reason are omitted from the presentation.
Windows tray notifications
announce success or a problem without activating a modal window, respect quiet
time and are deduplicated across app restarts. Clicking the notification opens Home.

Writes/removals while the game is running record the affected game PIDs. Home
requests one restart for those processes because already-loaded localization
cannot be replaced. A new game process clears the restart advice. Success does
not erase an outstanding restart requirement from the same running game.

## Limits and remaining work

Protection requires the resident watcher or app to be running. The game-process
startup fallback observes a process that has already started; it does not intercept
RSI launches. There is no guarantee of intervention before localization loads if
the player starts directly through RSI, races the next check or closes all
SynthScan processes. Changes made after loading require a game restart.

Validation establishes current text coverage and preservation. It does not prove
that compiled blueprint reward mappings still describe a mission after CIG changes
its data without changing its text key. Runtime regeneration of those mappings,
signed data-only compatibility packages, and optional developer failure reporting
are separate work. This implementation makes no network requests and sends no
player data or diagnostics to the developer. It reuses the existing native
annotation renderer; it does not guess replacement keys or mission rewards.

Regression tests simulate patches and recovery using temporary installations.
The optional native `--ui-test` SynthStrings fixture renders fallback, successful
adaptation and restart notices at two window sizes without launching services or
touching an installed game.
