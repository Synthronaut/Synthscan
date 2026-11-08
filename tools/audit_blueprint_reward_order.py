"""Recover observed reward chronology without treating it as a universal sequence.

Reads SynthScan's saved notification/contract evidence and an extracted build.
Does not change ownership, localization, or the running application.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blueprint_strings import item_key
from game_records import walk_nodes


def grants(text):
    """Only queue additions are grants; fades and queue dumps are duplicates."""
    found = {}
    pattern = re.compile(r'^<([^>]+)>.*<SHUDEvent_OnNotification> Added notification "Received Blueprint: (.*?): "')
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            stamp, name = match.groups()
            found[(stamp, name)] = dict(at=stamp.rstrip('Z'), name=name.strip())
    return sorted(found.values(), key=lambda row: row['at'])


def completions(text, version):
    found = {}
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) != 5 or fields[0] != 'completed' or fields[4] != str(version):
            continue
        _, at, mission_id, contract, _ = fields
        found[(at, mission_id)] = dict(at=at, mission_id=mission_id, contract=contract)
    return sorted(found.values(), key=lambda row: row['at'])


def contract_key(value):
    # Runtime names append a numeric instance suffix to CareerContract names.
    generator, _, name = value.rpartition('/')
    return generator.casefold(), re.sub(r'_\d+$', '', name).casefold()


def associate(rewards, finished, contracts, window=3):
    """Require one nearby completion and one matching current-build pool.

    This is temporal evidence, not a blueprint service transaction: notification
    MissionId is usually zero. An ambiguous completion is never selected by
    nearest-distance, nor is a multi-pool reward guessed from its display name.
    """
    rows, unresolved = [], []
    times = [(datetime.fromisoformat(c['at']), c) for c in finished]
    for reward in rewards:
        at = datetime.fromisoformat(reward['at'])
        nearby = [(t, c) for t, c in times if abs((at-t).total_seconds()) <= window]
        if len(nearby) != 1:
            unresolved.append(dict(**reward, reason='no unique nearby completion'))
            continue
        time, complete = nearby[0]
        candidates = contracts.get(contract_key(complete['contract']), [])
        matches = {(p['id'], m['id']): (p, m) for p in candidates
                   for m in p['members'] if m.get('id') and item_key(m['name']) == item_key(reward['name'])}
        if len(matches) != 1:
            unresolved.append(dict(**reward, reason='no unique matching blueprint/pool', contract=complete['contract']))
            continue
        pool, member = next(iter(matches.values()))
        rows.append(dict(**reward, blueprint_id=member['id'], pool_id=pool['id'],
                         pool=pool['name'], stored_position=member['record_position'],
                         completion_at=complete['at'], mission_id=complete['mission_id'],
                         contract=complete['contract'], delay_seconds=round((at-time).total_seconds(), 3),
                         evidence='unique completion within 3s; name matches pool; grant has no mission link'))
    return rows, unresolved


def load_contracts(records, pools):
    by_name = {p['name']: p for p in pools}
    result = defaultdict(list)
    for path in (records/'libs/foundry/records/contracts/contractgenerator').rglob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        generator = record['_RecordName_'].split('.', 1)[-1].casefold()
        for node in walk_nodes(record):
            if node.get('_Type_') != 'CareerContract':
                continue
            key = (generator, node.get('debugName', '').casefold())
            for reward in walk_nodes(node):
                if reward.get('_Type_') != 'BlueprintRewards' or not reward.get('blueprintPool'):
                    continue
                reference = reward['blueprintPool']
                if not isinstance(reference, str):
                    continue
                pool_path = records/'libs/foundry/records'/reference.replace('\\', '/').split('libs/foundry/records/', 1)[1]
                pool_name = json.loads(pool_path.read_text(encoding='utf-8'))['_RecordName_']
                if pool_name in by_name:
                    result[key].append(by_name[pool_name])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('--pool-audit', required=True, type=Path)
    parser.add_argument('--version', required=True, type=int, help='e.g. 41002; never combine patches')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    audit = json.loads(args.pool_audit.read_text(encoding='utf-8'))
    contracts = load_contracts(args.records, audit['pools'])
    blueprint_path = args.profile/'blueprint_log_backup.txt'
    contract_path = args.profile/'contract_log_backup.txt'
    rewards = grants(blueprint_path.read_text(encoding='utf-8'))
    finished = completions(contract_path.read_text(encoding='utf-8'), args.version)
    rows, unresolved = associate(rewards, finished, contracts)
    observed = defaultdict(list)
    for row in rows:
        observed[row['pool_id']].append(row)
    result = dict(version=args.version, build=audit['build'],
                  status='Observed personal history only. Universal reward order NOT established.',
                  limitations=['One profile, incomplete historical coverage; earlier ownership is unknown.',
                               'Current extracted pool membership may differ from earlier builds.',
                               'Blueprint notification has no mission link; association is temporal.',
                               'Missing grants do not establish no-drop or completion numbers.',
                               'Requires independent matching sequences before global prediction.'],
                  input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (blueprint_path, contract_path, args.pool_audit)},
                  observations=rows, unresolved=unresolved)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'observed_rewards.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = ['# Observed blueprint award chronology', '', result['status'], '',
             'These are observed grants, not guaranteed completion numbers. No game files or ownership flags were changed.', '',
             *('- '+s for s in result['limitations']), '']
    for pool_id, entries in observed.items():
        pool = next(p for p in audit['pools'] if p['id'] == pool_id)
        seen = {r['blueprint_id'] for r in entries}
        lines += ['## '+pool['name'].split('.', 1)[-1], '',
                  f"Observed {len(seen)} of {len(pool['members'])} pool entries on this profile.", '',
                  '| Grant time (UTC) | Observed blueprint | Stored list position |',
                  '| --- | --- | --- |']
        lines += [f"| {r['at']} | {r['name']} | {r['stored_position']} |" for r in entries]
        missing = [m['name'] for m in pool['members'] if m.get('id') not in seen]
        if missing:
            lines += ['', 'Not observed in matched evidence (positions unknown): '+', '.join(missing)+'.']
        lines.append('')
    (args.output/'observed_rewards.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(observations=len(rows), pools=len(observed), unresolved=len(unresolved), output=str(args.output))))


if __name__ == '__main__':
    main()
