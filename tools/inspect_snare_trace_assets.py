import sys,re,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tools.inspect_graphics_assets import open_archive
out=Path('research/snare_independent_sources');entries=[]
with open_archive() as archive:
 for e in archive.infolist():
  if re.search('trace.?filter|cigtrace|engineconfig|engine_config',e.filename,re.I):
   row=dict(path=e.filename,size=e.file_size);entries.append(row)
   if e.file_size<2_000_000 and Path(e.filename).suffix.lower() in ['.json','.xml','.ini','.cfg']:
    target=out/('trace_'+Path(e.filename.replace('\\','/')).name);target.write_bytes(archive.read(e));row['copied']=str(target)
(out/'trace_asset_inventory.json').write_text(json.dumps(entries,indent=2),encoding='utf-8');print(json.dumps(entries))
