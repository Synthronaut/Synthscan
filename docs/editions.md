# Standard and Full editions

Choose **Standard — no screen reading** if you do not want screen capture installed.
Choose **Full — local game-window screen reading** for automatic mining recognition
and screen-based readings/imports. These are separately built Windows installers,
not an enable/disable checkbox in the same binary.

| Capability | Standard | Full |
| --- | --- | --- |
| Item/ship Finder, shops, player-market estimates and blueprints | Yes | Yes |
| People, reputation, mission and blueprint log tracking | Yes | Yes |
| Server identity/history and available log/network/frame metrics | Yes | Yes |
| Hangar countdowns, daylight planning, notes and manual records | Yes | Yes |
| Mining planning, loadout information and saved mining diary | Yes | Yes |
| Automatic notification acceptance from game logs | Yes | Yes |
| Live mining signature/composition/quality recognition | Not installed | Yes |
| DisplayInfo screen-derived population/server metrics | Not installed | Yes |
| Screen-based fabricator/refinery/image imports | Not installed | Yes |

Standard does not compile the Windows Graphics Capture or desktop-duplication
providers. Their linked replacements return no images. It installs no
windows-capture, MSS, Pillow screen grabber, RapidOCR, ONNX Runtime, recognition
models or mining OCR worker. General image/UI utilities in the native program
remain shared; that is not a claim that every image-processing algorithm or
Windows drawing API has been removed. No screenshot upload is added.

The native binary reports Standard and cannot be upgraded to capture by editing
preferences. Standard's Privacy page preserves separate account permission and
explains the missing capability. A few shared/manual pages remain available,
with automatic readings unavailable; they do not fabricate missing measurements.

Each ZIP has an edition in release.json and each native build manifest records
its compiled edition. Packaging rejects a mismatched binary and audits Standard
for forbidden components. Signed application manifests and their archives must
agree on edition. Both download staging and activation reject cross-edition
updates. Legacy installations without an edition are treated as Full. The
Standard channel uses synthscan-update-standard.json; Full retains the original
synthscan-update.json channel for existing users.

To change editions, explicitly download the other installer. Standard has a
separate application ID/install directory, so it cannot accidentally reuse a
Full runtime or version pointer. Uninstall Full when moving to Standard if you
want its capture files removed from your computer; personal data lives separately
and is retained. Do not run both editions together. Existing Full users are not
silently moved to Standard.

Build with SYNTHSCAN_EDITION=standard (or full) using tools/build_native_app.py.
Package with tools/package_community.py --edition standard (or full), matching
--native to that build. tools/build_installer.py selects the appropriate installer
identity from the payload metadata. CI builds/tests/packages both editions and
only promotes their signed channels after both succeed.
