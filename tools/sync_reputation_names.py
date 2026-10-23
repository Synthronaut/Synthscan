"""Preview/apply organization-name snapshots while preserving all other strings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_control import DATA
from telemetry_ipc import read_shared_json, publish_json
from game_records import GameRecords
from reputation_strings import annotate_names

from installation import reference_paths
GAME=None


def sync(apply=False):
    paths=reference_paths();game=paths['game']
    snapshot=read_shared_json(DATA/'reputation_snapshot.json')
    if not 0<=time.time()-snapshot.get('read_at',0)<120:
        raise ValueError('Refresh reputation first; snapshot must be less than two minutes old')
    audit=json.loads(paths['audit'].read_text(encoding='utf-8'))
    manifest=json.loads((game/'build_manifest.id').read_text())
    if manifest['Data']['BuildId']!=audit['build']['BuildId']:
        raise ValueError('Game build changed; extract and review reputation definitions first')
    store=GameRecords(paths['records'],paths['localization'])
    factions={}
    for path in (store.root/'libs/foundry/records/factions/factionreputation').rglob('*.json'):
        value=store.read(path)['_RecordValue_']
        if value.get('GEID') and value.get('displayName'):
            kind='npc' if value.get('isNPC') else 'org'
            factions[f"urn:sc:reputations:{kind}:geid:{value['GEID']}"]=dict(key=value['displayName'])
    state_path=DATA/'reputation_localization_state.json'
    previous=read_shared_json(state_path,limit=1024*1024) if state_path.exists() else None
    ini=game/'Data/Localization/english/global.ini'
    before=ini.read_bytes()
    text,state=annotate_names(before.decode('utf-8'),snapshot,factions,{s['name']:s for s in audit['scopes']},previous)
    after=text.encode('utf-8')
    state.update(build_id=manifest['Data']['BuildId'],before_sha256=hashlib.sha256(before).hexdigest(),
                 after_sha256=hashlib.sha256(after).hexdigest(),phase='prepared',requires_game_text_reload=True)
    (DATA/'reputation_names_preview.json').write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8')
    if apply and after!=before:
        if previous and previous.get('after_sha256')==state['before_sha256'] and Path(previous.get('backup','')).is_file():
            state['backup']=previous['backup']
        else:
            backup=DATA/'localization_backups'/('reputation_names_'+time.strftime('%Y%m%d_%H%M%S'))
            backup.mkdir(parents=True,exist_ok=False)
            shutil.copy2(ini,backup/'global.ini')
            if previous:(backup/'previous_state.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
            state['backup']=str(backup/'global.ini')
        if not publish_json(state_path,state):raise OSError('Could not save restoration journal; game file unchanged')
        temporary=ini.with_name('global.ini.synthscan-reputation.tmp')
        try:
            temporary.write_bytes(after)
            if ini.read_bytes()!=before:raise ValueError('Localization changed concurrently; refusing replacement')
            temporary.replace(ini)
        finally:
            if temporary.exists():temporary.unlink()
        state['phase']='applied';publish_json(state_path,state)
    return dict(applied=bool(apply),changed=after!=before,names=len(state['entries']),
                          skipped=state['skipped'],requires_game_text_reload=True,
                          examples=[e['written'] for e in list(state['entries'].values())[:5]])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(sync(args.apply)))


if __name__=='__main__':main()
