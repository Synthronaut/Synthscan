"""Export Bedrock's generated C++ tables without executing upstream code.

Usage: python tools/import_bedrock_crafting.py [checkout] [output]
The tiny initializer reader deliberately accepts only literals and braces.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TOKEN = re.compile(r'\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|true\b|false\b|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?[fF]?|[{},])')


def initializer(source, name):
    start = re.search(r'\b' + re.escape(name) + r'\[\]\s*=\s*', source).end()
    end = source.index('};', start) + 1
    raw = re.sub(r'//[^\n]*', '', source[start:end])
    pos = 0
    tokens = []
    while pos < len(raw):
        match = TOKEN.match(raw, pos)
        if not match:
            if raw[pos:].strip():
                raise ValueError(f'Unsupported initializer in {name}: {raw[pos:pos+40]!r}')
            break
        tokens.append(match.group(1))
        pos = match.end()
    cursor = 0

    def value():
        nonlocal cursor
        t = tokens[cursor]
        cursor += 1
        if t == '{':
            rows = []
            while tokens[cursor] != '}':
                rows.append(value())
                if tokens[cursor] == ',':
                    cursor += 1
            cursor += 1
            return rows
        if t.startswith('"'):
            return json.loads(t)
        if t.startswith("'"):
            return t[1:-1]
        if t in ('true', 'false'):
            return t == 'true'
        return float(t.rstrip('fF')) if any(c in t for c in '.eEfF') else int(t)

    result = value()
    if cursor != len(tokens):
        raise ValueError('Trailing initializer tokens')
    return result


def export(checkout):
    path = checkout / 'include' / 'CraftingData.h'
    source = path.read_text(encoding='utf-8')
    tables = {name: initializer(source, 'CRAFT_' + name) for name in (
        'TYPES', 'CLASSES', 'STAT_NAMES', 'SLOT_NAMES', 'MATERIALS', 'EFFECTS',
        'SLOTS', 'SOURCES', 'BLUEPRINTS', 'POOL_ITEMS')}
    source_keys = ('title faction system standing type briefing minutes difficulty cooldown '
                   'abandon_cooldown once_only chance pool_size skill load risk knowledge illegal '
                   'reputation score risk_text ships party pool_first pool_count respawn '
                   'respawn_variance intro other_first other_count rep_faction rep_ladder '
                   'rep_rank rep_rank_max rep_gain').split()
    missions = []
    for row in tables['SOURCES']:
        if len(row) != len(source_keys):
            raise ValueError('Upstream mission schema changed')
        mission = dict(zip(source_keys, row))
        first, count = mission.pop('pool_first'), mission.pop('pool_count')
        mission['reward_pool'] = tables['POOL_ITEMS'][first:first + count]
        missions.append(mission)
    materials = [dict(zip(('name', 'location_name', 'as_units', 'blueprints', 'rarity', 'quality_bands'), row))
                 for row in tables['MATERIALS']]
    blueprints = []
    identities = {}
    for name, typ, grade, size, cls, maker, seconds, first, count, starter, nmissions, sf, sc, employers in tables['BLUEPRINTS']:
        slots = []
        for slot, mat, scu, units, minimum, ef, ec in tables['SLOTS'][first:first + count]:
            effects = []
            for stat, better, amin, amax, qmin, qmax in tables['EFFECTS'][ef:ef + ec]:
                effects.append(dict(stat=tables['STAT_NAMES'][stat] if stat >= 0 else 'Unnamed stat',
                                    better=('higher', 'lower', 'neither', 'unusable', 'unknown')[better],
                                    at_min=amin, at_max=amax, quality_min=qmin, quality_max=qmax))
            slots.append(dict(name=tables['SLOT_NAMES'][slot] if slot >= 0 else 'Material',
                              material=materials[mat]['name'], amount=units if units else scu,
                              unit='units' if units else 'SCU', min_quality=minimum, effects=effects))
        identity = json.dumps((name, typ, grade, size, cls, maker, slots), sort_keys=True)
        ordinal = identities.get(identity, 0)
        identities[identity] = ordinal + 1
        identifier = hashlib.sha256((identity + ':' + str(ordinal)).encode()).hexdigest()[:20]
        blueprints.append(dict(id=identifier, name=name,
                               type=tables['TYPES'][typ], grade=grade if grade != '0' and grade != 0 else None,
                               size=size if size >= 0 else None,
                               item_class=tables['CLASSES'][cls] if cls >= 0 else None,
                               manufacturer=maker, seconds=seconds, slots=slots,
                               known_from_start=starter, mission_count=nmissions,
                               sources=list(range(sf, sf + sc)), employers=employers))
    assert len(blueprints) == 1616 and len(materials) == 37 and len(missions) == 3406
    assert sum(len(b['slots']) for b in blueprints) == 4310
    commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    locations_path = checkout / 'include/MiningLocations.h'
    locations_text = locations_path.read_text(encoding='utf-8')
    location_rows = re.search(r'ORE_LOCATIONS\s*=\s*(\{.*?\n\});', locations_text, re.S).group(1)
    location_rows = re.sub(r'MiningFamily::(\w+)', r'"\1"', location_rows)
    locations = initializer('ORE_LOCATIONS[] = ' + location_rows + ';', 'ORE_LOCATIONS')
    for material in materials:
        material['locations'] = [dict(zip(('material', 'family', 'location', 'system', 'kind', 'note', 'chance'), r))
                                 for r in locations if r[0] == material['location_name']]
    refineries = initializer((checkout / 'include/RefineryData.h').read_text(encoding='utf-8'), 'REFINERIES')
    return dict(schema=1, provenance=dict(project='SC-Ravaxx/Bedrock', commit=commit,
                 source_url=f'https://github.com/SC-Ravaxx/Bedrock/blob/{commit}/include/CraftingData.h',
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(), game_version='4.10.2-LIVE',
                 extracted='2026-10-11', note='Upstream game-file tables; not independently verified against this installation.'),
                location_provenance=dict(source='Bedrock / SCMDB', game_version='4.10.0-live.12572603',
                    sha256=hashlib.sha256(locations_path.read_bytes()).hexdigest(),
                    source_url=f'https://github.com/SC-Ravaxx/Bedrock/blob/{commit}/include/MiningLocations.h'),
                refinery_stations=[r[0] for r in refineries],
                materials=materials, missions=missions, blueprints=blueprints)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    checkout = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'research/bedrock_upstream'
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'data/crafting_catalog.json'
    data = export(checkout)
    output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{len(data["blueprints"])} blueprints, {len(data["materials"])} materials, {len(data["missions"])} mission sources -> {output}')
