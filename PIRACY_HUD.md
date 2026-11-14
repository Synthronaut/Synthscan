# Piracy HUD population watch

Open **HUD + → Piracy**. Keep `r_DisplayInfo 1` visible in Star Citizen.

The default view is a wide, opaque panel: 600 × 200 logical pixels (750 × 250
at the current desktop scale). Its mode tabs and controls share the top row.
Timer, report history and alert muting are under **Details +**. Piracy omits the
repeated server-information footer; Mining and Missions keep their existing
dimensions and appearance. Details can be collapsed again with **Details -**.

The activity HUD displays shard/server population, server FPS and ping recognized
from the rendered DisplayInfo panel. Capture and recognition run in a separate
background worker only while Piracy is selected. Mining scanning remains paused.
Turning DisplayInfo off, unreadable text, missing frames and stale observations
produce `--`; a previous value is not presented as a fresh reading. The source
expires after four seconds and is reset on a shard/session change.

The 15-minute graph samples valid shard counts at most once every five seconds.
Its displayed range identifies the vertical scale. Gaps longer than 15 seconds
are not connected. The 5-/15-minute changes require an observation near the actual
time boundary (within 20 seconds); they remain blank while history accumulates.
History is held in memory for this app session and clears on a server hop.

Inside Details, **Start wait**, **Pause wait**, and **Reset** control a manual timer. Switching
away from Piracy pauses it. A shard change or app restart resets it. It does not
detect the snare's armed state, arrivals, nearby ships or catches.

Existing crime-based interdiction reports remain separate from population.
Their absence does not prove that no interdiction occurred in a lawless zone.

## Verification — 2026-10-22

- 358 unit tests passed, including stale frames, zero counts, invalid values,
  timed trend boundaries, mode changes, in-flight old-shard frames and timer
  behavior.
- Native UI/command checks and 414 existing native self-tests passed. Timer
  buttons, mode changes, scanner pause/resume, HUD collapse/restore and dragging
  were exercised with isolated fixtures.
- Passive live capture returned repeated population, server FPS and ping values
  without game input. The installed app's bridge was then exercised while its
  activity HUD remained collapsed: it read 376 shard players, 7 server players,
  30.0 server FPS and 199.9 ms ping at the time of the check. Timer start, pause
  and reset commands worked through the installed native app. The previous mode
  and collapsed preference were restored.

Artifacts: `research/piracy_population_live_20261022.json`,
`research/piracy_population_final_ui_20261022/`,
`research/piracy_population_installed_verification_20261022.json`, and
`research/piracy_population_deployment_20261022.json`.

The compact update also passed native layout, opacity, expansion, mode-switching
and scanner checks (`research/piracy_compact_ui_20261022/`). Installed-window
verification confirmed an opaque 750 × 250 panel at the top right and three
distinct fresh game frames while the panel was visible. This confirms that the
window-surface reader continues working beneath the opaque overlay; no game
input was sent (`research/piracy_compact_installed_verification_20261022.json`).
