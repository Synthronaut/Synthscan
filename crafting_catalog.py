"""Sourced recipes and library queries. No player files are modified here."""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
from installation import output_root, game_directory


def normalize_name(name):
    # Localization prefixes describe class/size/grade, not the item name.
    name = re.sub(r'^(?:Civ|Ind|Mil|Stl|Cmp)/\d+/[A-Z]\s+', '', name, flags=re.I)
    return ' '.join(re.findall(r'[a-z0-9]+', name.casefold()))


def category_for(item_type):
    if 'Armor' in item_type:
        return 'Armor & suits'
    if item_type in ('Mining Laser', 'Mining Modifier', 'Salvage Modifier', 'Tractor Beam'):
        return 'Mining & industry'
    if item_type in ('FPS Weapon', 'Weapon Attachment'):
        return 'Personal weapons'
    if item_type == 'Weapon Gun':
        return 'Ship weapons'
    if item_type in ('Cooler', 'Power Plant', 'Quantum Drive', 'Radar', 'Shield', 'Fuel Nozzle'):
        return 'Ship components'
    if item_type in ('Jacket', 'Shirt', 'Shoes', 'Trousers'):
        return 'Clothing'
    return 'Equipment'


class CraftingCatalog:
    def __init__(self, path=None):
        directory = Path(__file__).parent / 'data'
        self.data = json.loads(Path(path or directory / 'crafting_catalog.json').read_text(encoding='utf-8'))
        local = output_root() / 'data/local_game_catalog.json'
        if path is None and local.exists():
            candidate = json.loads(local.read_text(encoding='utf-8'))
            # Keep data for other builds available as a reference, without
            # silently labelling it as verified against the current install.
            manifest_path = game_directory()/'build_manifest.id'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
            if manifest and candidate['native_provenance']['build']['BuildId'] == manifest['Data']['BuildId']:
                self.data = candidate
        self.items = self.data['blueprints']
        self.materials = {m['name']: m for m in self.data['materials']}
        self.missions = self.data['missions']
        self.by_id = {b['id']: b for b in self.items}
        self.native_by_id = {b['native_id']: b for b in self.items if b.get('native_id')}
        self.by_name = defaultdict(list)
        for bp in self.items:
            self.by_name[bp['name']].append(bp)
        self.aliases = defaultdict(list)
        for bp in self.items:
            bp['category'] = category_for(bp['type'])
            self.aliases[normalize_name(bp['name'])].append(bp)
        self.search_text = {}
        for bp in self.items:
            missions = self.sources(bp)
            self.search_text[bp['id']] = ' '.join(str(s or '') for s in (
                bp['name'], bp['type'], bp['category'], bp['manufacturer'], bp['item_class'],
                *[v['material'] for v in bp['slots']],
                *[e['stat'] for slot in bp['slots'] for e in slot['effects']],
                *[m[k] for m in missions for k in ('title', 'faction', 'system', 'standing')])).casefold()

    def resolve(self, name):
        identifier = name.removeprefix('catalog:')
        if identifier in self.by_id:
            return self.by_id[identifier]
        if identifier in self.native_by_id:
            return self.native_by_id[identifier]
        found = self.aliases.get(normalize_name(name), [])
        return found[0] if len(found) == 1 else None

    def sources(self, item):
        return [self.missions[i] for i in item['sources']]

    def cost(self, item, unit='SCU'):
        result = defaultdict(float)
        for slot in item['slots']:
            if slot['unit'] == unit:
                result[slot['material']] += slot['amount']
        return {k: round(v, 4) for k, v in result.items()}

    def library(self, owned, favorites=(), search='', category='All', item_type='All', status='ALL', group='Category'):
        owned_by_id = {}
        extras = []
        fav_ids = {b['id'] for n in favorites if (b := self.resolve(n))}
        for name, record in owned.items():
            resolved = self.resolve(record.get('catalog_id') or name)
            if resolved:
                owned_by_id[resolved['id']] = record
            else:
                extras.append(dict(record, name=record.get('name', name), category='Unmatched records', type='Unmatched',
                                   id='legacy:' + name, slots=[], sources=[], known_from_start=False))
        output = []
        terms = search.casefold().split()
        for raw in self.items + extras:
            record = owned_by_id.get(raw['id']) or (raw if raw['id'].startswith('legacy:') else {})
            unlocked = bool(record) or raw['known_from_start']
            favorite = raw['id'] in fav_ids or raw['name'] in favorites
            if category != 'All' and raw['category'] != category:
                continue
            if item_type != 'All' and raw['type'] != item_type:
                continue
            if status in ('OWNED', 'UNLOCKED') and not unlocked:
                continue
            if status in ('MISSING', 'LOCKED') and unlocked:
                continue
            if status == 'FAVORITES' and not favorite:
                continue
            haystack = self.search_text.get(raw['id'], raw['name'].casefold())
            if not all(t in haystack for t in terms):
                continue
            bp = dict(raw, is_unlocked=unlocked, is_favorite=favorite,
                      unlocked_at=record.get('unlocked_at'),
                      ownership_source=record.get('source', 'Available from start' if raw['known_from_start'] else 'Not recorded'),
                      source=record.get('source', 'Game-file catalog'),
                      cost=self.cost(raw), recipe_verified=not raw['id'].startswith('legacy:'),
                      meta={'main': raw['category'], 'sub': raw['type'], 'size': f"Size {raw.get('size')}"})
            if group in ('Material', 'Primary material'):
                bp['group'] = raw['slots'][0]['material'] if raw['slots'] else 'Unknown materials'
            elif group == 'Manufacturer':
                bp['group'] = raw.get('manufacturer') or 'Unknown manufacturer'
            elif group == 'Type':
                bp['group'] = raw['type']
            else:
                bp['group'] = raw['category']
            output.append(bp)
        return sorted(output, key=lambda b: (b['group'].casefold(), b['name'].casefold()))


