# Working on SynthScan

Read [DESIGN.md](DESIGN.md) before creating or changing any user interface,
installer, setup screen, HUD or navigation. Its standards are requirements,
including during small fixes. Preserve existing player records and work added
by other chats. Use isolated profiles for installation tests; never reset a
real profile to simulate first run. Publish only after the release gates pass.

## Win32 Window Lifecycle & Anti-"White Demon Box" Invariant

The "white demon box" was a notorious regression where a secondary, unpainted white window titled `SynthScan` (class `SCMinerGUI`) appeared on the user's desktop at launch: unmovable, un-interactable, and un-closeable.

Future agents and developers MUST strictly follow these rules:

1. **Zero Desktop Presence for SCMinerGUI**:
   - `SCMinerGUI` (the mining HUD view, `MinerGUI.cpp`) must NEVER be created, mapped, restored, or displayed as an independent `WS_OVERLAPPEDWINDOW` on the user's desktop.
   - It exists in only two valid display states:
     a) **In-game compact overlay** (`overlayMode_ == true`): a top-level `WS_POPUP | WS_EX_LAYERED | WS_EX_TOPMOST` HUD floating over Star Citizen.
     b) **Embedded child page** (`SynthPages::contains(hwnd_) == true`): a `WS_CHILD | WS_CLIPCHILDREN` control hosted inside `SynthPages` within `SynthHome` (`SynthScan — Home`).
   - In all other states (including app launch in desktop mode), `SCMinerGUI` must remain strictly offscreen (`-32000, -32000`) and hidden (`SW_HIDE`).

2. **Creation Coordinates**:
   - In `MinerGUI::initialize()`, `hwnd_` must be created at offscreen coordinates (`-32000, -32000`), NEVER `CW_USEDEFAULT, CW_USEDEFAULT`. Windows DWM maps default coordinates directly to the primary monitor, which creates an unpainted surface if shown before being embedded.

3. **Never Intercept Win32 Visibility to Create "Zombie" Windows**:
   - NEVER add hacks in `handleMessage` that intercept `WM_WINDOWPOSCHANGING`, `WM_STYLECHANGING`, or `WM_SHOWWINDOW` to strip `SWP_SHOWWINDOW` or `WS_VISIBLE` or return 0 from `WM_SHOWWINDOW`.
   - Modifying window flags in `WM_WINDOWPOSCHANGING` while DWM is mapping a window desynchronizes Win32 from DWM compositing: DWM presents an uninitialized DirectX/GDI surface (pure `#FFFFFF` white) while Win32 marks the window non-visible (`IsWindowVisible() == 0`), preventing input hit-testing and trapping the unclosable zombie box on the desktop.

4. **Background Brushes & WM_ERASEBKGND**:
   - Window classes and `WM_ERASEBKGND` handlers must ALWAYS erase/fill using the dark theme background brush `CreateSolidBrush(CR_BG)` (`RGB(15, 16, 19)`). Never leave background erase empty or rely solely on deferred paints when DWM surfaces are allocated.

5. **Safe Page Unmounting in SynthPages::release**:
   - When `SynthPages::release()` reparents a hosted page back to `nullptr` (desktop), it must immediately move it offscreen (`-32000, -32000`) with `SWP_NOSIZE | SWP_NOACTIVATE | SWP_HIDEWINDOW | SWP_FRAMECHANGED` and `SW_HIDE`, never leaving a reparented window at desktop `(0, 0)`.

## Oracle Hub, Game Data & Release Publishing Protocol

Read [docs/UPDATING_AND_RELEASES.md](docs/UPDATING_AND_RELEASES.md) before modifying update feeds, `blueprints_catalog.json`, `global.ini` syncers, or publishing releases.

1. **Oracle Server Isolation (`158.101.88.35`)**:
   - SynthScan's public website, data hub, and release channel live at `https://synthscan.158-101-88-35.sslip.io/` (`/var/www/synthscan/` and `/home/ubuntu/synthscan/`, Nginx site `synthscan-app`, timer `synthscan-sync.timer`).
   - NEVER modify files, Docker containers, ports, or Nginx configs belonging to other projects on that server (BTD, AXEN, Embers).

2. **Blueprint Catalog & `global.ini` Invariants**:
   - `blueprints_catalog.json` must ONLY contain obtainable reward blueprints (`isReward == true`, deduplicated via `blueprint_strings.item_key()`). Never bulk-import `isReward == false` records from `blueprints_source.json`.
   - Mission `_title` / `_name` keys in `global.ini` must NEVER contain `<EM4>Potential Blueprints</EM4>` or `<EM4>Multiple Blueprint Pools</EM4>` lists. Keep only `[X Rep]` and `[ALL BP OWNED]` / `[BP: X LEFT]` tags in titles; blueprint lists belong in `_desc` keys.

3. **Private GitHub + Self-Hosted Releases**:
   - `update_trust.json` points to `https://synthscan.158-101-88-35.sslip.io/releases/` (NOT GitHub, which is private). Do not revert `update_trust.json` or the website Download button to GitHub URLs.
   - Always ship code/UI iterations via `.\publish_release.ps1` and data-only updates by publishing to `/var/www/synthscan/data/` and running `python3 /home/ubuntu/synthscan/scripts/sync_data.py`.

