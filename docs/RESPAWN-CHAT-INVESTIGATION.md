# Respawn chat investigation — 10 November 2026

Production behavior: GlobalChatOnJoin in contract_share.py permits one F12 attempt per (full_shard_id, joined_at). Loading completion alone does not rearm the same join. This intentionally prevents duplicate toggle presses. contract_share_helper.py rechecks focus and lifecycle immediately before input. Tests: tests/test_global_chat.py.

Observed in the actual current Game.log (timestamps UTC):
- 01:34:08.709 OnClientSpawned, followed by StopLoadingScreen Finished at 01:34:24.614: spawn preceded loading completion by about 16 seconds.
- 02:29:16.073 a local HUD Incapacitated notification was added.
- 02:30:05.769 [CSessionManager::OnClientSpawned] Spawned! appeared, about 50 seconds later. No following StopLoadingScreen Finished was found for this later spawn in the inspected log.
- Another incapacitation notification occurred at 02:31:21.089.

Interpretation: a later client spawn following incapacitation is a promising respawn candidate. Incapacitation is NOT confirmed death; rescue/revival remains possible. OnClientSpawned also occurs during login/frontend transitions. Generic entity spawn/corpse messages and regeneration-location tutorial notifications must not trigger F12. The observed signals do not establish exactly when bed wake-up or chat visibility is ready.

Implementation still required; no live F12 was sent and no production automation changed during this investigation:
1. Extend the existing incremental log reader with timestamped, deduplicated local incapacitation and subsequent in-session client-spawn observations. Ignore historical replay, startup/frontend spawns and stale events. Correlate current game PID and join identity.
2. Use a distinct respawn event ID, not a fabricated new shard join. Keep login and respawn attempts from racing or issuing two toggles.
3. Wait for actual post-respawn readiness if a reliable log event can be established. A configurable delay after the respawn event is only a fallback and needs live observation; do not declare a guessed 5/10/15 seconds reliable. Existing loading completion is insufficient because later respawns may omit it.
4. Reuse game-focus, active-session, modifier and held-F12 checks. Cancel pending events on disconnect, another incapacitation, process replacement, disable or expiry. Never retry F12 blindly: it toggles and can reopen already hidden chat.
5. Test a normal death/medical respawn, delayed bed wake-up, revive without death, alt-tab, repeated log lines, helper restart and reconnect with mocked input first. A user-confirmed observation of when chat reappears is still needed to validate timing. Log-only evidence currently does not prove chat open/closed state.

This is a documented feasibility finding, not a shipped respawn-chat feature. The existing join action has also not been visually confirmed by this investigation.
