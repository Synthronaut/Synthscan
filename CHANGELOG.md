## Unreleased

- Deliver registered HUD shortcuts through the native message loop instead of
  discarding them before the shell handler receives the event.

- Show generic shard identifiers only once in the server ribbon, regardless of
  capitalization. Keep saved names alongside numeric shard IDs in recent visits;
  do not invent a game-name mapping when the source supplies only a shard ID.

- Add optional, customizable HUD toggle and next-tab shortcuts. Recommend F23
  and F24 for programmable mouse buttons; new users opt in through Settings.
  Preserve hidden state when cycling, release keys outside the configured focus
  scope, suppress held-key repeats and reject duplicate/reserved bindings.

- Keep piracy metrics independently through brief OCR misses, preserving their
  original capture times. Dim and age delayed values, expire them after ten
  seconds, and never use held population values for live deltas.
- Read population independently of the FPS anchor and allow diagnostic rows
  below the former 210-pixel limit. Preserve strict numeric validation.
- Show logged interdiction counts and the manual wait timer when population is
  unavailable. Document that live counts still require rendered DisplayInfo;
  the app does not silently toggle debug text or claim a debug-off count source.

- Apply readable purchase cards to the in-game Finder HUD: prominent prices,
  compact locations and green/red retail price comparisons. Preserve the existing
  layered-window transparency and input behavior.
- Present player-market ranges and filtered listings as structured HUD cards;
  retain exact quality/unit separation and existing outlier exclusions. Format
  blueprint ingredients and unlock missions as short rows rather than a text wall.
- Add raster-only HUD presentation checks that create no windows or game input.

- Remove redundant Finder material-planning and blueprint navigation buttons;
  retain one explicit add/remove-favorite action.
- Add compact ship component-slot and weapon-mount cards with counts and size
  limits. Apply exact vehicle variant patches and active-port rules; follow
  stock gimbals/turrets without mistaking turret socket sizes for gun sizes.
  Mark unresolved mount information instead of guessing compatibility.
- Document the researched shopping-list and destination-consolidation proposal
  in docs/shopping-list-plan.md; the cart itself is not implemented yet.

- Prevent redundant hide/show cycles when sidebar pages receive a second ready
  notification. Keep page transitions on a dark surface until mounting finishes.
- Add stock ship overview cards: body-part HP, stock shield-generator capacity,
  physical/energy armor multipliers, crew, cargo and dimensions. Match installed
  ship records by exact UUID; show unavailable values rather than substitute a
  different variant. Label UEX specification patches separately from game files.
- Narrow Finder categories by selected type. Group ship roles into fighters,
  haulers, exploration, mining, salvage and support; split blueprint browsing into
  ship equipment, armor, clothing, personal weapons/ammo and tools. Preserve full
  source roles and categories in search and item details.
- Refresh older vehicle metadata caches and local ship references automatically.

- Add a dark Home window with direct feature navigation and current/previous
  game-session recaps. Record blueprint/contract notifications and verified
  reputation balance changes without substituting configured mission rewards.
- Show confirmed refinery-completion notices as a small Mining HUD reminder,
  with persistent reminders dismissible from Home. Theme More menus to match.
- Replace the unconditional borderless warning with a capture-failure notice
  shown only after an actual image-capture failure.

- Preserve the pop-out HUD's screen edge across tab sizes and restarts, and add
  explicit top-right docking. Unlocking placement enables the drag interaction.
- Clear unattended automatic signature results after 1.5 seconds without a new
  reading. Require stronger marker evidence for off-aim cockpit lookalikes.

- Publish the server ribbon before optional background work. Retain explicitly
  labelled last-known shard identity for brief feed delays while hiding stale
  metrics; clear it on disconnect, process change or a prolonged outage.

- Keep Finder details in an explicit animated loading state until prices and
  crafting information can appear together. Reuse recent completed selections
  immediately and poll Finder independently of slower session collectors.

- Replace raw player-market min/max with a median and middle-50% asking/bid
  range when enough comparable advertisements exist. Exclude extreme prices and
  multi-quality ads from estimates and displayed results. Do not use unfiltered
  UEX aggregate averages as a fallback; insufficient data produces no estimate.

