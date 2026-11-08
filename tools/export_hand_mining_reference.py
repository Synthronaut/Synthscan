"""Generate FPS/ROC scan-quality validation from a local StarBreaker export."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def export(records, manifest, destination):
    build=json.loads(Path(manifest).read_text(encoding='utf-8'))['Data']
    cached=json.loads((Path(records).parent/'source_manifest.json').read_text(encoding='utf-8'))
    cached=cached.get('Data',cached)
    if cached.get('BuildId')!=build.get('BuildId'):
        raise ValueError('Record cache and requested game build do not match')
    root=Path(__file__).resolve().parents[1]
    text=(root/'native/synthscan/include/MiningData.h').read_text(encoding='utf-8')
    names=set()
    for family in ('FPS_MINERALS','ROC_MINERALS'):
        block=re.search(family+r'\s*=\s*\{(.*?)\}',text,re.S)
        names.update(re.findall(r'"([^"]+)"',block[1]))
    rows=[];hashes={}
    for name in sorted(names):
        path=Path(records)/'libs/foundry/records/crafting/qualityquantization'/('quantization_'+name.lower()+'.json')
        raw=path.read_bytes();data=json.loads(raw)
        bands=[b['mappedValue'] for b in data['_RecordValue_']['qualityQuantization']['bands']]
        if len(bands)!=8 or any(not isinstance(v,int) or not 0<v<=1000 for v in bands):raise ValueError('Unsupported quality table: '+name)
        hashes[str(path.relative_to(records)).replace('\\','/')]=hashlib.sha256(raw).hexdigest()
        rows.append('    {"'+name+'", {'+', '.join(map(str,bands))+'}},')
    header='''#pragma once
// Generated from installed-game quality quantization by tools/export_hand_mining_reference.py.
// Reference build: %s. No inferred yield or piece counts.
#include "MiningHardware.h"
namespace SCMiner {
inline const OreBands HAND_MINING_BANDS[] = {
%s
};
inline constexpr int HAND_MINING_BANDS_COUNT = %d;
}
'''%(build.get('RequestedP4ChangeNum',build['BuildId']),'\n'.join(rows),len(rows))
    Path(destination).write_text(header,encoding='utf-8')
    return dict(build=build,records=hashes,materials=sorted(names))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--records',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--provenance',type=Path,required=True)
    a=p.parse_args();data=export(a.records,a.manifest,a.output)
    a.provenance.write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Generated quality validation for',len(data['materials']),'FPS/ROC minerals')