@lru_cache(maxsize=1)
def get_catalog():
    return CraftingCatalog()


def quality_factor(effect, quality):
    """Use the actual per-effect endpoints; do not assume q500 is stock."""
    if not 1 <= quality <= 1000:
        raise ValueError('Quality must be 1–1000')
    if effect.get('unreadable'):
        return None
    segments = effect.get('segments')
    if segments:
        selected = next((s for s in segments if s['quality_min'] <= quality <= s['quality_max']), None)
        if selected is None:
            if quality < segments[0]['quality_min']:
                return segments[0]['at_min']
            if quality > segments[-1]['quality_max']:
                return segments[-1]['at_max']
            return None
        effect = selected
    lo, hi = effect['quality_min'], effect['quality_max']
    if hi <= lo:
        return effect['at_min']
    fraction = min(1, max(0, (quality - lo) / (hi - lo)))
    return effect['at_min'] + fraction * (effect['at_max'] - effect['at_min'])


def material_coverage(item, inventory):
    """Reserve quantities across slots so repeated ingredients cannot be double used.

    Only SCU inventory can satisfy SCU slots. Unit-count gems are never converted.
    This is local ledger coverage, not evidence of materials at the fabricator.
    """
    available = defaultdict(list)
    for material, batches in inventory.get('batches', {}).items():
        key = normalize_name(material.replace('Aluminium', 'Aluminum'))
        for batch in batches:
            if batch.get('added_at') == 'Default Batch':
                continue  # Legacy totals-only migration invented quality 850.
            q = batch.get('quality')
            if isinstance(q, (int, float)) and 1 <= q <= 1000:
                available[key].append([float(batch.get('scu', 0)), q])
    rows = []
    # Hardest requirements first avoids consuming high-quality stock prematurely.
    slots = sorted(enumerate(item['slots']), key=lambda p: -p[1]['min_quality'])
    for index, slot in slots:
        needed, supplied = slot['amount'], 0.0
        if slot['unit'] == 'SCU':
            key = normalize_name(slot['material'].replace('Aluminium', 'Aluminum'))
            for batch in sorted(available[key], key=lambda b: b[1]):
                if batch[1] < slot['min_quality']:
                    continue
                take = min(batch[0], needed - supplied)
                supplied += take
                batch[0] -= take
        rows.append((index, dict(slot, available=round(supplied, 4), missing=round(needed - supplied, 4))))
    return [r for _, r in sorted(rows)]