- Add public UEX player market browsing to Finder, with separate sellers/buyers,
  per-unit prices, listing links, age filtering and cached background refreshes.
  Export material-specific quality quantization from the local game and offer
  exact values in a dropdown; refresh those values with each game catalog build.

- Add a fifth Finder HUD tab with fast autocomplete, background UEX purchase
  locations/prices and exact-item blueprint materials, minimum quality and unlock
  missions. Confirmed ownership hides unlock missions while retaining the recipe;
  inferred or unknown ownership is labelled explicitly.
- Add signed complete application updates with staging, idle activation outside
  the game, stable launcher routing, readiness checks and previous-version rollback.
  Add exact-build SCMDB imports for blueprint sources and numeric mining stats.
  Preserve profiles and cached references on source, validation or startup failure.

- Surface each full shard identity's earliest retained observation and recorded
  visit count in the region dropdown, server-log details and exports. Add a
  HISTORY span to the HUD without treating first visits or channel uptime as
  server creation, restart/reset confirmation or continuous server uptime.

- Add Ship, Vehicle and Component filters to Item directory, with automatically
  refreshed UEX vehicle indexing and in-game dealership prices. Keep variants
  distinct, including vehicles without a published game UUID; do not substitute
  pledge prices or rental quotes for purchase prices.

- Turn Game library & artwork into Item directory: exact-item blueprint links,
  mission reward searches and asynchronous UEX retail locations/prices. Show
  catalog/source patch and dates; keep cached results offline. Distinguish reward
  pool probability from an individual blueprint's unknown chance.
- Reload the directory automatically after a complete local reference refresh.
  Limit visible search results to 300 while searching the full catalog, avoiding
  thousands of list-control insertions each time the window opens.

- Pause automatic image scanning while SynthScan desktop windows have focus,
  giving menus priority. Resume Live automatically when returning to the game.

- Restore the server region dropdown while the game is foreground. Its small
  arrow and popup accept non-activating clicks while the ribbon body remains
  click-through.
- Remove the experimental quantum travel timer and its background reader.
- Match mining heads to mount sizes: MOLE S2; Golem and Prospector S1.
  Clear incompatible saved heads with their modules and crafted bonuses.
- Add independent saved toggles for automatic party invitations and friend
  requests in the contract share helper. Both social settings default off.

- Keep contract acceptance pending after an ignored key press and retry at
  750 ms intervals while the same logged contract prompt remains active.
  Acceptance confirmation, fade/removal, notification replacement and a
  bounded timeout cancel retries. Fresh reshares can be attempted again;
  leaving a menu no longer hits a permanent one-attempt lockout.

- Move rock-panel OCR off the signature/UI scan loop with a separate OCR model.
  Add a tracked gem price path that reads matching heading/material/quality
  without waiting for mass, volume, full composition or repeated scans.
- Favor the currently aimed signature over the previous marker. Strong new
  readings bypass old-number fragment repair; weak repair expires after 1.5s.
  Rejected-row OCR caching now checks image content, so a changed number in
  the same screen position is eligible immediately.

- Replace the buy-only quick valuation with general market ranges using buy,
  sell and recent listing-history prices. Same-patch history is fetched for
  scanned materials, deduplicated per listing and weighted toward recent data.
  Keep piece/SCU and quality matching, label sparse/historical estimates, and
  reduce extreme-price distortion without requiring verified final sale prices.

- Recognize hand/ROC mineral names and their installed-game quality bands on
  the mining scan panel. Keep per-piece player buy quotes separate from SCU;
  composition volume never becomes an inferred piece count or total.
- Prioritize matching player buy averages for ship-rock value, show the main
  refined yield and unit price, and label one/two-ad estimates as limited data.
  Piece quotes can load independently of terminal feeds; stale, wrong-patch,
  wrong-unit and different item-form quotes remain excluded.

- Polished crafted laser-power entry: replace the selected value directly,
  paste signed percentages, preview head power before modules, reset to Stock,
  and cancel with Escape. Unfinished/invalid edits no longer overwrite the
  configured bonus; switching heads or profiles commits the correct item's
  value. The HUD summary now shows individual crafted bonuses or stock power.
