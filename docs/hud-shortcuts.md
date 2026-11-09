# HUD shortcuts

The Mining HUD reserves space for mining results and its controls. Server stats
are not repeated in its footer, and automatic fitting reclaims those two rows.
The optional session-strip setting applies to the Missions HUD.

Open Settings → HUD keyboard / mouse shortcuts. Enable the shortcuts, choose
whether they should work only with Star Citizen or its HUD focused, and save.
New installations leave shortcuts disabled until the player enables them.

Recommended keys:

| Action | App binding | G502 X assignment |
|---|---|---|
| Show / hide HUD | F23 | G8 → F23 |
| Next HUD tab | F24 | G7 → F24 |

G7/G8 are programmable Logitech controls, not portable Windows mouse-button
numbers. Assign single keyboard keys in G HUB, rather than repeating macros.
Ensure the profile includes LIVE/Bin64/StarCitizen.exe. A profile named after the
launcher is fine if the game executable is included as an additional path.
G HUB may label the button positions differently; use the mouse diagram and
verify which physical button sends each key. No application changes G HUB's
assignments or edits its database automatically.

Click an app shortcut field and press a new combination. Escape cancels recording;
Backspace or Delete clears that action. Use function keys or Ctrl/Alt combinations.
F12 is reserved by Windows. Toggle and cycle must use different keys. Shortcuts
suspend while recording; saving a shortcut does not activate its action.

Cycle order is Mining → Piracy → Missions → Hangars → Finder → Mining. Cycling
while the HUD is hidden changes the selected tab without opening it. Showing the
HUD preserves its position and does not bring up the full Home window. No game
commands or simulated game keystrokes are sent.

Implementation uses Windows RegisterHotKey with MOD_NOREPEAT, a short duplicate-
event guard, and foreground-change notifications. A 20 ms fallback checks only
the two configured keys and their modifiers while in scope, covering game input
paths that do not deliver Windows hotkey messages. It uses no keyboard hook.
Held keys trigger once; keys held when focus returns must be released first.
With game/HUD scope enabled, registrations are released and fallback checks stop
when another app is focused.
Conflicting registrations are reported in Settings; failed bindings do not run.
Close releases both registrations. Binding configuration is local to each player
in hud_hotkeys.json and is excluded from community packages.

The native status snapshot exposes registration status, Windows-message/fallback
counts and accepted action counts for troubleshooting. It records only these two
configured app actions, not typed
text or other keys. An actual mouse-button test remains a physical user action;
unit tests do not prove that a G HUB profile sends the expected hardware keys.

References:
- [Windows RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)
- [Logitech key assignments](https://www.logitechg.com/en-us/software/guides/keycontrol)
