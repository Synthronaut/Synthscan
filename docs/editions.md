# One installer, two internal engines

New users download **SynthScan-Setup-Windows-x64.exe**. All feature checkboxes start selected. Uncheck **Live Mining Recognition [SCREEN READING]** to install the screen-free engine. Server HUD, hangars, reputation, blueprints and piracy do not need OCR.

Standard and Full are internal build identities. Standard does not compile Windows Graphics Capture or desktop duplication providers and installs no OCR models, ONNX runtime, capture packages or mining OCR worker. The recognition pack supplies the Full engine and reader dependencies together; editing a preference cannot add missing files.

Shared native presentation, game-data infrastructure and drawing utilities remain in Core. Small native-only packs are capability declarations, not separate DLLs. Optional Python providers and resources are separately packaged. This is not an OS sandbox or a claim that every shared algorithm disappears when a checkbox is cleared.

Existing Standard and Full update channels preserve their screen-reading choices when migrating to the modular product. The unified installer upgrades the former Full installation identity. Legacy Standard has a separate install directory and registration; uninstall it before a fresh unified installation. Player records stay in AppData. Do not run two installations at once.

Build both engines from the same source with `tools/build_native_app.py`. Split matched verified packages with `tools/package_modules.py` and compile the unified installer with `tools/build_modular_installer.py`. See [module guide](modules.md).
