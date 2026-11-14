# HUD and shard-tracking implementation

**Player FPS and reliability update, October 18:** the administrator helper now
also collects StarCitizen.exe frame events using the Intel-signed PresentMon
2.6.0 standalone CLI. `PLAYER FPS` appears independently of server FPS. Absolute
event timestamps, PID, swap chain, and freshness are checked. The metadata IPC
now permits atomic replacement during reads and skips/retries transient sharing
failures instead of terminating packet collection. There are 86 isolated tests,
plus live compact/normal ribbon checks with no clipped text or callback errors.
The five-metric requirement and remaining source gaps are recorded in
[player FPS findings](research/PLAYER_FPS_FINDINGS.md).

**Network RTT implementation, October 18:** a separate passive Windows reader
now decodes the game's unencrypted, CRC32C-verified ping/pong control exchange
with DisplayInfo off. The HUD receives fresh session-matched timing metadata
and labels it `NET RTT`. It uses a sixteen-sample average and game-clock send
calibration to avoid artificially fast readings from late packet processing.
This is capture timing, not a validated exact match to DisplayInfo's average.
The reader requires a manual administrator launch for each game run for now.
There are 79 isolated tests. Server FPS/population and encrypted gameplay
decoding remain unresolved; ordinary and elevated memory-read checks were both
denied. See [network investigation](research/NETWORK_PROTOCOL_FINDINGS.md).

**HUD field correction, October 18:** unavailable ping, server FPS, population,
and entity fields are omitted from the ribbon. The permanent unknown-health box
and green `PU: ONLINE` substitute have been removed. A health badge appears only
for an observed symptom. The entity painter no longer bypasses freshness checks
by reading a historical count directly from the log reader. Location hints are
labelled `LAST LOC`. Medical imprint is omitted: the former dialog's claim of
automatic terminal sync had no implementation. The retained `RESPAWN NOTE`
dialog explicitly describes manual entry, and existing saved text is preserved.

The isolated suite passes 62 tests, including actual canvas output before and
after metric expiry. A temporary-record preview opened all six pages, saved a
manual note, and checked both ribbon sizes with no clipped text or callback
errors. With the current log, the compact ribbon is 699 by 24 pixels and shows
shard identity, return history, region, and the last location hint. These changes
correct misleading presentation; they do not provide DisplayInfo-off telemetry.

**Usability update, October 18:** automatic launch is installed through the
current user's Windows Startup folder. A hidden process-name watcher launches
SynthScan once per Star Citizen run, reuses an existing app, and respects manual
exit until the next game run. Automatic starts keep the MFD in the tray; opening
the usual shortcut restores that same window. The tray controls automatic launch
and compact mode. Compact mode preserves the existing style, uses a 24-pixel
height, and fits width to content. Both modes passed text-clipping checks.

The tray HUD toggle no longer requires opening the lazy-loaded Settings page.
Refinery parsing now respects explicit SCU/cSCU units instead of dividing large
SCU values by 100, and excludes percentages from ore quantities. The isolated
suite passes 59 tests. All six feature pages opened without callback errors in a
temporary-record preview, including hidden startup and window restoration.
The real watcher launched the app for the currently running game; disabling and
re-enabling the watcher left that app open. Inventory, owned blueprint records,
and recipes were verified unchanged. These checks do not establish complete
end-to-end OCR/inventory/crafting correctness or solve the telemetry source limit.

**Latest source investigation, October 18:** both tested own-shard service
lookups explicitly reject self-queries. Static inspection also found evidence
that the FPS logging CVar is dedicated-server-only. The core DisplayInfo-off
feed remains unimplemented. See [source findings](research/DISPLAYINFO_OFF_FINDINGS.md)
for observed responses, reproducible schema inspection, and remaining limits.

**Layout restoration, October 18:** the user requested the prior appearance.
The HUD's original 28-pixel height, 1680-pixel maximum width, painter, palette,
fonts, and field order have been restored from the pre-change backup. The
unrequested server-page button and evidence row were removed; all seven page
builders now match the original layout. Saved records were preserved. Numeric
source research remains incomplete and is not a reason for further UI redesign.

