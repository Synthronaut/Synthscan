# Piracy HUD sources and missing population readings

Checked 8 November 2026. Static game records do not provide live shard state.

The population reader captures the game window surface and recognizes rendered
DisplayInfo labels and numeric fields. It does not read the game process. A
static definition or a console-variable name is not a live telemetry source.

The current Game.log snapshot (585,584 bytes) contained no explicit population
lines or server-FPS observations. A previous audit of current and twelve backup
logs covered 101,560,178 bytes without establishing a recurring population or
server-FPS feed. Previously recorded SocialService.GetInstanceInfo and
ContactsService.GetShardInfo probes rejected self-player queries. No new account
requests were made for this change. This evidence does not rule out every future
source; it does mean that debug-off live population is not an implemented feature.

Two fixable causes of intermittent display were found:

- A failed OCR frame replaced all previously validated metrics with an empty map.
  Partial observations also erased unrelated fields.
- The parser required a server-FPS anchor above pixel 210 before looking for the
  population row. Additional diagnostic lines or one obscured FPS label could
  therefore suppress otherwise readable population information.

The reader now locates population independently and searches the captured region
for the FPS and ping labels. Numeric confidence, two-scale agreement and labelled
population consistency checks remain in place. Tests use prior checked images,
including a shifted layout and a missing FPS anchor. This is not a claim of live
validation of every current DisplayInfo layout.

Each metric retains its own capture timestamp. A brief failed or partial frame
cannot refresh other values. Readings are live for up to four seconds; values up
to ten seconds old are explicitly aged and dimmed, then removed. Old readings do
not supply live population deltas. Session changes clear readings immediately.

When no population is available, the compact panel shows logged interdiction
report counts and the manual wait timer. Those features do not need DisplayInfo.
Logged English interdiction crime notices are limited observations, not a complete
snare/catch detector. Shard or game-server player counts are not nearby traffic.
The population history remains historical, rather than being extended with held
values.

No game commands, input, bindings, memory access or settings changes are part of
this update. The app does not silently toggle or pulse DisplayInfo.
