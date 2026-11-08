# Privacy verification and release review

## Local validation, 2026-11-08

The development build passed 512 native headless checks and 729 Python tests
(23 GUI/private-fixture skips). A live 640 × 400 game-window capture probe returned
70/70 nonblank frames: median 1.53 ms, 95th percentile 5.05 ms. It rejected desktop
targets and zero-filled off-game crop areas without saving images. This is a
capture-path measurement on one SDR machine, not a full scan-latency or HDR-hardware
qualification.

Two separately compiled local builds produced the same unsigned SynthScan.exe:
`ba84ccd8f6b84657be1cd87984a9db5bb7663ea29f1539580d931f9c7100de97`.
This is local repeatability evidence, not an independent audit or a cross-machine
reproduction. It does not identify an older public installer. A new distribution
must carry its own corresponding hashes and validation report.

## Implemented capture boundary

Windows native capture uses Windows Graphics Capture with CreateForWindow.
The target must be a visible CryENGINE window belonging to StarCitizen.exe.
Neither the desktop nor a monitor can be selected as its target. Screen-coordinate
crops are taken from that window's surface; portions outside its client area are
zero-filled. Window movement, closure, resizing and stale frames invalidate the
reading. Windows' capture indicator is retained. No renderer injection is used.

The Python capture compatibility path also uses a window-specific WGC session.
Its former MSS/PIL desktop fallbacks are removed. The older mining helper rejects
direct live capture; its client supplies window images through bounded shared
memory, not temporary PNG files. Manual image imports remain explicit actions.

Privacy & capture is an ordinary embedded page, not a popup. It provides pause,
automatic pause on focus loss, an in-memory game preview, clear preview, and an
explicit Save action. Save is the only image-writing action on that page.
Account-service permission is separate and checked before credential loading
and before service calls. New profiles require opt-in. A request already in flight
when permission is revoked may finish; revocation prevents subsequent calls.

Community native builds ignore legacy recording settings and do not automatically
write OCR/debug screenshots. Explicit developer builds and manually invoked
capture/export commands must be distinguished from normal screen reading.
Existing local screenshots are not silently deleted. Profile files remain
protected by the Windows account, not separately encrypted.

## Evidence to publish with a release

- Exact source commit, build manifest and SHA-256 digests for actual artifacts.
- Native selftest and Python test results, with skipped fixtures disclosed.
- Real game capture checks for successful/nonblank frames, off-game zero padding,
  invalid target rejection and capture latency. Never include captured pixels
  or OCR text in the public performance report.
- Two independently compiled unsigned builds compared by
  `tools/verify_reproducible.py`. This is repeatability evidence, not an audit.
- Windows publisher signature when an appropriate signing identity is supplied.
  `tools/sign_windows_release.ps1` uses an installed code-signing certificate;
  it never exports a private key. Signing changes the binary digest, so publish
  separate unsigned/reproducible and signed/distributed hashes.
  Keep the unsigned build outside the package, sign the staging binaries, then
  generate package integrity/update manifests. Signing refreshes matching native
  binary hashes so runtime integrity checks continue to work. This script needs
  PowerShell 7. The unsigned CI attestation does not attest a subsequently changed
  signed file; final signed artifacts need their own provenance evidence.
- CI provenance from the manually dispatched Verify native release provenance
  workflow. GitHub attestation identifies the build/source relationship; it is
  separate from Authenticode, code review and an assurance that code is harmless.

Build paths are normalized and MSVC deterministic compilation/linking is enabled.
Matching compiler, SDK, inputs and build instructions are required. Runtime path
files and personal settings are intentionally outside binary comparison. Do not
claim cross-machine reproducibility until another machine reproduces the build.

## Independent reviewer checklist

Review these paths and their callers: ScreenCapture.*, SynthGameCapture.cpp,
SynthCapturePrivacy.h, SynthPrivacy.cpp, capture_privacy.py,
window_telemetry_capture.py, detector.py, native_mining.py, the mining worker,
SynthFrameTransfer.h, native_bridge.py, game_account.py, player_services.py,
Updater.cpp, update verification, and tools/package_community.py.

1. Attempt browser/desktop/launcher targets; none may yield automatic pixels.
2. Cover the game with another application and move it between monitors. WGC
   must keep reading only the game surface or return unavailable, never desktop.
3. Pause, minimize, close, change session, and return while holding a shortcut.
   Check frame expiry, bounded memory and absence of unintended key actions.
4. Watch disk writes during normal scans and terminal recognition. No screenshot
   file may appear. Explicit Save must write only the previewed game image.
5. Revoke account permission. New account requests and credential loading must
   stop. Check that logs, exceptions, support bundles and exports contain no tokens.
6. Inspect network destinations and call paths. No implemented OCR path should
   upload a captured image. Verify optional UEX reporting and social actions
   separately: they do transmit explicitly requested structured data.
7. Test signed-update verification, rollback, archive paths, source packaging,
   artifact digests and publisher identity. A valid update signature does not
   prove that the updated code preserves privacy.

Record findings, tool versions, tested commit/hash and limitations. Report
vulnerabilities privately through the repository's security reporting channel.
There has been no independent privacy audit merely because this checklist exists.

## Outstanding isolation and external release requirements

The normal application and OCR readers are not yet an OS-enforced offline
sandbox. An experimental zero-network-capability AppContainer worker failed its
startup checks on the development machine and was excluded from production.
Keeping it would have disabled working readers, contrary to the no-regression
requirement. Do not label the current release "network-isolated OCR".

Completing that boundary requires moving all active native/Python recognition
paths behind a compatible offline worker, validating its IPC and lifecycle, and
measuring parity on the real mining, loadout and terminal fixtures. The current
window boundary and absence of image-upload calls are useful protections, but
are not equivalent to OS network denial.

The public CI build and provenance workflow has passed for the initial privacy
hardening commit 7a4b466:
https://github.com/Synthronaut/Synthscan/actions/runs/42490813289
Each later release needs evidence for its own commit and artifact.

An independent reviewer and a trusted publisher signing identity remain external
release requirements. Neither is manufactured by local selftests, CI provenance
or this document. Do not advertise them as completed without the corresponding
report and certificate.

Primary references:
- https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nf-windows-graphics-capture-interop-igraphicscaptureiteminterop-createforwindow
- https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture
- https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
- https://reproducible-builds.org/docs/definition/