October 17, 2026 · tested installation: Star Citizen branch `sc-alpha-4.10.2`,
client build `12913470`.

**October 18 update:** live validation exposed wrong digits in the original
bitmap reader. Production now uses narrow-field recognition with agreement and
availability checks, plus window-surface capture when available. There are 50
isolated tests, including real captured frames. See
[WINDOW_CAPTURE_FINDINGS.md](research/WINDOW_CAPTURE_FINDINGS.md) for the measured
results and remaining limits. The debug-off source requirement is still unsolved.

## Delivered

The HUD now has a single main-thread owner for log-derived state and UI updates.
One incremental log reader preserves partial UTF-8 lines, detects replacement or
truncation, resets when the game process stops, and records distinct join events.
A bounded queue carries optional screen observations from a separate capture worker.
Mining OCR no longer determines telemetry polling cadence. Hiding the ribbon does
not stop session collection.

Every numeric field has a source, observation timestamp, age, and availability
status. Old numeric readings expire after five seconds. A queued capture cannot
cross a join boundary, even when the new join is to the same shard. An observed
simulation-server name change inside a shard invalidates the former node's metrics.
Partial bitmap keyword matches and impossible local/shard population pairs are
rejected instead of being turned into a valid-looking reading.

The former TCP-to-AWS latency fallback has been removed. Missing measurements no
longer produce a healthy 96% score. Zero FPS is a stall observation, while a lack
of FPS measurements is unknown. Alerts describe symptoms and do not claim a crash
probability. Unexpected closure of the current remote replication channel can be
reported from the log without the debug block; the local frontend channel being
destroyed during a normal join is explicitly excluded.

Full shard IDs identify visits. They include the region and deployment component;
neither a short number nor a friendly name is a sufficient identity. Reopening
SynthScan in the same join does not add a visit. Later same-shard joins do. Old
records with receipt-time timestamps close to the actual join are aligned while
retaining the original timestamp as `legacy_joined_at`. Ambiguous old short-ID
records are preserved rather than asserted to be exact matches.

Personal reminders store a label and user-selected duration against the full shard
identity. They survive hopping away and back, and appear on the ribbon. Their
expiry is a personal reminder, not evidence that an in-game cooldown is complete.
Matchmaking itself is not controlled.

The desktop server card uses current observations rather than falling back to
historical averages as if they were live. Old summaries without a known sample
history are labelled legacy/unverified. New session summaries count each observed
sample once, accept valid zero readings, and are persisted periodically and on
close. Writes use atomic replacement. Unreadable original records are preserved;
an unavailable history store is surfaced in the ribbon.

Additional corrections include the unreachable entity capture region, the missing
monitor-switch constant, unsafe inferred numeric station IDs, overly broad queue-name
guesses, and repeated DPI scaling of persisted window dimensions. The fitted server
notebook now keeps its action buttons on-screen on the tested two-monitor setup.

## Live source investigation

| Candidate | Observed result | Decision |
|---|---|---|
| Existing `Game.log` and 80 backups | Useful join/location/award events; no established live server-FPS, ping, population, or restart feed | Use for the events actually present |
| `net_log_fps_interval` | Present in the executable with logging help text; submitting interval 1 produced no usable readings in the observed console or Game.log | Unavailable as a verified provider in this installation |
| `net_dump_connections` | User confirmed the console command was silent | No provider implemented from this command |
| ICMP to the actual join endpoint | Two requests timed out | Do not present the timeout as a server failure or substitute another host |
| TCP to an AWS API endpoint | Existing app measured this, not the game connection | Removed |
| Compatible visible DisplayInfo pixels | Existing fixed-font decoder retained behind complete-row checks | Optional diagnostic source only; not a debug-off solution |
| PresentMon / Windows frame events | Documented independent source of client frame measurements | Not integrated in this phase; cannot supply server population or server FPS |
| Embedded `GameTelemetryService` schema | Two protobuf descriptors decoded from the client, with 28 message definitions covering actors, vehicles, weapons, turrets, and haptics; no required network/population/shard fields | Not a provider for these HUD measurements; runtime access was not assumed |
| Static game assets | Useful research path for IDs and recipes | Cannot supply changing live network or population measurements |

