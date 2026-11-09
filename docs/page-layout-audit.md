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
