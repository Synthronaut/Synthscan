# Changes

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
