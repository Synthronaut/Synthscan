# Third-party licenses and data sources

SynthScan is an independent Star Citizen companion. Its product name and HUD
are SynthScan's; credits below identify the actual sources of reused material.

- SC-Ravaxx/Bedrock: https://github.com/SC-Ravaxx/Bedrock
  The full native SynthScan application is a modified GPL-3.0-or-later fork of
  commit 8fd809d84ff614d466447dd8b370cee86a7822ce. Its source is native/synthscan/;
  original tracked-file hashes are in native/synthscan-upstream.json. The new
  lifecycle/workspace layer is SynthScanShell.cpp; the original native mining,
  tracking, blueprint and refinery application remains the foundation. GPL,
  authorship and third-party notices accompany dist/native/. This fork has its
  own data directory and ships no upstream service/account tokens.
  Copyright (C) 2026 Ravaxx. The adapted OCR preprocessing/CTC implementation in
  textline_ocr.py is GPL-3.0-or-later. The native mining worker also compiles its
  original glyph/neural readers, marker locator, rock/composition/loadout and
  refinery readers, signature analyzer and mining calculations. Unmodified
  sources and their pinned commit/file hashes are in native/mining_worker/vendor/;
  SynthScan's IPC and scheduling adapters are in native/mining_worker/.
  Build provenance and license copies accompany third_party/mining_core/.
  Original notices and the license for the earlier Python integration are in
  third_party/bedrock/NOTICE.txt and third_party/bedrock/LICENSE. Imported
  reference tables preserve their exact upstream commit, URL and hash in data/.
- The PP-OCRv4 model is from PaddleOCR (Apache-2.0) through gutenye/ocr-models
  (MIT), with fixed input dimensions. Notices accompany the model under
  third_party/bedrock/textline/.
- StarBreaker v0.3.2: https://github.com/diogotr7/StarBreaker (MIT).
  Its license and pinned download provenance are in third_party/starbreaker/.
- PresentMon v2.6.0: https://github.com/GameTechDev/PresentMon (MIT).
  The standalone application presentation timing helper, license and verified
  upstream release hash are in third_party/presentmon/. It is optional and is
  started only when the user requests the timing/network helper.
- The Windows installer is built with unmodified Inno Setup 7.1.0, by Jordan
  Russell and Martijn Laan: https://jrsoftware.org/. Its compiler is a build-only
  dependency downloaded from a pinned official release with SHA-256 verification.
- Game records, descriptions, artwork and test screenshots depict or describe
  Star Citizen content belonging to Cloud Imperium Games. Local extraction
  metadata distinguishes native records from imported reference annotations.
- Mining destination labels and explicit community aliases retain their SCMDB
  attribution and build/version under data/; mining preset numbers are extracted
  independently from the installed game.
- SVG rasterization uses resvg-py; its license is in third_party/game_artwork/.
- The native worker uses the official OpenCV 4.12.0 Windows SDK (Apache-2.0).
  Its license is third_party/mining_core/LICENSE-OpenCV; download URL and verified
  release digest are recorded in the worker's build_manifest.json.
- The full native application statically compiles zstd 1.5.7 from the official
  facebook/zstd source release. Its BSD license is dist/native/LICENSE-zstd;
  source download URL/hash is recorded in the native build manifest.

Historical research reports retain source names so their findings are auditable.
Renaming the product does not remove original authors' copyright notices or
change the licenses of reused components.