- Keep swapped-out MOLE laser bonuses per turret, preventing same-model heads
  with different crafting results from inheriting one another's remembered bonus.

- Added quick named ship-profile selection to the HUD More menu and tray,
  including direct access to profile management and heads/modules/crafting.
  Profiles retain independent per-head crafted bonuses across same-model ships.
- Corrected the Golem's outdated fixed-Pitman configuration restriction so its
  S1 mount accepts Helix I. Clarified crafted laser-power entry and exposed
  stock/crafted status on MOLE head tiles. Added a four-profile roundtrip and
  Helix I +25% calculation regression.

- Added background public-source and app-release checks with a Data updates
  screen under Setup & reputation. Source checks distinguish changed upstream
  tables, newer application code, unavailable checks, and unverified SCMDB site
  revisions; downloading metadata never implies an update was applied.
- Rebuild outdated local references after the game closes, publish complete
  catalog generations atomically, and retain the previous generation. Recipe
  matching uses stable identities instead of ingredient quantities, includes
  newly decoded recipes, and labels unmatched older references.
- Keep Executive Hangar timing refreshed in every HUD mode. Check official
  reset notices independently of timing downloads, retain reset history across
  outages/restarts, and reject LIVE timing verification for PTU installations.

- Fixed quantum detection against live Golem cockpit frames: use the QT EXIT
  control independently of distance, exclude blue party markers, prioritize
  central navigation text instead of unrelated gauges, and show observed
  elapsed time while ETA is unreadable. Private in-flight/post-exit replay
  regression now verifies automatic box activation and hiding.

- Moved quantum timing out of the activity pop-out into an automatic passive
  box left of the permanent server ribbon. Removed the pop-out row and manual
  controls. The box hides outside fresh observed travel and avoids the HUD
  expand button when that button is docked left of the ribbon.

- Added a compact QT row and Start/Stop control to every activity HUD mode,
  with a manual elapsed fallback and experimental normal-screen distance
  progress detection. Closing-rate ETA is approximate and expires with stale
  readings; own-hull arrivals finish the timer. Live OCR validation is pending.
- Shortened juvenile Valakkar creature labels through SynthStrings to Vlk Jr
  and Irr Vlk Jr, preserving other names and descriptions.

- Fixed contract auto-accept being blocked by normal keyboard/mouse activity.
  Only modifiers and a physically held accept key block input. An active prompt
  remains eligible for up to five seconds, ending immediately on fade,
  replacement or removal, rather than expiring after 750 ms.

- Fixed the contract helper silently disabling on window close or stale session
  data. Opt-in preference is now saved locally; closing hides the window,
  stale data pauses input, and diagnostics record blocked/sent decisions.

- Added an experimental contract share helper under More and the tray menu.
  Tracks new share pushes and notification queue transitions, excludes party
  and friend requests, uses the Notifications Accept binding, deduplicates
  attempts, and reports game confirmations. Starts off until opted in; saved preference persists, while session changes
  clear queued events. Live queue/input timing remains to be tested.

- Revised AFK motion from a one-count immediate return to a fifteen-count,
  six-event pulse over at least 280 ms. First pulse waits ten idle seconds;
  later pulses wait four minutes. Added countdown and sent feedback on the
  HUD button, and cancellation between events if input or focus changes.

- Added a direct AFK on/off button beside the activity HUD's top-left collapse
  control, with a subtle green armed indicator and no menu needed.

- Added an opt-in AFK mouse jiggler to More and the tray menu. It waits four
  idle minutes, requires a verified foreground game and a fresh connected
  session, pauses for user input/background windows, and resets off on exit.
  No hotkeys, clicks, key presses, focus changes or saved armed state.

- Mining numeric-column recovery handles white, green and red resistance;
  fragmented SCU numbers are joined and faint unit labels require confirmation
  from the complete COMP row as well as a high-confidence numeric reading.

- Fixed mining scan tracking reusing mass-only composition caches; confirmed
  scans are now rechecked, target volume/ore constrain background results, and
  the HUD distinguishes unread volume from unconfirmed composition.
- Improved the small pilot-panel numeric fallback and exposed each configured
  mining head's full-power laser-to-rock distance in the mining HUD.

