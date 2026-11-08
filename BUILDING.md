# Building the Windows release

For a public-source native build, run `python -B tools/fetch_native_build_inputs.py`
to download hash-pinned OpenCV and zstd inputs (7-Zip and tar must be installed).
The compiler, SDK and pinned inputs must match when comparing builds. The builder
normalizes source paths and requests deterministic compiler/linker output.
Compile into separate object/output directories, then run
`python -B tools/verify_reproducible.py FIRST_OUTPUT SECOND_OUTPUT --report reproducibility.json`.
Personal runtime paths/settings are excluded from the binary comparison.
The manually dispatched Verify native release provenance workflow performs this
comparison and native headless checks before issuing an executable attestation.
It does not publish an installer, sign a Windows publisher identity, or constitute
an independent security audit. See `docs/privacy-review.md` for the release gates.

Windows x64, CPython 3.14, Visual Studio C++ Build Tools and Windows SDK are needed
only on the build machine. Users normally download the guided Windows installer;
the complete release ZIP is an alternative.

1. Install MSVC C++ Build Tools (2019 or newer), Windows 10/11 SDK and Python 3.14
   with Tcl/Tk. `SYNTHSCAN_MSVC` can select a VC/Tools/MSVC version folder;
   `SYNTHSCAN_SDK` can select the Windows Kits/10 folder.
2. Run `python tools/fetch_build_dependencies.py`. It verifies the pinned upstream
   OpenCV and zstd archives before extracting them. StarBreaker and its MIT license
   are included in source with pinned provenance.
3. Run `python -m pip install --require-hashes -r requirements-release.lock`.
4. Run `python -B tools/build_native_app.py`. Set `SYNTHSCAN_BUILD_OUT` to choose
   another output folder.
5. Run `python -B -m unittest discover -s tests -q`. Private game-capture fixtures
   and the historical optional mining worker are deliberately excluded; their
   tests skip when unavailable. No tests should require a real account.
6. Run `python -B tools/package_community.py --source out/public-source
   --package out/SynthScan-Windows-x64 --native dist/native`. Use fresh output
   directories. It bundles a clean Python runtime, hash-pinned wheels, native app,
   OCR resources, app source, licenses, launcher and integrity manifest.

The `Windows community build` workflow performs these steps on demand and uploads
the resulting ZIP/checksum and guided installer as workflow artifacts. Build the
installer locally with `python tools/build_installer.py --payload out/SynthScan-Windows-x64 --output out/installer`.
The Inno Setup compiler is downloaded from its pinned official release and hash-checked.
To sign the ZIP, run `python tools/sign_release.py --archive out/SynthScan-Windows-x64.zip
--url https://github.com/Synthronaut/Synthscan/releases/download/v0.1.0-alpha.9/SynthScan-Windows-x64.zip
--output out/synthscan-update.json`. Local signing uses the protected release key;
CI uses the matching `SYNTHSCAN_SIGNING_PRIVATE_B64` secret. A different signing key
will be rejected. Build artifacts remain usable without signing, but cannot be
promoted to the automatic update channel.

Publication is a separate deliberate step: the workflow's `publish` input defaults
to false. Configure the protected `community-release` environment before enabling
publication. It creates an immutable versioned release, then promotes the signed
manifest at `update-channel`. Never upload the development folder directly.

Corresponding modified GPL application source is `native/synthscan`; the earlier
worker's source is `native/mining_worker`. Original copyright and component
licenses remain in source and in downloadable builds. Game data is extracted from
the recipient's own installation during setup.

Interactive HUD/window fixtures must only run while Star Citizen is closed.
The native --ui-test entry point refuses to run when the game window is present.
