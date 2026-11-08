"""Compare native ore-location membership with locally extracted game presets."""
import argparse
import json
from pathlib import Path
import re

def audit(catalog,header):
    data=json.loads(Path(catalog).read_text(encoding='utf-8'))
    expected=set();all_parts={};provenance={}
    for location in data['locations']:
        if not location.get('curated_visible',True):continue
        provenance[location['name']]=location.get('curated_alias') or {'preset':location['preset'],'source':'Local game record; location label is curated'}
        for group in location['groups']:
            if group['weight']<=0:continue
            for deposit in group['deposits']:
                if deposit['weight']<=0 or not deposit.get('composition'):continue
                parts=data['compositions'][deposit['composition']]['parts']
                viable=[part for part in parts if part['probability']>0 and part['max_percent']>0]
                if not viable:continue
                main=max(viable,key=lambda part:part['max_percent'])['material'].replace('Aluminum','Aluminium')
                key=(location['name'],group['family'],main);expected.add(key)
                all_parts.setdefault(location['name'],set()).update(part['material'] for part in viable)
    compiled={(place,family,ore) for ore,family,place in re.findall(r'\{"([^"]+)", MiningFamily::(\w+), "([^"]+)"',Path(header).read_text(encoding='utf-8'))}
    compared=set(provenance)
    return dict(build=data['provenance']['build'],scope='Primary ore membership; omitted trace admixtures cannot establish absence',
        missing_native=sorted(expected-compiled),extra_native=sorted(row for row in compiled-expected if row[0] in compared),
        uncovered_native_locations=sorted({row[0] for row in compiled if row[0] not in compared}),
        terminus={name:dict(primary_ores=sorted(ore for place,family,ore in expected if place==name and family=='Ship'),
            all_materials=sorted(all_parts.get(name,[])),provenance=provenance[name]) for name in provenance if 'Terminus' in name})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--catalog',required=True);parser.add_argument('--header',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=audit(args.catalog,args.header);Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
