"""Build a GUID-indexed encyclopedia and genuine artwork cache from local exports.

Game asset references are matched by full archive path, never fuzzy item names.
RTT entities are retained as references; a missing render is not a static icon.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_records import GameRecords, walk_nodes


def asset_key(path):
    path = str(path).replace('\\', '/').strip('/').lower()
    if not path.startswith('data/'):
        path = 'data/' + path
    if '..' in path.split('/'):
        raise ValueError('Asset path traversal')
    # Source art references use TIFF; the packaged GPU texture uses DDS.
    return str(Path(path).with_suffix('.dds')).replace('\\', '/') if path.endswith(('.tif', '.tiff', '.png')) else path


def export_assets(source, destination, build):
    from PIL import Image
    import resvg_py
    assets, failures = {}, []
    output = destination / 'assets/game' / build
    output.mkdir(parents=True, exist_ok=True)
    for parent, _, files in os.walk(source):
        for filename in sorted(files):
            path = Path(parent) / filename
            if path.suffix.lower() not in ('.png', '.svg'):
                continue
            reference = path.relative_to(source).as_posix()
            key = asset_key(reference)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            target = output / (hashlib.sha256(key.encode()).hexdigest()[:20] + '.png')
            try:
                if path.suffix.lower() == '.svg':
                    target.write_bytes(resvg_py.svg_to_bytes(svg_string=raw.decode('utf-8-sig'), width=192, height=192, skip_system_fonts=True))
                else:
                    with Image.open(path) as image:
                        image = image.convert('RGBA')
                        image.thumbnail((384, 384))
                        image.save(target)
                with Image.open(target) as image:
                    if not image.getbbox():
                        raise ValueError('Empty image')
                    width, height = image.size
                assets[key] = dict(file=target.relative_to(destination).as_posix(), source=reference,
                                   decoded_source_sha256=digest, sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                                   width=width, height=height)
            except (OSError, ValueError) as exc:
                failures.append(dict(source=reference, error=str(exc)))
    return assets, failures


def artwork(raw, assets):
    refs = []
    # Only actual UI fields. Entity Icon=Default.bmp is an editor placeholder.
    for node in walk_nodes(raw.get('StaticEntityClassData', [])):
        for field in ('displayThumbnail', 'displayImage', 'displayIcon'):
            if node.get(field):
                refs.append(dict(field=field, path=node[field]))
    for node in raw.get('Components', []):
        if isinstance(node, dict) and node.get('displayThumbnail'):
            refs.append(dict(field='displayThumbnail', path=node['displayThumbnail']))
    for field in ('defaultThumbnailPathSVG', 'defaultThumbnailPath'):
        if raw.get(field):
            refs.append(dict(field=field, path=raw[field]))
    keys = list(dict.fromkeys(asset_key(r['path']) for r in refs))
    return [key for key in keys if key in assets], refs


def category(typ):
    if typ.startswith(('Armor', 'Clothing', 'Char_Armor', 'Char_Clothing')) or typ in ('Helmet', 'Undersuit'):
        return 'Armor & clothing'
    if typ.startswith(('Mining', 'Salvage')) or typ in ('WeaponMining', 'TractorBeam', 'TowingBeam', 'ToolArm'):
        return 'Mining & salvage'
    if typ.startswith(('Weapon', 'Missile', 'Turret', 'Gun', 'Magazine')) or typ in ('Grenade', 'Bomb', 'BombLauncher'):
        return 'Weapons & ammunition'
    if typ in ('PowerPlant', 'Cooler', 'Shield', 'QuantumDrive', 'JumpDrive', 'Radar', 'Thruster', 'FuelTank', 'QuantumFuelTank'):
        return 'Ship components'
    if typ.startswith(('Food', 'Drink', 'Medical')) or typ=='FPS_Consumable':
        return 'Consumables'
    if typ.startswith(('Cargo', 'Container', 'Carryable')):
        return 'Cargo & containers'
    if typ=='Paints':
        return 'Paints & customization'
    return 'Equipment & other items'


def internal_type(typ):
    return (typ.startswith(('Char_Head', 'Char_Hair', 'Char_Skin', 'Char_Body', 'Seat'))
            or typ.endswith('Controller') or typ in {
                'Door', 'ControlPanel', 'UNDEFINED', 'Elevator', 'Display', 'Button', 'AttachedPart',
                'DockingAnimator', 'DockingCollar', 'SelfDestruct', 'Relay', 'WeaponMount', 'TargetSelector'})


def export_entries(store, assets):
    entries, skipped, failures = [], Counter(), []
    directory = store.root / 'libs/foundry/records/entities/scitem'
    processed = 0
    for parent, _, files in os.walk(directory):
        for filename in sorted(files):
            if not filename.endswith('.json'):
                continue
            path = Path(parent) / filename
            try:
                record = store.read(path)
                raw = record['_RecordValue_']
                components = [n for n in raw.get('Components', []) if isinstance(n, dict)]
                attach = next((n['AttachDef'] for n in components if n.get('_Type_') == 'SAttachableComponentParams'), None)
                if not attach:
                    skipped['no_item_definition'] += 1
                    continue
                item = store.item(path.relative_to(store.root).as_posix())
                if not item['name'] or item['name'].upper() in ('PLACEHOLDER', 'UNINITIALIZED', 'DEFAULT'):
                    skipped['no_localized_name'] += 1
                    continue
                art, refs = artwork(raw, assets)
                typ = item['type'] or 'Other'
                entry = dict(id=item['guid'], name=item['name'], description=item['description'], type=typ,
                             manufacturer=item['manufacturer'], size=item['size'], grade=item['grade'],
                             kind='Item', category=category(typ), tag=record['_RecordName_'],
                             internal=internal_type(typ),
                             record=path.relative_to(store.root).as_posix(), artwork=art, artwork_references=refs,
                             has_geometry=any(n.get('_Type_')=='SGeometryResourceParams' for n in components),
                             inventory_micro_scu=attach.get('inventoryOccupancyVolume', {}).get('microSCU'),
                             component_types=sorted({n.get('_Type_', '') for n in components}))
                entries.append(entry)
            except (KeyError, ValueError, OSError) as exc:
                failures.append(dict(record=path.relative_to(store.root).as_posix(), error=str(exc)))
            processed += 1
            if processed % 2000 == 0:
                print(f'Indexed {processed} item records; {len(entries)} named entries', flush=True)
    for guid, resource in store.resources.items():
        name = store.text(resource.get('displayName'))
        if not name:
            skipped['resource_without_name'] += 1
            continue
        art, refs = artwork(resource, assets)
        refined = resource.get('refinedVersion')
        entries.append(dict(id=guid, name=name, description=store.text(resource.get('description')),
                            kind='Material', category='Raw resources' if refined else 'Materials & commodities',
                            type='Raw resource' if refined else 'Resource', tag=resource['_RecordName_'],
                            record='libs/foundry/records/resourcetypedatabase/resourcetypedatabase.json',
                            artwork=art, artwork_references=refs, thumbnail_entity=resource.get('rttThumbnailEntityClass'),
                            refined_id=refined.get('_RecordId_') if refined else None))
    return entries, dict(skipped), failures


def export(store, source, destination, manifest):
    assets, asset_failures = export_assets(source, destination, manifest['Data']['BuildId'])
    entries, skipped, failures = export_entries(store, assets)
    return dict(schema=1, entries=entries, assets=assets, provenance=dict(
        build=manifest['Data'], source='Installed Game2.dcb and Data.p4k via StarBreaker v0.3.2',
        tool_url='https://github.com/diogotr7/StarBreaker/releases/tag/v0.3.2',
        copyright='Game records and artwork: Cloud Imperium Games. Local extraction; no redistribution grant implied.',
        entries=len(entries), with_static_artwork=sum(bool(e['artwork']) for e in entries),
        by_kind=dict(Counter(e['kind'] for e in entries)), assets=len(assets), skipped=skipped,
        failures=failures, asset_failures=asset_failures,
        note='Named client records include variants, internal and unreleased items. Presence does not establish availability. Static icons can be shared by the game; missing 3D thumbnails are not replaced with invented art.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=Path, required=True)
    parser.add_argument('--localization', type=Path, required=True)
    parser.add_argument('--artwork-source', type=Path, required=True)
    parser.add_argument('--game-dir', type=Path, default=Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE'))
    args = parser.parse_args()
    manifest_path = args.game_dir / 'build_manifest.id'
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    # The export folder must carry a build receipt from the extraction step.
    for source in (args.records.parent, args.artwork_source):
        receipt = json.loads((source / 'source_manifest.json').read_text(encoding='utf-8'))
        if receipt['Data']['BuildId'] != manifest['Data']['BuildId']:
            raise ValueError('Export/artwork belongs to a different game build: '+str(source))
    store = GameRecords(args.records, args.localization)
    data = export(store, args.artwork_source, ROOT, manifest)
    if original != manifest_path.read_bytes():
        raise RuntimeError('Game build changed; catalog preserved')
    output = ROOT / 'data/local_game_library.json'
    prepared = output.with_suffix('.json.tmp')
    prepared.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    os.replace(prepared, output)
    print(json.dumps(data['provenance'], indent=2), flush=True)


if __name__ == '__main__':
    main()
