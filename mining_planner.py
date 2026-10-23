"""Mining-trip queries over versioned game presets; no invented live spawn rate."""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
from installation import output_root, game_directory


def material_key(name):
    name = name.casefold().replace('aluminium', 'aluminum')
    name = name.replace('pressurized ice', 'ice').replace('raw ice', 'ice').replace('raw silicon', 'silicon')
    return re.sub(r'\W+', '', re.sub(r'\s*\((ore|raw|r)\)$', '', name))


def primary_material(composition):
    amounts = defaultdict(float)
    for part in composition['parts']:
        if part['probability'] > 0:
            amounts[part['material']] += part['max_percent']
    return max(amounts, key=amounts.get) if amounts else None


class MiningPlanner:
    def __init__(self, path=None):
        self.data = json.loads(Path(path or output_root() / 'data/local_mining_catalog.json').read_text(encoding='utf-8'))
        self.compositions = self.data['compositions']
        self.locations = self.data['locations']
        manifest = game_directory()/'build_manifest.id'
        current = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else None
        self.matches_installation = bool(current and current['Data']['BuildId']==self.data['provenance']['build']['BuildId'])
        self.materials = sorted({p['material'] for c in self.compositions.values() for p in c['parts']})
        self.canonical = {material_key(m): m for m in self.materials}

    def resolve_material(self, name):
        return self.canonical.get(material_key(name))

    def candidates(self, targets, system='All', family='Ship', primary_only=True, include_internal=False,
                   min_quality_scale=0, sort='Primary prevalence'):
        wanted = [self.resolve_material(t) for t in targets]
        if not wanted or any(m is None for m in wanted):
            return []
        wanted = list(dict.fromkeys(wanted))
        results = []
        for location in self.locations:
            if not include_internal and not location['curated_visible']:
                continue
            if system != 'All' and location['system'] != system:
                continue
            families = sorted({g['family'] for g in location['groups']}) if family == 'All' else [family]
            for f in families:
                groups = [g for g in location['groups'] if g['family'] == f]
                total_weight = sum(g['weight'] for g in groups)
                if total_weight <= 0:
                    continue
                weights = defaultdict(float)
                for group in groups:
                    if group['denominator'] <= 0:
                        continue
                    for deposit in group['deposits']:
                        weights[deposit['composition']] += group['weight']/total_weight * deposit['weight']/group['denominator']
                matches = {}
                for target in wanted:
                    main_share, contains_share, max_fraction = 0., 0., 0.
                    for cid, weight in weights.items():
                        comp = self.compositions[cid]
                        parts = [p for p in comp['parts'] if p['material'] == target and p['probability'] > 0
                                 and p['quality_scale'] >= min_quality_scale]
                        if not parts:
                            continue
                        if primary_material(comp) == target:
                            main_share += weight
                        contains_share += weight
                        # This is an upper bound on configured mass share, not
                        # expected yield or probability of a successful trip.
                        max_fraction += weight * min(100, sum(p['max_percent'] for p in parts))/100
                    matches[target] = dict(primary_share=main_share, containing_share=contains_share,
                                           maximum_material_weight=max_fraction)
                if any(matches[t]['primary_share' if primary_only else 'containing_share'] <= 0 for t in wanted):
                    continue
                key = 'maximum_material_weight' if sort == 'Configured material upper bound' else 'primary_share'
                score = min(matches[t][key] for t in wanted)
                results.append(dict(location=location, family=f, matches=matches, weights=dict(weights), score=score,
                                    requested=wanted, quality_scale=min_quality_scale))
        return sorted(results, key=lambda r: (-r['score'], -sum(m['maximum_material_weight'] for m in r['matches'].values()), r['location']['name']))

    def relevant_compositions(self, candidate):
        wanted = set(candidate['requested'])
        result = []
        for cid, weight in candidate['weights'].items():
            comp = self.compositions[cid]
            if any(p['material'] in wanted and p['quality_scale'] >= candidate['quality_scale'] and p['probability'] > 0 for p in comp['parts']):
                result.append(dict(comp, weight=weight, primary=primary_material(comp)))
        return sorted(result, key=lambda c: -c['weight'])


@lru_cache(maxsize=1)
def get_mining_planner():
    return MiningPlanner()
