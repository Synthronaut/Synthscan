# Mission and wallet history

Open **Mission & Wallet Log** in the Home sidebar. Collection starts with the
native app and continues while its owner is running. It uses the existing
**Privacy & capture → game-account access** permission. Turning that permission
off stops new collection and account requests; saved history remains available.

The page provides **All activity**, **Missions**, **Reputation changes**,
**Mission rewards**, **aUEC ledger**, and **Session recaps** views. Search and
filter by outcome, current/all sessions, increases/decreases, and wallet category.
Select an entry to inspect the underlying balance window and comparisons.

## Missions pop-out HUD and completion timing

The Missions HUD has four sub-tabs: **Active**, **aUEC**, **Reputation**, and
**Runs**. Active follows the selected observed contract and uses the same ledger
for available payout, accepted participants and configured reputation rewards.
Party splits remain labeled estimates. The aUEC and Reputation views show the
current session's observed increases and decreases; Runs shows recent saved
outcomes and durations. The HUD projection is independent of desktop filters.

Elapsed time starts at a logged acceptance and freezes at the logged outcome.
It is wall time, including menus, travel, logout time and time away, rather than
measured active play time. A service's first observation of an already active
mission is not treated as its acceptance. Missing acceptance evidence shows
**Start unknown**. Restarts and duplicate notifications do not reset a captured
start. Saved event evidence supports timing older missions when acceptance was
actually captured; otherwise their full durations remain unknown.

Duration is included in the mission/reward table, entry details, and CSV, JSON
and HTML exports. Negative reputation and wallet changes remain visible, but
balance changes are not automatically relabeled as a mission's exact reward.

The recorder publishes a bounded `mission_hud.json` in the private profile.
Native controls read it without adding another account poll or reading the
SQLite database from the HUD. Expired or wrong-owner snapshots are not shown
as a live ledger. Screen reading is not required.

When the selected contract finishes, Active keeps a completion card until the
next active contract. A retained result from before a restart is labeled as a
previous session. It shows the configured base, observed reputation change,
accepted participant count, available before/after balances and the completion
time. Reputation also shows that completion summary and before/after balances.
A configured 250-point reward does not overwrite an observed 50-point gain;
with five observed accepted participants, that is labeled a matching one-fifth
scenario. The comparison does not establish a universal distribution rule.
Standard faction reputation rows use the organization name without the
internal `/ FactionReputation` suffix; distinct tracks retain their label.

The recorder caches mission definitions using the game build and reference
file fingerprints. Unchanged catalogs are not rebuilt on each periodic check;
changed references invalidate the cache. This avoids repeated catalog scans
pausing live ledger publication during play.

## Recorded evidence

- Mission identity, definition, title, acceptance, completion, failure,
  abandonment/cancellation, and share notices from Game.log. Replays and duplicate
  completion notifications do not create another completed mission.
- Every complete, verified own-character reputation snapshot, including negative
  changes, individual organization/track balances, and read timestamps.
- Verified own-character wallet balances from read-only LedgerService/GetFunds.
  The empty request uses authenticated context; every returned owner must match
  the verified character before funds are retained. Currency identifiers are
  resolved from the installed game schema; aUEC is distinct from UEC and REC.
- Accepted participant count, mission owner/recipient role, source read times,
  and uninterpreted service share vectors. Share vectors are not assumed to be
  reputation split fractions. Participant observations older than 90 seconds
  at mission end do not establish an eligible-recipient count.
- Configured completion reputation and fixed payouts when exposed. Missing
  calculated payouts remain unknown. A reward inferred only from a referenced
  filename is explicitly weaker than an extracted numeric reward record.

## Comparison rules

Balance differences are exact for the retained before/after samples. Association
with a task is a correlation. Multiple endings in the same relevant window,
gaps exceeding 90 seconds, missing balances and session boundaries remain
ambiguous. A ten-second clock tolerance accommodates short differences between
service and local game-log timing. The logger does not force a nearest-mission
match or split an observed change among overlapping tasks.

Each reward comparison shows the base amount, observed change if associated,
and the base divided by a recent accepted-participant count. A full-amount or
equal-split match is a numerical comparison, not proof of a universal game rule.
Unexplained percentages and missing observations are retained as such.

## Wallet coverage and reconciliation

The available service returns balances, not an itemized transaction history.
Every observed aUEC increase/decrease is retained, even without a mission match.
Payments, transfers, purchases, repairs, fuel and fees between two reads can
combine into one net change. Offsetting transactions can leave no visible
change. The page and exports do not claim to recover those hidden transactions.

Right-click a wallet entry to label a cause you recognize: mission reward,
player transfer, repair, refueling, store purchase, vehicle/equipment, cargo
trade, fees/fines, other, or unclassified. Labels are recorded as **player
classifications**, with the original balance evidence intact. The service does
not automatically identify purchases, repairs, transfers or other individual
transactions from a net balance change.

Positive aUEC windows with exactly one completed mission, no other mission
endings, no session boundary and no long sampling gap are labeled **Mission
reward (correlated)** automatically. The mission name and available reward
organization are shown in the ledger, HUD and exports. A reward organization
is not presented as a verified payer or an individual NPC mission giver.
An explicitly resolved giver can be displayed when the source provides it.
Unmatched/overlapping windows stay unclassified, and player classifications
always override an automatic correlation. Session reconciliation separates
player-classified amounts, correlated mission inflows and unclassified net.

Session recaps show completion/failure/abandonment counts, first/last-read net
reputation, wallet opening/closing balances and observed increases/decreases.
Player-classified and unclassified net amounts reconcile the observed wallet
change. A remaining decrease is an **unclassified net outflow**, not a fabricated
list of purchases. Observation times disclose partial-session coverage. A
contract accepted before a game restart and completed afterward belongs to
the completion session; its acceptance evidence remains retained.

## Storage and export

Evidence stays in `%LOCALAPPDATA%/SynthScan/native/mission_log.sqlite3` using
SQLite WAL. Raw observation rows survive app restarts. Only the logger writes
the journal; the native page reads a bounded published view. Temporary capture
evidence used during development is replayed idempotently.

**CSV** exports mission rows and observed reputation/wallet changes. **JSON**
also includes source samples, lifecycle events, participant observations and
player classifications. **Report** exports readable HTML with session recaps,
missions, reputation changes and aUEC changes. Exports contain all retained
history, independent of the current page filter. They are local files chosen by
the user. No other players' account identifiers, credentials or tokens are stored
or exported. Journal/view/command/evidence files are excluded from release
packages and source control.
