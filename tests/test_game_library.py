import json
from pathlib import Path
import tempfile
import unittest

from game_library import GameLibrary
from game_records import GameRecords
from tools.export_game_library import artwork, asset_key, category, internal_type


class GameLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'library.json'
        self.path.write_text(json.dumps(dict(entries=[
            dict(id='a', name='Same name', kind='Item', category='Weapons', type='WeaponPersonal', artwork=['icon']),
            dict(id='b', name='Same name', kind='Item', category='Armor', type='Armor', artwork=[]),
            dict(id='c', name='Gold', kind='Material', category='Materials', type='Resource', artwork=[]),
            dict(id='d', name='Door', kind='Item', category='Other', type='Door', artwork=[], internal=True),
        ], assets=dict(icon=dict(file='../../config.json')), provenance={})))
        self.catalog = GameLibrary(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_identity_does_not_pick_a_same_named_variant(self):
        self.assertIsNone(self.catalog.resolve('Same name'))
        self.assertEqual(self.catalog.resolve('b')['category'], 'Armor')
        self.assertEqual(self.catalog.resolve('gold', 'Material')['id'], 'c')
        self.assertIsNone(self.catalog.resolve('Gold', 'Item'))

    def test_internal_records_are_opt_in(self):
        self.assertEqual(self.catalog.query('Door'), [])
        self.assertEqual(self.catalog.query('Door', include_internal=True)[0]['id'], 'd')

    def test_filters_combine_without_hiding_ambiguous_variants(self):
        self.assertEqual(len(self.catalog.query('same name', kind='Item')), 2)
        self.assertEqual([e['id'] for e in self.catalog.query('same', artwork_only=True)], ['a'])
        self.assertEqual([e['id'] for e in self.catalog.query(category='Armor')], ['b'])

    def test_catalog_cannot_open_a_non_artwork_file(self):
        self.assertIsNone(self.catalog.image_path(self.catalog.resolve('a')))

    def test_missing_catalog_has_usable_empty_state(self):
        missing = GameLibrary(self.path.with_name('missing.json'))
        self.assertTrue(missing.error)
        self.assertEqual(missing.query(), [])
        self.assertFalse(missing.matches_installation)

    def test_bad_catalog_schema_does_not_break_startup(self):
        for content in ('[]', '{"entries": null}', '{"entries": [null], "assets": {}, "provenance": {}}'):
            self.path.write_text(content)
            broken = GameLibrary(self.path)
            self.assertTrue(broken.error)
            self.assertEqual(broken.query(), [])

    def test_full_asset_path_matching_and_editor_placeholder_exclusion(self):
        raw = dict(Icon='Default.bmp', StaticEntityClassData=[dict(displayIcon='UI/A/icon.tif')], Components=[None])
        art, refs = artwork(raw, {'data/ui/b/icon.dds': {}, 'data/ui/a/icon.dds': {}})
        self.assertEqual(art, ['data/ui/a/icon.dds'])
        self.assertEqual(len(refs), 1)
        self.assertEqual(artwork(dict(Icon='Default.bmp'), {}), ([], []))

    def test_asset_reference_normalization_keeps_svg_distinct(self):
        self.assertEqual(asset_key(r'UI\Assets\Gold.tif'), 'data/ui/assets/gold.dds')
        self.assertEqual(asset_key('Data/UI/Gold.svg'), 'data/ui/gold.svg')
        with self.assertRaises(ValueError):
            asset_key('UI/../../config.json')

    def test_game_types_have_player_facing_categories(self):
        self.assertEqual(category('Char_Armor_Torso'), 'Armor & clothing')
        self.assertEqual(category('WeaponMining'), 'Mining & salvage')
        self.assertTrue(internal_type('FlightController'))
        self.assertFalse(internal_type('WeaponMining'))

    def test_null_polymorphic_component_does_not_discard_valid_item(self):
        root = Path(self.temp.name)
        (root/'english.ini').write_text('item_name=Test weapon\n')
        path = root/'libs/foundry/records/resourcetypedatabase/resourcetypedatabase.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        item = root/'libs/foundry/records/item.json'
        item.write_text(json.dumps(dict(_RecordId_='guid', _RecordValue_=dict(Components=[None, dict(
            _Type_='SAttachableComponentParams', AttachDef=dict(Type='WeaponPersonal', Localization=dict(Name='@item_name')))]))))
        store = GameRecords(root, root/'english.ini')
        self.assertEqual(store.item('libs/foundry/records/item.json')['name'], 'Test weapon')


if __name__ == '__main__':
    unittest.main()
