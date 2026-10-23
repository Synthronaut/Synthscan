# SynthScan fork

Based on SC-Ravaxx/Bedrock commit 8fd809d84ff614d466447dd8b370cee86a7822ce,
declared upstream version 2.6.6. Copyright and GPL notices are preserved.

The Windows build keeps the complete original Application/MinerGUI, recognition,
tracking, hardware, blueprint, refinery, ore-planning and notebook code. Normal
UI identity and the icon are SynthScan. AppPaths defaults to
%LOCALAPPDATA%/SynthScan/native; SYNTHSCAN_DATA_DIR selects an isolated test profile.
No original app/account tokens or official update/sharing endpoints are shipped.

SynthScanShell provides the owned background bridge, session strip, visible
startup/HUD controls, tray, global HUD toggle, single-instance readiness/handoff,
and native workspace views of the extracted library, material picker and imports.
Its JSON protocol/parser and state handling are separate from the original
recognition code. Native display/capture stop on game-window absence. Headless
UI tests do not register system hotkeys or launch capture/bridge services.

The native bridge and lifecycle helpers are in the parent SynthScan workspace.
Build using tools/build_native_app.py. The original CMake file remains as an
upstream reference; use the SynthScan build script for this Windows fork.

The SDK compatibility shim exposes std::min/max for the installed older GDI+
headers. zstd is compiled locally with MSVC rather than linking the official
Windows archive's MinGW static library. Required notices ship with the binary.

Original tracked-file fingerprints: ../synthscan-upstream.json. Current source
and binary fingerprints: ../../dist/native/build_manifest.json.
