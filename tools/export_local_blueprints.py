"""Verify/enrich the recipe catalog with the installed game's StarBreaker export.

Mission annotations and mining-location curation retain their separate
Bedrock/SCMDB provenance. This exporter never claims they were re-derived.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_records import GameRecords, walk_nodes


def effects_for(slot, records, directions):
    effects = []
    for node in walk_nodes(slot.get('context', [])):
        if node.get('_Type_') != 'CraftingGameplayPropertyModifierCommon':
            continue
        prop = records.value(node['gameplayPropertyRecord'])
        stat = records.text(prop['propertyName'], prop['propertyName'])
        ranges = node.get('valueRanges', [])
        if not ranges or any(not isinstance(r, dict) or r.get('_Type_') != 'CraftingGameplayPropertyModifierValueRange_Linear' for r in ranges):
            effects.append(dict(stat=stat, better=directions.get(stat, 'unknown'), unreadable=True))
            continue
        segments = sorted([dict(quality_min=r['startQuality'], quality_max=r['endQuality'],
                                at_min=r['modifierAtStart'], at_max=r['modifierAtEnd']) for r in ranges],
                          key=lambda r: r['quality_min'])
        effects.append(dict(stat=stat, better=directions.get(stat, 'unknown'), segments=segments,
                            quality_min=segments[0]['quality_min'], quality_max=segments[-1]['quality_max'],
                            at_min=segments[0]['at_min'], at_max=segments[-1]['at_max'],
                            direction_source='Bedrock interpretation' if stat in directions else 'Unknown'))
    return effects


def slots_for(costs, records, directions):
    mandatory = costs.get('mandatoryCost', {})
    if mandatory.get('_Type_') != 'CraftingCost_Select' or mandatory.get('count') != len(mandatory.get('options', [])):
        raise ValueError('Unsupported mandatory recipe selection')
    slots = []
    for slot in mandatory['options']:
        if slot.get('count') != 1 or len(slot.get('options', [])) != 1:
            raise ValueError('Recipe has alternative inputs; requires explicit choice support')
        ingredient = slot['options'][0]
        typ = ingredient.get('_Type_')
        if typ == 'CraftingCost_Resource':
            material = records.resource_name(ingredient['resource'])
            amount, unit = ingredient['quantity']['standardCargoUnits'], 'SCU'
        elif typ == 'CraftingCost_Item':
            material = records.item(ingredient['entityClass'])['name']
            amount, unit = ingredient['quantity'], 'units'
        else:
            raise ValueError('Unsupported ingredient type: ' + str(typ))
        info = slot['nameInfo']
        slots.append(dict(name=records.text(info['displayName'], info['debugName'].title()), material=material,
                          amount=amount, unit=unit, min_quality=ingredient['minQuality'],
                          effects=effects_for(slot, records, directions)))
    return slots


def recipe_key(slots):
    return [(s['name'].casefold(), s['material'].casefold(), s['unit'], round(s['amount'], 4)) for s in slots]


def export(records, base, manifest):
    data = copy.deepcopy(base)
    directions = {e['stat']: e['better'] for b in base['blueprints'] for s in b['slots'] for e in s['effects']}
    native = []
    failures = []
    for path in sorted((records.root / 'libs/foundry/records/crafting/blueprints').rglob('*.json')):
        raw = records.read(path)
        bp = raw['_RecordValue_'].get('blueprint', {})
        creation = bp.get('processSpecificData', {})
        if creation.get('_Type_') != 'CraftingProcess_Creation':
            continue
        try:
            item = records.item(creation['entityClass'])
            costs = bp['tiers'][0]['recipe']['costs']
            slots = slots_for(costs, records, directions)
            t = costs['craftTime']
            seconds = t['days']*86400 + t['hours']*3600 + t['minutes']*60 + t['seconds']
            native.append(dict(guid=raw['_RecordId_'], tag=raw['_RecordName_'], name=item['name'],
                               slots=slots, seconds=seconds, item=item))
        except (KeyError, ValueError, FileNotFoundError) as exc:
            failures.append(dict(record=raw['_RecordName_'], error=str(exc)))
    matched, unmatched, ambiguous = 0, [], []
    for bp in data['blueprints']:
        candidates = [n for n in native if n['name'] == bp['name'] and recipe_key(n['slots']) == recipe_key(bp['slots'])
                      and n['item']['size'] == bp['size']]
        if len(candidates) != 1:
            (ambiguous if candidates else unmatched).append(bp['name'])
            continue
        n = candidates[0]
        for fresh, prior in zip(n['slots'], bp['slots']):
            for index, effect in enumerate(fresh['effects']):
                if effect.get('unreadable'):
                    reference = next((e for e in prior['effects'] if e['stat'] == effect['stat']), None)
                    if reference:
                        fresh['effects'][index] = dict(copy.deepcopy(reference), local_decode_unknown=True,
                                                       curve_source='Bedrock reference; local decoder returned an unreadable range')
        bp.update(native_id=n['guid'], native_tag=n['tag'], item_id=n['item']['guid'],
                  description=n['item']['description'], slots=n['slots'], seconds=n['seconds'],
                  recipe_source='Installed Game2.dcb via StarBreaker', native_verified=True)
        matched += 1
    data['native_provenance'] = dict(build=manifest['Data'], tool='StarBreaker v0.3.2',
        tool_source='https://github.com/diogotr7/StarBreaker/releases/tag/v0.3.2',
        native_recipes=len(native), enriched_entries=matched,
        unmatched_entries=unmatched, ambiguous_entries=ambiguous, failures=failures,
        note='Recipe inputs and descriptions verified locally. Readable curves retain their actual segments; undecoded curves are explicitly labelled reference data. Unlock annotations retain their original source.')
    return data


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-root', type=Path, required=True)
    parser.add_argument('--localization', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=root / 'data/local_game_catalog.json')
    args = parser.parse_args()
    records = GameRecords(args.export_root, args.localization)
    base = json.loads((root / 'data/crafting_catalog.json').read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    data = export(records, base, manifest)
    data['native_provenance']['record_hashes'] = {str(p.relative_to(records.root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(records.used)}
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in data['native_provenance'].items() if k != 'record_hashes'},indent=2))


if __name__ == '__main__':
    main()