- Fixed activity HUD tabs and buttons being unclickable while the game has focus.
  Explicit visible-pointer button clicks no longer activate SynthScan; HUD body,
  hidden game cursor and mouse presses already in progress remain passive.
- Added destination-first Daylight planner to More and the tray menu, with arrival
  forecasts, sunrise/sunset and daylight windows for Stanton/Pyro surface POIs.
  Automatic public-data refresh, offline data, patch-aware local calibration and
  a labelled Orison reference for Siege are included.

# Changes

## 0.1.0-alpha.8 — 2026-11-02

- Make blueprint-list checkboxes toggle ownership directly and save through the
  existing manual-ownership path, without opening item details. Clicking the
  name still opens the recipe. Keep the list/scroll position and provide a more
  generous checkbox target with hover feedback.
- Add a window-free regression check against the production list hit targets,
  including scrolled rows, ownership callbacks and name-versus-checkbox routing.

## 0.1.0-alpha.7 — 2026-11-01

- Match the source tracker's 65-minute ONLINE countdown. The earlier closing
  countdown incorrectly targeted the 60-minute end of its green-light sequence.
  Preserve the final five-minute all-lights-off segment and use the website's
  minute/second formatting and rounding.

## 0.1.0-alpha.6 — 2026-11-01

- Give Executive Hangars its own compact activity-HUD tab, with five lights,
  an opening/closing countdown and a subtle complete-compboard-set total.
- Detect installed game-build changes and announced server resets through CIG's
  public status feed. Label unverified timing visibly; re-downloading unchanged
  timing cannot clear a build-change warning. Revised community timing is applied
  automatically without an application update.
- Refresh the public schedule/status data every ten minutes while Hangars is
  selected, or every two minutes while awaiting verification. Offline or stale
  verification is labeled; this is not a direct read of hangar availability.

## 0.1.0-alpha.5 — 2026-11-01

- Manual compboard inventory with seven saved quantities, +/− controls, typed
  counts, complete-set totals, atomic set deductions and undo of the last use.
- Show board quantities and complete sets on the passive Executive Hangar strip.
  Open inventory controls from the tray menu or Startup & HUD settings.

## 0.1.0-alpha.4 — 2026-11-01

- Optional shared PYAM Executive Hangar five-light timer under the server ribbon,
  with predicted charging/open/reset phases, countdowns, public-source resync
  and a passive display that does not consume gameplay input.
- Toggle the timer in Startup & HUD settings or the tray menu. It defaults off
  and uses the tracker’s published schedule, not a live hangar-availability feed.

## 0.1.0-alpha.3 — 2026-11-01

- Preserve the app when closing its HUD; recover from unexpected exits. App-wide
  hotkeys are disabled so they cannot collide with Star Citizen controls.
- Protect gameplay input: the HUD body passes clicks through and does not take
  focus. Small HUD +/− and docked − controls collapse/restore without activation.
  System minimize uses the same saved collapse state. Open SynthScan from the
  tray to use menus or reposition the overlay outside gameplay.
- Block interactive UI fixtures whenever Star Citizen is open.
- Improve detailed mining-panel recognition, including SynthStrings material
  abbreviations, mass-label font errors, volume number/unit separation, quality
  punctuation, overlapping instruments and stray digits from terrain.
- Show separate material/quality rows with potential raw SCU and modeled refined
  SCU. Public UEX feeds supply raw/refined estimates without an account or token.
  Player-value indications require matching, recent qualifying buy averages.
- Label near-complete OCR estimates with their actual coverage and omit the
  unread remainder. Unknown identities and larger gaps keep valuation pending.
- Refresh owned-blueprint text from native observations without replacing other
  localization changes. Serialize SynthStrings writes to preserve reputation and
  blueprint annotations together.

Mining recognition remains dependent on readable on-screen game text; not every
ship, pose, background or radiation signature has been validated. Values are
estimates of rock potential, not confirmed cargo or guaranteed sales. Server
population/FPS OCR still needs visible DisplayInfo. Reputation localization is a
verified-account snapshot loaded after a full game restart, not live game text.

The installer upgrades the app while preserving the local player profile. No
player profiles, credentials, game logs, extracted local reference caches or
private screenshots are distributed. Open-source notices and licenses remain.
