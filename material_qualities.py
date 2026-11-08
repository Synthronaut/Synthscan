"""Material-specific quality quantization from linked local game records."""
import hashlib
import json
from pathlib import Path
import re

def normalized(name):
    name=re.sub(r'\s*\((?:ore|raw)\)$','',str(name),flags=re.I)
    name=re.sub(r'^raw\s+','',name,flags=re.I)
    return re.sub('[^a-z0-9]','',name.lower()).replace('aluminium','aluminum').replace('quantanium','quantainium')

def export(store,manifest):
    entries={};folder=store.root/'libs/foundry/records/crafting/qualityquantization'
    for path in sorted(folder.glob('*.json')):
        if path.stem.lower().endswith('_template'):continue
        record=store.read(path);bands=record['_RecordValue_']['qualityQuantization']['bands'];last=-1;values=[]
        for band in bands:
            start,end,value=(band[key] for key in ('start','end','mappedValue'))
            if any(not isinstance(v,int) or isinstance(v,bool) for v in (start,end,value)) or start!=last+1 or not start<=end<=1000 or not 0<=value<=1000:raise ValueError('Invalid game quality quantization: '+path.name)
            last=end;values.append(value)
        if last!=1000 or not values:raise ValueError('Incomplete game quality quantization: '+path.name)
        raw_name=record['_RecordName_'].split('Quantization_',1)[-1]
        entries[path.resolve()]=dict(name=raw_name,aliases=[raw_name],values=sorted(set(values)),
            bands=[dict(start=b['start'],end=b['end'],value=b['mappedValue']) for b in bands],resource_ids=[],source=str(path.relative_to(store.root)).replace('\\','/'),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for resource in store.resources.values():
        for prop in resource.get('properties',[]):
            if not isinstance(prop,dict):continue
            reference=(prop.get('qualityQuantization') or {}).get('qualityQuantizationRecord')
            if not reference:continue
            row=entries.get(store.reference_path(reference).resolve())
            if row is None:continue
            raw=store.text(resource.get('displayName'),resource['_RecordName_'].split('.',1)[-1])
            refined=store.resource_name(resource,refined=True)
            row['name']=refined or raw;row['aliases']+=list(dict.fromkeys([raw,refined]));row['resource_ids'].append(resource['_RecordId_'])
    result=list(entries.values())
    for row in result:row['aliases']=sorted(set(row['aliases']+[row['name']]))
    return dict(schema=1,build=manifest['Data'],source='Installed Game2.dcb quality quantization; localized through ResourceType links',materials=sorted(result,key=lambda row:row['name'].casefold()))

def lookup(reference,name):
    key=normalized(name);matches=[r for r in reference.get('materials',[]) if any(normalized(alias)==key for alias in r['aliases'])]
    if not matches or any(r['values']!=matches[0]['values'] for r in matches):return None
    return matches[0]

def bundled():
    return json.loads((Path(__file__).resolve().parent/'data/material_qualities.json').read_text(encoding='utf-8'))

def write_chart(reference,path):
    lines=['# Material quality values', '', 'Game build: '+str(reference['build'].get('Branch'))+' / '+str(reference['build'].get('RequestedP4ChangeNum')), '',
        'These are mapped output values from the game’s quality-quantization records, not a value for every hundred. Not every material or quality is available at every location.', '',
        '| Material | Fixed quality values |','|---|---|']
    lines += ['| '+row['name']+' | '+', '.join(str(v) for v in row['values'])+' |' for row in reference['materials']]
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')
