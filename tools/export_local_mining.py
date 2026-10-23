"""Extract mining compositions and location groups from StarBreaker JSON.

Location labels are separately attributed curation. All numerical data and
reference relationships come from the selected local game export.
"""
import argparse
import csv
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_records import GameRecords, walk_nodes

FAMILIES = {'SpaceShip_Mineables': 'Ship', 'SpaceShip_Mineables_Rare': 'Ship',
            'GroundVehicle_Mineables': 'ROC', 'FPS_Mineables': 'FPS'}


def clean_material(name):
    import re
    return re.sub(r'\s*\((?:Ore|Raw|R)\)$', '', name, flags=re.I).replace('Aluminium', 'Aluminum').replace('Raw Ice', 'Ice').replace('Raw Silicon', 'Silicon')


def composition(reference, records):
    record = records.resolve(reference)
    value = record['_RecordValue_']
    parts = []
    for raw in value['compositionArray']:
        element = records.resolve(raw['mineableElement'])
        name = records.resource_name(element['_RecordValue_']['resourceType'])
        refined = records.resource_name(element['_RecordValue_']['resourceType'], refined=True)
        parts.append(dict(material=clean_material(refined).replace('Pressurized Ice','Ice'), raw_name=name, element_id=element['_RecordId_'],
                          min_percent=raw['minPercentage'], max_percent=raw['maxPercentage'],
                          probability=raw['probability'], quality_scale=raw['qualityScale'], curve_exponent=raw['curveExponent']))
    return dict(id=record['_RecordId_'], name=records.text(value.get('depositName'), record['_RecordName_'].split('.',1)[-1]),
                minimum_distinct_elements=value['minimumDistinctElements'], parts=parts)


def export(records, manifest, labels_path):
    labels = {r['preset']: r for r in csv.DictReader(labels_path.open(encoding='utf-8'))}
    locations, compositions, failures = [], {}, []
    directory = records.root / 'libs/foundry/records/harvestable/providerpresets'
    for path in sorted(directory.rglob('*.json')):
        label = labels.get(path.stem)
        if not label:
            continue
        record = records.read(path)
        groups = []
        for raw_group in record['_RecordValue_']['harvestableGroups']:
            family = FAMILIES.get(raw_group['groupName'])
            if not family:
                continue
            deposits = []
            for raw in raw_group['harvestables']:
                try:
                    preset = records.resolve(raw['harvestable'])
                    entity = records.value(preset['_RecordValue_']['entityClass'])
                    mineable = next(c for c in entity['Components'] if c['_Type_'] == 'MineableParams')
                    comp = composition(mineable['composition'], records)
                    compositions[comp['id']] = comp
                    deposits.append(dict(id=preset['_RecordId_'], composition=comp['id'],
                                         weight=raw['relativeProbability'], source=preset['_RecordName_']))
                except (KeyError, ValueError, FileNotFoundError, StopIteration) as exc:
                    failures.append(dict(location=label['name'], group=raw_group['groupName'], error=str(exc)))
            # Retain all original denominator weights, even unreadable entries.
            groups.append(dict(name=raw_group['groupName'], family=family,
                               weight=raw_group['groupProbability'],
                               denominator=sum(d['relativeProbability'] for d in raw_group['harvestables']), deposits=deposits))
        if groups:
            locations.append(dict(id=record['_RecordId_'], preset=path.stem, name=label['name'],
                                  system=label['system'], kind=label['kind'], curated_visible=label['visible']=='1', groups=groups))
    alias_data = json.loads(labels_path.with_name('mining_location_aliases.json').read_text(encoding='utf-8'))
    for alias in alias_data['aliases']:
        source = next((l for l in locations if l['preset']==alias['source_preset']), None)
        if source is None:
            failures.append(dict(location=alias['name'], error='Curated alias source preset is missing'))
            continue
        locations.append(dict(copy.deepcopy(source), id=alias['id'], name=alias['name'], system=alias['system'],
                              kind=alias['kind'], curated_alias=dict(alias, source=alias_data['source'], url=alias_data['url'])))
    return dict(schema=1, provenance=dict(build=manifest['Data'], source='Installed Game2.dcb via StarBreaker v0.3.2',
                labels=json.loads(labels_path.with_suffix('.provenance.json').read_text(encoding='utf-8')),
                failures=failures), locations=locations, compositions=compositions)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-root', type=Path, required=True)
    parser.add_argument('--localization', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=root / 'data/local_mining_catalog.json')
    args = parser.parse_args()
    records = GameRecords(args.export_root, args.localization)
    data = export(records, json.loads(args.manifest.read_text(encoding='utf-8')), root/'data/mining_location_labels.csv')
    data['provenance']['record_hashes'] = {str(p.relative_to(records.root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(records.used)}
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(',',':'))+'\n', encoding='utf-8')
    print(json.dumps(dict(locations=len(data['locations']), compositions=len(data['compositions']), failures=data['provenance']['failures']),indent=2))


if __name__ == '__main__':
    main()
