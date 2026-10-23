# Building the Windows release

Windows x64, CPython 3.14, Visual Studio C++ Build Tools and Windows SDK are needed
only on the build machine. Users download the complete release ZIP.

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
the resulting ZIP/checksum as workflow artifacts. Publication to Releases is a
separate deliberate step. Never upload the development folder directly.

Corresponding modified GPL application source is `native/synthscan`; the earlier
worker's source is `native/mining_worker`. Original copyright and component
licenses remain in source and in downloadable builds. Game data is extracted from
the recipient's own installation during setup.
