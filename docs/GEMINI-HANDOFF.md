# SynthScan migration handoff — 10 November 2026

## User mandate

The user wants the desktop interface migrated to TypeScript because repeated native UI fixes have not eliminated resetting, flashing and painting problems. Frequent iterations must reach GitHub and installed users without manual reinstallation. Preserve existing player records and functioning engine/HUD behavior. This is an authorized migration direction, not permission to reset profiles or send real social requests during tests.

## Current truth

Production remains Windows native C++ desktop/HUD plus Python services. No TypeScript production host exists yet. `ui/` is a buildable development foundation ONLY: static prototype and proposed typed bridge interface. It has no game connection, account access or write capability. It does not replace the installed application. Do not describe migration or automatic publishing as completed.

Latest functional source commit before this handoff: 43eb1d1. It includes Home background painting fixes, installed patch display, neutral “Game text unchanged · No action needed”, and Feature modules moved to Settings. Earlier work already on main includes 50-person action limit, random 0.09–0.99s invitation gaps, three contract-accept attempts at least two seconds apart, and AFK first/subsequent waits randomly 5–12 minutes. Do not revert these or introduce timing changes as anti-detection claims.

Local development workspace: C:/Users/Dev/Documents/SynthScan. Actual Git checkout: release/public-source-v3. The workspace root is NOT a Git checkout. GitHub: https://github.com/Synthronaut/Synthscan, branch main. Root files and checkout can diverge; fetch main and inspect before copying. Other chats have edited the same workspace. Read AGENTS.md and DESIGN.md.

## Architecture to implement

Keep the working native engine, Windows game capture, OCR, HUDs and input adapters. Replace desktop Home, People, Settings and remaining pages progressively with a TypeScript UI. Evaluate a WebView2-backed host (Tauri is a candidate, not an already-approved dependency). Measure working set, startup and idle CPU on this user's constrained PC before choosing the host. Do not replace native game HUDs with web overlays without separate measurement.

Use a narrow authenticated local bridge. UI must not receive login tokens or arbitrary filesystem/shell access. Prefer a typed host IPC adapter over an unrestricted localhost HTTP service. If HTTP/WebSocket is used, bind loopback only, require per-session credentials, validate origin and commands, and reject replay/stale-owner/session messages. Reuse the existing service validation; do not implement account operations in the browser.

Start with People: key rows by stable player ID; preserve scroll anchor, search, highlighted IDs and drafts across snapshot refreshes. Maintain Action list independently, cap it at 50, and apply ordinary click toggles. Preserve self purple, party blue and friend green priority, individual colored tags, recipient receipts, pause/cancel, current-shard/fresh-friend eligibility rules and existing repeat-request behavior. Sorting/refresh must never recreate the entire page. Reconcile removed IDs explicitly. Use a synthetic 500-player changing roster for regression tests.

The bridge.ts contract is a sketch. Inspect companion_features.py, player_services.py, party_invites.py, native_bridge.py and native/synthscan/src/SynthCompanion.cpp before extending it. Inventory all existing commands and their validation. Do not expose arbitrary social writes or automatically execute an action on page mount.

## Update delivery: existing components, not a blank slate

`app_updates.py` already branches to `module_distribution.prepare` for module_schema=1. Module packages are authenticated by signed catalog, integrity inventories and hashes. Downloads are cached by package hash. Fresh version assemblies and activation rollback already exist. Keep signatures, trusted hosts, monotonic catalog checks, selected features and saved records. Never replace this with downloading/running raw main-branch files.

Relevant files: tools/package_modules.py, tools/package_modular_updates.py, module_distribution.py, app_updates.py, update_agent.py, update_trust.json, .github/workflows/modular-release.yml. Catalog endpoint is the update-channel release asset synthscan-modules.json. Signing key is a protected GitHub secret; do not export it or put it in source.

The current workflow couples engine builds, module packaging, installer creation and publication. Split update-only publication from installer creation. A push should automatically run validation, package the changed application/assets, sign and publish immutable artifacts, then promote the update catalog LAST. Failed checks must leave the working public channel intact. Serialize channel promotion and prevent an older concurrent run from superseding a newer one. Use a version/sequence policy compatible with existing clients; inspect validators rather than inventing a version string.

Reuse unchanged native binaries only after verifying their provenance and exact source/build-input identity. Native C++ changes require compilation. Python/TypeScript-only changes can reuse compatible engines. Module ZIPs currently include versioned inventories: inspect whether global version changes invalidate every package hash before claiming changed-module-only download sizes. Do not promise binary delta updates; they are not implemented.

An installer is a first-install/bootstrap artifact. Existing users should receive signed updates through the installed updater, without redownloading the installer. For new users, either periodically rebuild a current bundled installer or implement a bootstrap install that fetches the current signed catalog. Bootstrap behavior is not yet implemented. No architecture can make raw GitHub pushes safely appear on installed PCs without build/package/publish steps; automate those steps instead of asking users to perform them.

Inspect actual startup/update cadence and activation rules. Current code stages activation until game/app windows are idle. Preserve game safety and decide how to notify users when restart is required. Do not silently remove protections just to claim instant updates.

