import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import blueprint_db
from crafting_catalog import get_catalog, material_coverage, quality_factor


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = get_catalog()

    def test_export_cardinality_and_references(self):
        c = self.catalog
        self.assertEqual(len(c.items), 1616)
        self.assertEqual(len(c.materials), 37)
        self.assertEqual(len(c.missions), 3406)
        self.assertEqual(sum(len(b['slots']) for b in c.items), 4310)
        self.assertEqual(len(c.by_id), len(c.items))
        for bp in c.items:
            for slot in bp['slots']:
                self.assertIn(slot['material'], c.materials)
                self.assertGreater(slot['amount'], 0)
                self.assertIn(slot['unit'], ('SCU', 'units'))
            self.assertEqual(len(c.sources(bp)), len(bp['sources']))

    def test_real_shield_recipe_preserves_repeated_material_and_units(self):
        bp = self.catalog.resolve('FR-76')
        self.assertEqual(self.catalog.cost(bp), {'Stileron': 1.1})
        self.assertEqual(self.catalog.cost(bp, 'units'), {'Feynmaline': 58})
        self.assertEqual([s['name'] for s in bp['slots']], ['Shell', 'Field Array', 'Frequency Controller'])

    def test_quality_uses_actual_endpoints_and_lower_is_better(self):
        bp = self.catalog.resolve('XL-1')
        effect = bp['slots'][2]['effects'][0]
        self.assertEqual(effect['better'], 'lower')
        self.assertAlmostEqual(quality_factor(effect, 1000), .8)
        self.assertAlmostEqual(quality_factor(effect, 500), 1)
        with self.assertRaises(ValueError):
            quality_factor(effect, 1001)

    def test_searches_stat_material_and_mission(self):
        for search in ('quantum fuel burn', 'borase tungsten', 'xl-1'):
            self.assertIn('XL-1', [b['name'] for b in self.catalog.library({}, search=search)])
        bp = self.catalog.resolve('XL-1')
        mission = self.catalog.sources(bp)[0]
        self.assertIn('XL-1', [b['name'] for b in self.catalog.library({}, search=mission['title'])])

    def test_no_partial_variant_resolution(self):
        self.assertIsNone(self.catalog.resolve('ADP Arms'))
        self.assertEqual(self.catalog.resolve('Civ/2/A FR-76')['name'], 'FR-76')
        self.assertNotEqual(self.catalog.resolve('ADP Arms Black')['id'], self.catalog.resolve('ADP Arms Blue')['id'])

    def test_legacy_cost_does_not_replace_real_recipe(self):
        rows = self.catalog.library({'FR-76': {'cost': {'Iron': 999}, 'source': 'Old OCR'}})
        bp = next(b for b in rows if b['name'] == 'FR-76')
        self.assertEqual(bp['cost'], {'Stileron': 1.1})
        self.assertTrue(bp['is_unlocked'])

    def test_unknown_owned_record_preserved_without_fake_recipe(self):
        result = self.catalog.library({'Future item': {'cost': {'Iron': 1}}}, status='OWNED')
        self.assertEqual(result[0]['name'], 'Future item')
        self.assertEqual(result[0]['slots'], [])
        self.assertEqual(result[0]['cost'], {})

    def test_group_and_type_filters(self):
        result = self.catalog.library({}, category='Ship components', item_type='Shield', group='Manufacturer')
        self.assertTrue(result)
        self.assertTrue(all(b['type'] == 'Shield' for b in result))
        self.assertTrue(all(b['group'] == (b['manufacturer'] or 'Unknown manufacturer') for b in result))

    def test_duplicate_display_names_require_explicit_variant_identity(self):
        self.assertIsNone(self.catalog.resolve('BroadSpec'))
        self.assertEqual({b['size'] for b in self.catalog.by_name['BroadSpec']}, {2, 3})

    def test_inventory_not_double_spent_across_slots(self):
        bp = self.catalog.resolve('FR-76')
        rows = material_coverage(bp, {'batches': {'Stileron': [{'scu': .7, 'quality': 1000}]}})
        self.assertAlmostEqual(sum(r['available'] for r in rows), .7)
        self.assertEqual(rows[2]['available'], 0)  # Unit-count gems aren't SCU.

    def test_default_quality_migration_is_not_measured_stock(self):
        bp = self.catalog.resolve('FR-76')
        rows = material_coverage(bp, {'batches': {'Stileron': [{'scu': 100, 'quality': 850, 'added_at': 'Default Batch'}]}})
        self.assertEqual(sum(r['available'] for r in rows), 0)

    def test_high_minimum_slots_get_qualified_stock_first(self):
        slot = dict(material='Iron', unit='SCU', amount=1, effects=[], min_quality=1, name='Low')
        item = dict(slots=[slot, dict(slot, min_quality=900, name='High')])
        result = material_coverage(item, {'batches': {'Iron': [{'scu': 1, 'quality': 1000}, {'scu': 1, 'quality': 500}]}})
        self.assertEqual([r['missing'] for r in result], [0, 0])

    def test_material_locations_keep_source_and_mining_family(self):
        material = self.catalog.materials['Pressurized Ice']
        self.assertTrue(material['locations'])
        self.assertEqual(material['location_name'], 'Ice')
        self.assertIn('family', material['locations'][0])

    def test_no_fabricated_cost_for_unknown_blueprint(self):
        self.assertEqual(blueprint_db.generate_default_cost('Unknown Rifle', 'FPS Weapons'), {})


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(blueprint_db, attr, str(self.root / name)) for attr, name in (
            ('BLUEPRINT_LIB_FILE', 'owned.json'), ('BLUEPRINT_CATALOG_FILE', 'catalog.json'), ('BLUEPRINT_FAVORITES_FILE', 'favorites.json'))]
        for p in self.patches:
            p.start()
        self.manager = blueprint_db.BlueprintManager()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def test_import_deduplicates_localization_aliases(self):
        self.assertEqual(self.manager.unlock_batch(['Civ/2/A FR-76', 'FR-76']), 1)
        self.assertEqual(len(self.manager.get_blueprints(status_filter='OWNED')), 1)
        self.assertEqual(self.manager.unlock_batch(['FR-76']), 0)

    def test_remove_does_not_remove_neighbor_variant(self):
        self.manager.unlock_batch(['ADP Arms Black', 'ADP Arms Blue'])
        self.assertFalse(self.manager.remove_blueprint('ADP Arms'))
        self.assertTrue(self.manager.remove_blueprint('ADP Arms Black'))
        self.assertIn('ADP Arms Blue', self.manager.blueprints)

    def test_corrupt_ownership_file_is_never_overwritten(self):
        path = self.root / 'owned.json'
        path.write_text('{broken', encoding='utf-8')
        manager = blueprint_db.BlueprintManager()
        with self.assertRaises(ValueError):
            manager.unlock_batch(['FR-76'])
        self.assertEqual(path.read_text(), '{broken')

    def test_favorites_survive_scans_and_reload(self):
        self.manager.toggle_favorite('FR-76')
        self.manager.unlock_batch(['FR-76', 'XL-1'])
        reloaded = blueprint_db.BlueprintManager()
        rows = reloaded.get_blueprints(status_filter='FAVORITES')
        self.assertEqual([r['name'] for r in rows], ['FR-76'])

    def test_log_unlock_keeps_source_timestamp(self):
        self.assertTrue(self.manager.record_log_unlock('FR-76', '2026-10-20T01:02:03', 'Live Game.log'))
        self.assertEqual(self.manager.blueprints['FR-76']['unlocked_at'], '2026-10-20T01:02:03')
        self.assertFalse(self.manager.record_log_unlock('Civ/2/A FR-76', 'later', 'Live Game.log'))

    def test_ambiguous_item_can_be_owned_by_explicit_id_only(self):
        variant = get_catalog().by_name['BroadSpec'][0]
        self.manager.unlock_batch([variant])
        rows = self.manager.get_blueprints(status_filter='OWNED')
        self.assertEqual([r['id'] for r in rows], [variant['id']])

    def test_failed_disk_write_rolls_back_import(self):
        with patch.object(blueprint_db, 'atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.manager.unlock_batch(['FR-76'])
        self.assertEqual(self.manager.blueprints, {})

    def test_favorite_write_failure_does_not_change_memory(self):
        with patch.object(blueprint_db, 'atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.manager.toggle_favorite('FR-76')
        self.assertEqual(self.manager.favorites, set())

    def test_unexpected_ownership_shape_is_preserved(self):
        path = self.root / 'owned.json'
        path.write_text('[]', encoding='utf-8')
        manager = blueprint_db.BlueprintManager()
        with self.assertRaises(ValueError):
            manager.unlock_batch(['FR-76'])
        self.assertEqual(path.read_text(), '[]')


if __name__ == '__main__':
    unittest.main()
