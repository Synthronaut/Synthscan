import json
from pathlib import Path
import unittest

from crafting_catalog import CraftingCatalog, get_catalog, quality_factor
from mining_planner import get_mining_planner


class MiningPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planner = get_mining_planner()

    def location(self, rows, name):
        return next(row for row in rows if row['location']['name']==name)

    def test_native_dataset_has_matching_build_and_no_unresolved_deposits(self):
        p = self.planner
        self.assertEqual(p.data['provenance']['build']['RequestedP4ChangeNum'], '12913470')
        self.assertEqual(sum(not bool(l.get('curated_alias')) for l in p.locations), 45)
        self.assertEqual(len(p.compositions), 56)
        self.assertEqual(p.data['provenance']['failures'], [])
        for location in p.locations:
            for group in location['groups']:
                self.assertGreater(group['denominator'], 0)
                for deposit in group['deposits']:
                    self.assertIn(deposit['composition'], p.compositions)

    def test_primary_weight_does_not_double_count_two_quality_portions(self):
        row = self.location(self.planner.candidates(['Gold']), 'Lagrange B')
        self.assertAlmostEqual(row['matches']['Gold']['primary_share'], .18)
        self.assertAlmostEqual(row['matches']['Gold']['maximum_material_weight'], .162)

    def test_secondary_only_location_not_represented_as_primary_source(self):
        primary = self.planner.candidates(['Gold'])
        self.assertNotIn('Lagrange A', [r['location']['name'] for r in primary])
        secondary = self.location(self.planner.candidates(['Gold'], primary_only=False), 'Lagrange A')
        self.assertEqual(secondary['matches']['Gold']['primary_share'], 0)
        self.assertAlmostEqual(secondary['matches']['Gold']['containing_share'], .18)
        self.assertAlmostEqual(secondary['matches']['Gold']['maximum_material_weight'], .009)

    def test_quality_scale_filter_keeps_high_quality_portion_only(self):
        row = self.location(self.planner.candidates(['Gold'], min_quality_scale=1), 'Lagrange B')
        self.assertAlmostEqual(row['matches']['Gold']['maximum_material_weight'], .18*.117)
        rows = self.planner.candidates(['Gold'], primary_only=False, min_quality_scale=1)
        self.assertNotIn('Lagrange A', [r['location']['name'] for r in rows])

    def test_same_rock_secondaries_are_preserved_separately(self):
        row = self.planner.candidates(['Stileron'])[0]
        rock = next(c for c in self.planner.relevant_compositions(row) if c['primary']=='Stileron')
        secondary = next(p for p in rock['parts'] if p['material']=='Taranite')
        self.assertEqual((secondary['min_percent'], secondary['max_percent'], secondary['quality_scale']), (5,10,.789))
        self.assertEqual(len([p for p in rock['parts'] if p['material']=='Stileron']), 2)

    def test_system_and_equipment_filters_are_independent(self):
        rows = self.planner.candidates(['Gold'], system='Stanton', family='Ship')
        self.assertTrue(rows)
        self.assertTrue(all(r['location']['system']=='Stanton' and r['family']=='Ship' for r in rows))
        self.assertEqual(self.planner.candidates(['Gold'], family='ROC'), [])

    def test_material_aliases_and_unknown_material(self):
        self.assertEqual(self.planner.resolve_material('Aluminium'), 'Aluminum')
        self.assertEqual(self.planner.resolve_material('Pressurized Ice'), 'Ice')
        self.assertEqual(self.planner.candidates(['Definitely not ore']), [])

    def test_internal_presets_are_not_default_trip_destinations(self):
        self.assertTrue(all(r['location']['curated_visible'] for r in self.planner.candidates(['Gold'])))

    def test_multi_material_filter_requires_all_targets(self):
        rows = self.planner.candidates(['Gold','Laranite'], primary_only=False)
        self.assertTrue(rows)
        self.assertTrue(all(set(r['matches'])=={'Gold','Laranite'} for r in rows))

    def test_terminus_ring_is_an_explicit_community_mapping(self):
        row = self.location(self.planner.candidates(['Ouratite'],system='Pyro'), 'Terminus Ring')
        self.assertIn('community curation', row['location']['curated_alias']['note'])


class NativeRecipeTests(unittest.TestCase):
    def test_local_recipe_inputs_and_real_guid_are_available(self):
        bp = get_catalog().resolve('FR-76')
        self.assertTrue(bp['native_verified'])
        self.assertEqual(bp['native_id'], '6748a7c7-5e6f-463e-87c2-05b20a7bd3ae')
        self.assertEqual(get_catalog().resolve(bp['native_id'])['name'], 'FR-76')
        self.assertTrue(bp['description'])

    def test_quality_501_uses_second_segment_instead_of_global_linear_approximation(self):
        effect = get_catalog().resolve('FR-76')['slots'][0]['effects'][0]
        self.assertEqual(quality_factor(effect,500), 1)
        self.assertEqual(quality_factor(effect,501), 1)
        self.assertEqual(quality_factor(effect,1000), 1.2)

    def test_null_local_ranges_keep_their_reference_provenance(self):
        effects = [e for b in get_catalog().items for s in b['slots'] for e in s['effects'] if e.get('local_decode_unknown')]
        self.assertTrue(effects)
        self.assertTrue(all('reference' in e['curve_source'].lower() for e in effects))

    def test_unreadable_curve_is_not_silently_flat(self):
        self.assertIsNone(quality_factor({'unreadable':True},500))

    def test_original_reference_catalog_remains_available(self):
        c = CraftingCatalog(Path(__file__).resolve().parents[1]/'data/crafting_catalog.json')
        self.assertFalse(c.resolve('FR-76').get('native_verified',False))


if __name__ == '__main__':
    unittest.main()
