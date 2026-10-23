"""Copy selected graphics configuration assets into research, without game changes.

Uses the archive reader already present from prior SynthScan research. No game
process access, archive writes, or changes to runtime restrictions are made.
"""
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import types
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from performance_lab import parse_cvar_group
OUTPUT = ROOT / 'research/performance/2026-10-20/packaged-graphics'
GAME = Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE')


def open_archive():
    dependency = Path(os.environ['TEMP']) / 'SynthScanDataTools'
    if not (dependency / 'scdatatools/p4k.py').is_file():
        raise FileNotFoundError('Previously prepared archive reader is unavailable; no dependency was installed.')
    sys.path.insert(0, str(dependency))
    package = types.ModuleType('scdatatools')
    package.__path__ = [str(dependency / 'scdatatools')]
    sys.modules['scdatatools'] = package
    utils = types.ModuleType('scdatatools.utils')
    utils.norm_path = lambda path: str(path).replace('\\', '/')
    def no_conversion(*args, **kwargs):
        raise NotImplementedError('Dictionary conversion is outside this inspector.')
    utils.etree_to_dict = no_conversion
    sys.modules['scdatatools.utils'] = utils
    from scdatatools.p4k import P4KFile, P4KInfo
    from scdatatools.engine.cryxml import is_cryxmlb_file, etree_from_cryxml_file

    def decode_extra(info):
        info.is_encrypted = len(info.extra) > 168 and info.extra[168] > 0
        cursor = 0
        while cursor + 4 <= len(info.extra):
            kind, size = struct.unpack_from('<HH', info.extra, cursor)
            cursor += 4
            if cursor + size > len(info.extra):
                if kind == 1:
                    raise zipfile.BadZipFile('Truncated ZIP64 metadata.')
                break
            if kind == 1:
                position = cursor
                for field in ('file_size', 'compress_size', 'header_offset'):
                    if getattr(info, field) in (0xffffffff, 0xffffffffffffffff):
                        if position + 8 > cursor + size:
                            raise zipfile.BadZipFile('Truncated ZIP64 size or offset.')
                        setattr(info, field, struct.unpack_from('<Q', info.extra, position)[0])
                        position += 8
                break
            cursor += size
    P4KInfo._decodeExtra = decode_extra
    original_endrec = zipfile._EndRecData
    def archive_endrec(stream):
        record = original_endrec(stream)
        if record and record[zipfile._ECD_SIGNATURE] == zipfile.stringEndArchive64:
            position = stream.tell()
            stream.seek(record[zipfile._ECD_OFFSET])
            signature = stream.read(4)
            stream.seek(position)
            if signature != zipfile.stringCentralDir:
                raise zipfile.BadZipFile('Declared P4K directory is invalid.')
            record[zipfile._ECD_LOCATION] = (record[zipfile._ECD_OFFSET] + record[zipfile._ECD_SIZE]
                + zipfile.sizeEndCentDir64 + zipfile.sizeEndCentDir64Locator)
        return record
    zipfile._EndRecData = archive_endrec
    try:
        archive = P4KFile(GAME / 'Data.p4k')
    finally:
        zipfile._EndRecData = original_endrec
    return archive


def main():
    archive = open_archive()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest, candidates = [], []
    with archive:
        for entry in archive.infolist():
            name = entry.filename
            if re.search(r'(?:graphicssettings|graphicoptions|optionsgraphics|systemspec|cvargroups)', name, re.I):
                candidates.append({'name': name, 'bytes': entry.file_size})
            if not (name.lower().startswith('engine/config/cvargroups/') and name.lower().endswith('.cfg')):
                continue
            if entry.file_size > 1_000_000:
                continue
            raw = archive.read(entry)
            stream = BytesIO(raw)
            if is_cryxmlb_file(stream):
                stream.seek(0)
                raw = ET.tostring(etree_from_cryxml_file(stream).getroot(), encoding='utf-8')
            output = OUTPUT / Path(name).name
            output.write_bytes(raw)
            manifest.append({'source': name, 'output': str(output), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    report = {'build': json.loads((GAME / 'build_manifest.id').read_text())['Data'],
              'copied': manifest, 'candidates': candidates, 'runtime_verified': False}
    (OUTPUT / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    groups = {Path(item['source']).stem: {
        'source': item['source'], 'sha256': item['sha256'],
        **parse_cvar_group(Path(item['output']).read_text(encoding='utf-8-sig'))}
        for item in manifest}
    (OUTPUT / 'decoded-groups.json').write_text(json.dumps({'build': report['build'], 'groups': groups}, indent=2), encoding='utf-8')
    print(json.dumps({'copied_assets': len(manifest), 'candidate_paths': len(candidates), 'output': str(OUTPUT)}))


if __name__ == '__main__':
    main()
