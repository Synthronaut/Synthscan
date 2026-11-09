# Desktop page sizing audit

Server history used fixed 820×155 logical-pixel table dimensions, leaving a large
empty area in a tall desktop window. Its filters, details and actions now follow
the page's actual client size. The history table gets most additional height;
notes and shard actions remain below it. Columns use extra width, and the filter
labels are below the cropped legacy toolbar rather than partly hidden by it.

| Sidebar page | Audit result |
| --- | --- |
| Home | Existing responsive tiles and sidebar spacing. |
| Mining | Existing client-size layout and constrained HUD placement. |
| Item & ship finder | Existing adaptive list/details layout; its material/review variants now also call that layout on resize. |
| Blueprint library | Existing client-size drawing and internal scrolling. |
| Refinery | Existing client-size drawing and scrollable order content. |
| Mining planner | Existing client-size list/detail drawing. |
| People | Existing responsive native controls; selection and scroll retained. Fixed recipient confirmation being mistaken for another embedded page. |
| Buyer alerts | Existing responsive controls and independently scrollable lists. |
| Piracy | Short settings/summary form fits its minimum page; host scrolling remains available below that size. |
| Server history | Fixed: full-width filters and table, growing history area, anchored details/notes/actions. |
| Mining diary | Fixed: both columns use spare width; entry list and story editor use spare height; lower actions stay accessible. |
| Personal notes | Existing client-size rich text editor/tree layout. |
| Rock bookmarks | Fixed: growing bookmark/details panes and anchored capture/export actions. |
| Daylight | Existing weighted grid and embedded-window resizing. |
| Automatic acceptance | Short settings form fits its minimum page. |
| Settings and shortcuts | Short forms fit their minimum page; large-window whitespace is intentional. |
| Privacy & capture | Separate migration owns this page; existing controls use client width. No capture-policy or preview behavior changed by this audit. |

Resizing moves existing controls, preserving their text, selection and checkbox
states. Fonts retain their readable DPI-scaled size. Complex editors retain a
minimum usable size and use the existing page-host scrollbars in smaller windows.

Validation uses synthetic native pages under a hidden parent at compact, normal
and large sizes, with 125% display scaling on the test machine. It checks actual
control bounds, growth, selected records and unsaved editor text, and renders PNG
previews. No game images, game input, social requests or real records are used by
the fixture. The native self-test also checks the layout calculations independently.

## 9 November: live repaint regression

The earlier hidden-parent bitmap checks did not exercise normal Windows paint
dispatch. A visible People page inside a `WS_EX_COMPOSITED` ancestor could enter
a synchronous repaint loop and block the entire app's UI thread. A synthetic
fixture reproduced more than 57,000 window messages before its hard timeout.

Removed whole-tree compositing from Home; individual buffered controls retain
their existing appearance. People paint handlers release GDI+ graphics before
`EndPaint`, unchanged labels no longer trigger text redraws, and selection walks
are bounded even if their control is missing during teardown.

`tools/verify_companion_responsiveness.py` now exercises the actual Home window,
People and buyer pages with 400 synthetic records, native message dispatch,
repeated navigation, resizing and service heartbeats. All windows live on a
separate desktop that is never displayed. No game input, screen capture, account
requests or real player records are used. The process runs below normal priority,
on one CPU, with a hard timeout. It also repeats the existing selection, scroll
and action-routing fixtures. This check is a modular-release gate.

At the local display's 125% scaling, the repaired fixture completed eight seconds
with 12 service heartbeats, 572 paints and a longest dispatched message of 32 ms.
The foreground remained unchanged; the existing People interaction checks passed.
This verifies the reproduced UI fault, not unrelated hardware crashes or every
possible live-game state.

The repaired native executable was installed locally after 517 native self-tests
and 20 People interaction checks passed. The previous executable and manifest
were retained in a local backup. A 35-second observation of the normal app kept
a fresh UI heartbeat throughout (about 0.02 seconds old at the last sample) and
used 1.25 CPU seconds in total, including startup. No profile or game files were
replaced to install this repair. Public release validation is still pending.
