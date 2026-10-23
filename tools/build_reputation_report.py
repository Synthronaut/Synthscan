"""Render the verified own-account snapshot against build-stamped rank data."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_records import GameRecords
from native_control import DATA
from telemetry_ipc import read_shared_json


def main():
    snapshot=read_shared_json(DATA/'reputation_snapshot.json')
    if not snapshot.get('complete') or not snapshot.get('own_character_verified'):
        raise ValueError('No complete verified own-account snapshot')
    audit=json.loads((ROOT/'research/reputation_12913470/audit.json').read_text(encoding='utf-8'))
    store=GameRecords(ROOT/'research/reputation_12913470/records',ROOT/'research/local_game_12913470/localization/Data/Localization/english/global.ini')
    factions={}
    for path in (store.root/'libs/foundry/records/factions/factionreputation').glob('*.json'):
        value=store.read(path)['_RecordValue_']
        if value.get('GEID'):
            factions[str(value['GEID'])]=store.text(value.get('displayName'))
    scopes={s['name']:s for s in audit['scopes']}
    rows=[]
    for record in snapshot['records']:
        match=re.fullmatch(r'urn:sc:reputations:(?:org|npc):geid:(\d+)',record['entity'])
        organization=factions.get(match[1],record['entity']) if match else record['entity']
        scope=scopes.get(record['scope'])
        score=record['score']
        above=sorted([s for s in (scope or {}).get('standings',[]) if s['minimum']>score],key=lambda s:s['minimum'])
        target=above[0] if above else None
        standing=record['standing']['name']
        if scope:
            current=[s for s in scope['standings'] if s['minimum']<=score]
            # Prefer the live standing's minimum; gates can prevent promotion.
            exact=[s for s in current if s['minimum']==record['standing']['minimum']]
            if exact:standing=exact[-1]['name'] or standing
        next_text=f"{target['name'] or 'Next threshold'} ({target['minimum']:,})" if target else ('Top configured threshold' if scope else 'Unmapped track')
        remaining=f"{target['minimum']-score:,}" if target else '—'
        rows.append([organization,(scope or {}).get('display_name') or record['scope'],standing,f'{score:,}',next_text,remaining])
    rows.sort(key=lambda row:(row[0],row[1]))
    observed=datetime.fromtimestamp(snapshot['read_at'],timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    lines=['# Your reputation snapshot','',f'Read from the authenticated game reputation service at **{observed} Taipei (UTC+8)**. All {len(rows)} returned records matched your current character.','',
           'This is a saved observation, not a continuously updating display. Scores are service readings; next-rank requirements are local build 12913470 configuration. Additional gates can apply. Missing tracks are unknown, not zero.','',
           '| Organization | Track | Current standing | Current points | Next configured threshold | Points remaining |',
           '|---|---|---|---:|---|---:|']
    for row in rows:lines.append('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |')
    lines.extend(['','Party splitting does not change these observed balances. Attributing a change to a specific task still needs before/after observations and task context.',''])
    path=DATA/'reputation_report.md';path.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(path=str(path),records=len(rows),mapped=sum(bool(scopes.get(r['scope'])) for r in snapshot['records']))))


if __name__=='__main__':main()
