"""Read-only reputation feasibility audit of an explicit StarBreaker export.

Writes research artifacts only; never edits game localization or account data.
Outcome array indices are retained until their engine meaning is verified.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_records import GameRecords


def audit(records, localization, manifest):
    store = GameRecords(records, localization)
    base = store.root / 'libs/foundry/records'
    failures = []

    def ref(reference):
        try:
            return store.resolve(reference)['_RecordValue_']
        except (ValueError, OSError, KeyError) as error:
            failures.append({'reference': reference, 'error': str(error)})
            return {}

    scopes, missions, labels = [], [], defaultdict(set)
    faction_tracks = []
    for path in sorted((base / 'factions/factionreputation').glob('*.json')):
        record = store.read(path)
        value = record['_RecordValue_']
        reference = value.get('reputationContextPropertiesUI')
        if not reference:
            continue
        context = ref(reference)
        entries = [context.get('primaryScopeContext', {})] + context.get('scopeContextList', [])
        for entry in entries:
            if not entry.get('scope'):
                continue
            scope = ref(entry['scope'])
            faction_tracks.append(dict(faction_id=record['_RecordId_'],
                                       faction=store.text(value.get('displayName')),
                                       hidden=value.get('hideInDelpihApp'),
                                       scope=scope.get('scopeName'), scope_reference=entry['scope'],
                                       current_balance=None, live_source_verified=False))
    for path in sorted((base / 'reputation/scopes').rglob('*.json')):
        record = store.read(path)
        value = record['_RecordValue_']
        standing_map = value.get('standingMap', {})
        standings = []
        for reference in standing_map.get('standings', []):
            standing = ref(reference)
            key = standing.get('displayName', '')
            threshold = standing.get('minReputation')
            labels[key].add(threshold)
            standings.append(dict(name=store.text(key), localization_key=key,
                                  minimum=threshold, gated=standing.get('gated'),
                                  drift=standing.get('driftReputation'),
                                  drift_hours=standing.get('driftTimeHours'), reference=reference))
        scopes.append(dict(id=record['_RecordId_'], name=value.get('scopeName'),
                           display_name=store.text(value.get('displayName')),
                           localization_key=value.get('displayName'),
                           initial=standing_map.get('initialReputation'),
                           ceiling=standing_map.get('reputationCeiling'), standings=standings,
                           source=str(path.relative_to(store.root))))
    for path in sorted((base / 'missionbroker').rglob('*.json')):
        record = store.read(path)
        value = record['_RecordValue_']
        outcomes = []
        for index, outcome in enumerate(value.get('missionResultReputationRewards', [])):
            rewards = []
            for entry in outcome.get('reputationAmounts', []):
                faction = ref(entry.get('factionReputation'))
                scope = ref(entry.get('reputationScope'))
                reward = ref(entry.get('reward'))
                rewards.append(dict(faction=store.text(faction.get('displayName')),
                                    scope=store.text(scope.get('displayName')),
                                    configured_amount=reward.get('reputationAmount'),
                                    references=entry))
            if rewards:
                outcomes.append(dict(index=index, rewards=rewards))
        if outcomes:
            missions.append(dict(id=record['_RecordId_'], record=record['_RecordName_'],
                                 title=store.text(value.get('title')),
                                 description_key=value.get('description'),
                                 not_for_release=value.get('notForRelease'),
                                 can_be_shared=value.get('canBeShared'), outcomes=outcomes,
                                 source=str(path.relative_to(store.root))))
    # Shared descriptions with different rewards must not receive an exact annotation.
    descriptions = defaultdict(set)
    for mission in missions:
        descriptions[mission['description_key']].add(json.dumps(mission['outcomes'], sort_keys=True))
    return dict(build=manifest['Data'], scopes=scopes, faction_tracks=faction_tracks, missions=missions,
                limitations=['Static configured values, not verified server payouts.',
                             'Outcome indices are not yet mapped to engine result names.',
                             'Test/unreleased records are retained and flagged; presence does not prove availability.',
                             'No live account reputation source established.'],
                shared_rank_labels_with_different_thresholds={k: sorted(v, key=lambda x: (x is None, x))
                    for k, v in labels.items() if len(v) > 1},
                shared_mission_descriptions_with_different_rewards=[k for k, v in descriptions.items() if len(v) > 1],
                unresolved_references=failures,
                source_hashes={str(p.relative_to(store.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(store.used)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('--localization', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.records, args.localization, json.loads(args.manifest.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(scopes=len(result['scopes']), missions_with_rewards=len(result['missions']),
                          ambiguous_rank_labels=len(result['shared_rank_labels_with_different_thresholds']),
                          ambiguous_mission_descriptions=len(result['shared_mission_descriptions_with_different_rewards']),
                          unresolved_references=len(result['unresolved_references']))))


if __name__ == '__main__':
    main()