## Next implementation sequence

1. Run ui development/build commands; select and measure host, connect read-only synthetic People snapshots.
2. Implement stable rendering/state tests before migrating production writes.
3. Connect existing validated backend actions through the restricted bridge; test with mocked services only.
4. Build update-only GitHub workflow using existing signing/catalog logic. Test in a separate channel/profile before promoting production.
5. Prove a fresh installation and an already-installed client receive a small update, keep feature selections/tags/notes/history, and roll back a deliberately broken isolated update.
6. Migrate other pages; retire old desktop paths only after feature parity and performance checks. Keep native HUDs working throughout.

## Acceptance and evidence

No surprise profile resets, no real invitations or input during tests, no new OCR for shard names. Screenshots must be inspected at small/normal/high-DPI sizes. Verify scroll/selection preservation under live refresh and resize, no white flashes, keyboard accessibility, bounded text and low idle cost. Existing local fixes had 230 focused checkout tests passing (4 skips), native self-tests and hidden paint/workspace/People fixtures. Those validate the old interface changes, NOT this migration.

Local evidence: research/quiet_text_status_20261110 and research/home_patch_status_20261110. These contain build manifests, checks, isolated renders and installation records; they are not published binaries. Installed local application is dist/native/SynthScan.exe and uses native_runtime.json to locate Python sources. Avoid rebuilding directly over a running binary; stage privately and verify source stability.

Deliver the completed implementation and precise verification results. Clearly distinguish source push, signed update promotion, installer publication and successful client activation.

## Follow-up: chat after respawn

Read RESPawn investigation at `docs/RESPAWN-CHAT-INVESTIGATION.md`. Actual logs contain a later OnClientSpawned after incapacitation, but UI readiness and chat visibility are not established. No production respawn toggle has been enabled.

## Implementation status (10 November 2026)

1. **WebView2-backed TypeScript desktop host (`SynthWebView.h` / `SynthWebView.cpp` + `ui/`)**:
   - Hosted inside `SynthCompanionWindow` (`SynthScan.exe`) via Edge WebView2 mapped to `https://synthscan.local/index.html` using an isolated `userDataFolder` (`%LOCALAPPDATA%\SynthScan\webview2-data`) and dark default background (`#0E1216`) to prevent white flashes.
   - Native game HUDs (`MinerGUI`, `MissionHud`, `SynthExecutiveHangar`, `SynthFinder`, `native_session_hud.py`), game capture, OCR, and Python services (`native_bridge.py`, `companion_features.py`, `player_services.py`, `party_invites.py`) remain intact.
   - Narrow authenticated bridge: 128-bit per-session cryptographic `bridge_token` (`BCryptGenRandom`), strict origin check (`https://synthscan.local/`), strictly increasing `client_seq` replay rejection, explicit command allowlist, and mandatory `confirmed: true` for outgoing queue execution.
   - Measured on this PC (`SynthScan.exe --webview-preview`): `startup_ms` ~2.5s, host working set ~21.8 MB, WebView2 working set ~119.8 MB, `outgoing_requests_sent: 0`, `foreground_unchanged: true`.
2. **People, Buyer Alerts, Session Recap, and Settings/Modules in TypeScript (`ui/src/`)**:
   - Keyed DOM rows (`rosterRowMap`, `actionRowMap`), preserved scroll anchor (including surviving-neighbor fallback when the top visible player leaves), preserved search, highlighted IDs, and unsaved tag drafts across snapshot refreshes and window resizes.
   - Independent Action list capped at 50 with ordinary click toggles and Shift-click range selection, relationship color priority (`RGB(193,157,255)` self purple > `RGB(116,183,255)` party blue > `RGB(121,225,158)` friend green > neutral), distinct deterministic tag colors (`Friend` vs `Friendly`), recipient confirmation modal (`Cancel` default focused, repeat-request `resend` checkbox default off), and live queue progress/receipts (`Pause`/`Resume`/`Cancel`).
   - Validated by the 20-assertion 500-player changing roster regression suite in both Node (`npm --prefix ui test`) and headless Edge WebView2 (`SynthScan.exe --webview-preview`).
3. **Automatic update-only publishing (`.github/workflows/auto-update.yml`)**:
   - Triggered automatically on push to `main` (and `workflow_dispatch`), serialized with `concurrency: update-channel-promotion` (`cancel-in-progress: false`) and stale-SHA commit guard before promotion.
   - Computes monotonic version and sequence (`tools/compute_update_version.py`), builds `ui/dist`, runs unit tests, WebView2 preview, and isolated auto-update/rollback verification (`tools/verify_auto_update.py`), reuses compatible native binaries when `native/synthscan/**` is unchanged (or compiles when changed), packages and signs module ZIPs and update manifests (`tools/package_modules.py`, `tools/package_modular_updates.py`), uploads immutable release assets first, and promotes `synthscan-modules.json`, `synthscan-update.json`, and `synthscan-update-standard.json` to `update-channel` LAST.
