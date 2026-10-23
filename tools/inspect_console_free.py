"""Read-only inventory of console-free telemetry candidates in installed assets.

Never attaches to the game, sends input/network commands, or changes game files.
Only selected diagnostic/config assets are copied into the research directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import types
import zipfile
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "research" / "console_free"
    output.mkdir(parents=True, exist_ok=True)
    game = Path(r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE")
    if args.assets:
        dependency_root = Path(os.environ["TEMP"]) / "SynthScanDataTools"
        sys.path.insert(0, str(dependency_root))
        # Load the archive/XML readers without importing the library's Blender,
        # audio, launcher and model-conversion dependency tree.
        package = types.ModuleType("scdatatools")
        package.__path__ = [str(dependency_root / "scdatatools")]
        sys.modules["scdatatools"] = package
        utils = types.ModuleType("scdatatools.utils")
        utils.norm_path = lambda path: str(path).replace("\\", "/")
        def unsupported_conversion(*args, **kwargs):
            raise NotImplementedError("Dictionary conversion is outside this inspector")
        utils.etree_to_dict = unsupported_conversion
        sys.modules["scdatatools.utils"] = utils
        from scdatatools.p4k import P4KFile, P4KInfo
        from scdatatools.engine.cryxml import is_cryxmlb_file, etree_from_cryxml_file
        from io import BytesIO
        from xml.etree import ElementTree
        def decode_extra(info):
            info.is_encrypted = len(info.extra) > 168 and info.extra[168] > 0
            cursor = 0
            while cursor + 4 <= len(info.extra):
                kind, size = struct.unpack_from("<HH", info.extra, cursor)
                cursor += 4
                if cursor + size > len(info.extra):
                    if kind == 1:
                        raise zipfile.BadZipFile(f"Truncated ZIP64 extra field: {info.filename}, {cursor}, {size}, {len(info.extra)}")
                    break  # CIG metadata after the ZIP64 fields is not a ZIP TLV.
                if kind == 1:
                    position = cursor
                    for field in ("file_size", "compress_size", "header_offset"):
                        if getattr(info, field) in (0xffffffff, 0xffffffffffffffff):
                            if position + 8 > cursor + size:
                                raise zipfile.BadZipFile("Truncated ZIP64 size/offset")
                            setattr(info, field, struct.unpack_from("<Q", info.extra, position)[0])
                            position += 8
                    break  # Remaining extra bytes are CIG metadata, not ZIP TLVs.
                cursor += size
        P4KInfo._decodeExtra = decode_extra
        # This CIG archive has a signature trailer after the central directory.
        # scdatatools 1.0.4 mistakes that trailer for a concatenated ZIP prefix.
        # Trust the declared directory offset only after checking its signature.
        original_endrec = zipfile._EndRecData
        def p4k_endrec(stream):
            record = original_endrec(stream)
            if record and record[zipfile._ECD_SIGNATURE] == zipfile.stringEndArchive64:
                position = stream.tell()
                stream.seek(record[zipfile._ECD_OFFSET])
                signature = stream.read(4)
                stream.seek(position)
                if signature != zipfile.stringCentralDir:
                    raise zipfile.BadZipFile("Declared P4K central directory is invalid")
                record[zipfile._ECD_LOCATION] = (record[zipfile._ECD_OFFSET] + record[zipfile._ECD_SIZE]
                    + zipfile.sizeEndCentDir64 + zipfile.sizeEndCentDir64Locator)
            return record
        zipfile._EndRecData = p4k_endrec
        try:
            archive = P4KFile(game / "Data.p4k")
        finally:
            zipfile._EndRecData = original_endrec
        with archive:
            candidates = []
            extracted = []
            for entry in archive.infolist():
                name = entry.filename
                if re.search(r"(?:actionmaps|defaultprofile|defaultactions|cvar|remoteconsole|consolecommand|whitelist|autoexec|keybind|inputmap)", name, re.I):
                    candidates.append({"name": name, "size": entry.file_size})
                if (re.search(r"(?:^|/)(?:defaultprofile|actionmaps|CvarsCommandsDebugItems[^/]*|defaultactions)\.(?:xml|cfg)$", name, re.I)
                        or re.search(r"(?:^|/)(?:console|remoteconsole|autoexec|system)\.cfg$", name, re.I)):
                    if entry.file_size > 4_000_000:
                        continue
                    raw = archive.read(entry)
                    stream = BytesIO(raw)
                    if is_cryxmlb_file(stream):
                        stream.seek(0)
                        raw = ElementTree.tostring(etree_from_cryxml_file(stream).getroot(), encoding="utf-8")
                    path = output / name.replace("/", "__").replace("\\", "__")
                    path.write_bytes(raw)
                    extracted.append({"name": name, "output": str(path), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            report = {"entries_checked": len(archive.infolist()), "candidates": candidates, "extracted": extracted}
        (output / "asset_inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"entries_checked": report["entries_checked"], "candidates": len(candidates), "extracted": extracted}))
    else:
        data = (game / "Bin64" / "StarCitizen.exe").read_bytes()
        pattern = re.compile(rb"(?:displayinfo|display_info|keybind|binds\.cfg|remote.?console|\brcon\b|console.?bind|con_(?:restricted|show|hide|debug)|load.?config|load.?cvar|reload.?config)", re.I)
        strings = [{"offset": hex(m.start()), "text": m[0][:-1].decode("ascii")}
                   for m in re.finditer(rb"[\x20-\x7e]{4,500}\x00", data) if pattern.search(m[0])]
        report = {"exe_sha256": hashlib.sha256(data).hexdigest(), "strings": strings}
        (output / "executable_strings.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"strings": len(strings), "report": str(output / "executable_strings.json")}, indent=2))


if __name__ == "__main__":
    main()
