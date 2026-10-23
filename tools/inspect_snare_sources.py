"""Inspect installed snare assets and executable strings without game input/access."""
import json,re,hashlib,sys,time
from pathlib import Path
from io import BytesIO
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.inspect_graphics_assets import open_archive,GAME
OUT=ROOT/'research/snare_independent_sources';OUT.mkdir(exist_ok=True)

def main():
    report=dict(at=time.time(),candidates=[],extracted=[],executable_strings=[])
    with open_archive() as archive:
        for entry in archive.infolist():
            name=entry.filename
            if re.search(r'(?:wpqe|qed[_/\\.]|snare|quantum.?interdict|quantum.?enforce)',name,re.I):
                report['candidates'].append(dict(path=name,bytes=entry.file_size))
                if entry.file_size<4_000_000 and Path(name).suffix.lower() in ['.xml','.json','.txt','.lua','.cfg']:
                    raw=archive.read(entry)
                    from scdatatools.engine.cryxml import is_cryxmlb_file,etree_from_cryxml_file
                    stream=BytesIO(raw)
                    if is_cryxmlb_file(stream):
                        stream.seek(0);raw=ET.tostring(etree_from_cryxml_file(stream).getroot(),encoding='utf-8')
                    dest=OUT/(hashlib.sha256(name.encode()).hexdigest()[:12]+'_'+Path(name.replace('\\','/')).name)
                    dest.write_bytes(raw);report['extracted'].append(dict(source=name,output=str(dest.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest()))
        report['archive_entries_checked']=len(archive.infolist())
    raw=(GAME/'Bin64/StarCitizen.exe').read_bytes()
    for m in re.finditer(rb'[\x20-\x7e]{5,600}',raw):
        if re.search(rb'snare|interdict|qed|tethering',m[0],re.I):report['executable_strings'].append(dict(offset=m.start(),text=m[0].decode()))
    report['executable_sha256']=hashlib.sha256(raw).hexdigest()
    (OUT/'inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(candidates=len(report['candidates']),extracted=len(report['extracted']),executable_strings=len(report['executable_strings']))))

if __name__=='__main__':main()