The user restored `net_log_fps_interval 0` and `r_DisplayInfo 0`. A subsequent game-log
entry confirmed DisplayInfo was set to zero. `USER.cfg` was not changed. No game
process memory was read or written, no matchmaking action was taken, and no game
files were patched for this investigation.

Silent commands do not prove that every logging facility is impossible. They do
mean that compiled strings are insufficient evidence to ship a functioning provider.
The first review's logging lead has therefore been tested and narrowed, not promoted
to a promised solution.

Further static inspection found `sc/game/telemetry/v1/api.proto` and `types.proto`.
Their decoded metadata is saved in `research/game_telemetry_schema.json` and can be
reproduced with `tools/inspect_game_schema.py`. The streaming response contains
vehicle, weapons, events, actor, force-feedback, and turret frames. The event enum
describes actor spawn/death/seat/respawn/downed events, not server recovery. The
schema contains no fields for the requested ping, FPS, populations, or shard identity.
This is stronger evidence than inferring API usefulness from the name "telemetry".

An index-only inspection of all 1,379,308 P4K entries also recorded potentially
relevant text/config filenames in `research/p4k_diagnostic_paths.json`. File names
are not evidence of a runtime export. No archived asset was extracted or executed.

## Validation

39 isolated regression tests pass. They exercise real state-merging paths as well
as partial lines, UTF-8 boundaries, log truncation, game exit, reconnects, stale and
cross-session samples, full-identity history, reminders, legacy timestamp alignment,
unavailable storage, zero values, unknown health, and server transitions within a shard.

The full app was launched and visually inspected on the current two-monitor setup.
The final disposable preview reported zero Tk callback errors, all shard action
buttons mapped inside the window, 18 existing history cards without a new duplicate
join, and a passing reminder create/save flow. The preview's writable JSON records
were isolated in a temporary directory. Initial preview migration output and original
records were preserved in the backup folder; the original real records were restored
after that first preview. Inventory and blueprint files were not modified.

A real server crash or an actual matchmaking hop was not induced. Recognition of a
future loading-screen codename and numeric decoding of the current build's debug
text have not been comprehensively validated against a labelled capture set. These
are material limits on the screen-reading path.

## Remaining central problem

Reliable debug-off game ping, current server population, shard population, restarts,
and server FPS still require a verified runtime data source. This implementation
does not claim to have solved that requirement. With DisplayInfo off in the observed
session, those fields correctly remain unavailable.

The most useful further research is another accessible diagnostic/export facility
or a CIG-supported local telemetry feed. A small timestamped, read-only export of
full shard identity, active simulation server, game RTT/loss, both populations,
server FPS, and recovery state at roughly one sample per second would supply the
needed information. A richer OCR model or a static asset catalog cannot recover
runtime measurements that are neither logged nor rendered.

## Primary references

- [Intel PresentMon](https://github.com/GameTechDev/PresentMon): ETW frame-event collection and client frame metrics.
- [CIG DGS Mesh Node description](https://robertsspaceindustries.com/en/comm-link/spectrum-dispatch/18227-Roadmap-Roundup-July-14th-2021): multiple simulation servers can belong to the same shard infrastructure.
- [Star Citizen Alpha 3.23.0](https://robertsspaceindustries.com/en/comm-link/Patch-Notes/19915-Star-Citizen-Alpha-3230): replication layer/server recovery context; not evidence of a current public telemetry API.
- [Microsoft IcmpSendEcho](https://learn.microsoft.com/en-us/windows/desktop/api/icmpapi/nf-icmpapi-icmpsendecho): ICMP reply status and measured round-trip time are distinct from game application measurements.
- [CIG Alpha 4.8 patch notes](https://robertsspaceindustries.com/en/comm-link/Patch-Notes/21168-Star-Citizen-Alpha-48): experimental D-BOX haptic integration, distinct from a general server-diagnostics feed.
