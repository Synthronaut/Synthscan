"""Tests for the Knick-Knacks spare inventory catalog and graph extractor."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from knick_knacks import (
    KnickKnacksCatalog,
    KnickKnacksService,
    aggregate_items,
    cig_guid_crc,
    extract_inventory_items,
)


class KnickKnacksTests(unittest.TestCase):
    def test_cig_guid_crc_matches_known_entitlement_and_starmap_ids(self):
        # Verified against StarCitizen.exe SSE4.2 CRC32C (<QQ hipart, lopart)
        self.assertEqual(cig_guid_crc('8cda0b9b-22a8-43fe-ac33-df7a1ba9434d'), 3781743795)  # GrimHEX
        self.assertEqual(cig_guid_crc('233238ee-adeb-4405-8045-49fa07370f37'), 2147648880)  # Port Tressler
        self.assertEqual(cig_guid_crc('0df18692-2cc7-4d9d-af85-95b8a7a45419'), 2792343189)  # MG Scrip

    def test_catalog_classifies_components_crafting_wikelo_and_comp_boards(self):
        cat = KnickKnacksCatalog()
        self.assertEqual(cat.resolve_inventory_location('205621716799:Location:848868938')['location_name'], 'Orbituary')
        self.assertEqual(cat.resolve_inventory_location('205621716799:Location:3170699229')['location_name'], 'New Babbage')

        # DCHS-05 Comp-Board -> comp_boards + is_wikelo (used in Wikelo recipes too)
        comp_board = cat.classify_item(cig_guid_crc('7f2786bf-bf9a-4115-a14c-9fc0506be204'))
        self.assertIsNotNone(comp_board)
        assert comp_board is not None
        self.assertEqual(comp_board['category'], 'comp_boards')
        self.assertTrue(comp_board['is_comp_board'])

        # Carinite -> mining_crafting + is_crafting + is_wikelo
        carinite = cat.classify_item(next(
            c for c, m in cat.items_by_crc.items() if m['name'] == 'Carinite'
        ))
        self.assertIsNotNone(carinite)
        assert carinite is not None
        self.assertEqual(carinite['category'], 'mining_crafting')
        self.assertTrue(carinite['is_crafting'])
        self.assertTrue(carinite['is_wikelo'])

        # Starter respawn suits/helmets are excluded, while special variants remain visible
        for starter in ('Beacon Undersuit White', 'Horizon Helmet White'):
            crc = next((c for c, m in cat.items_by_crc.items() if m['name'] == starter), None)
            if crc is not None:
                self.assertIsNone(cat.classify_item(crc))
        rust = next((c for c, m in cat.items_by_crc.items() if m['name'] == 'Beacon Undersuit "Rust Society"'), None)
        if rust is not None:
            self.assertIsNotNone(cat.classify_item(rust))

    def test_extract_inventory_items_excludes_ship_mounted_and_includes_hangar_and_crate_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            ship_crc = 1001
            shield_crc = 2001
            ore_crc = 2002
            backpack_crc = 2003
            keycard_crc = 2004
            hangar_crc = 3001
            structural_crc = 4001

            cat_path = tmp_dir / 'catalog.json'
            cat_path.write_text(json.dumps({
                'schema': 1,
                'locations': {
                    '848868938': {'name': 'Orbituary', 'record': 'RR_P3_LEO', 'system': 'Pyro'},
                },
                'vehicle_crcs': [ship_crc],
                'hangar_crcs': [hangar_crc],
                'non_item_crcs': [structural_crc],
                'extra_items': {
                    str(shield_crc): {'name': 'FR-76', 'category': 'Ship components', 'type': 'Shield'},
                    str(ore_crc): {'name': 'Hadanite', 'category': 'Raw resources', 'type': 'Raw resource'},
                    str(backpack_crc): {'name': 'Pembroke Backpack', 'category': 'Armor & clothing', 'type': 'Char_Armor_Backpack'},
                    str(keycard_crc): {'name': 'PYAM Supervisor Keycard', 'category': 'Equipment & other items', 'type': 'RemovableChip'},
                },
                'wikelo_ingredients': ['hadanite'],
                'crafting_materials': ['hadanite'],
            }), encoding='utf-8')
            lib_path = tmp_dir / 'lib.json'
            lib_path.write_text(json.dumps({'schema': 1, 'entries': []}), encoding='utf-8')
            cat = KnickKnacksCatalog(catalog_path=cat_path, library_path=lib_path)

            # Build Location graph:
            # - Ship (10) stowed in inv -> has mounted FR-76 (11) ATTACHED_TO Ship -> MUST BE EXCLUDED
            # - Spare FR-76 (12) stowed directly in inv -> INCLUDED (Local Storage)
            # - Structural Door (13) stowed in inv -> EXCLUDED
            # - Backpack (14) stowed in inv -> holds 12x Hadanite (15) STOWED_IN Backpack -> INCLUDED
            inv_id = '999:Location:848868938'
            nodes = [
                {'properties': {'entity_properties': {'geid': '10', 'class_guid_crc': ship_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '11', 'class_guid_crc': shield_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '12', 'class_guid_crc': shield_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '13', 'class_guid_crc': structural_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '14', 'class_guid_crc': backpack_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '15', 'class_guid_crc': ore_crc, 'stack_size': 12}}},
            ]
            edges = [
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '10'}, 'end': {'type': 'NODE_TYPE_INVENTORY', 'inventory_id': inv_id}},
                {'type': 'ENTITY_EDGE_TYPE_ATTACHED_TO', 'start': {'entity_id': '11'}, 'end': {'type': 'NODE_TYPE_ENTITY', 'entity_id': '10'}},
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '12'}, 'end': {'type': 'NODE_TYPE_INVENTORY', 'inventory_id': inv_id}},
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '13'}, 'end': {'type': 'NODE_TYPE_INVENTORY', 'inventory_id': inv_id}},
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '14'}, 'end': {'type': 'NODE_TYPE_INVENTORY', 'inventory_id': inv_id}},
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '15'}, 'end': {'type': 'NODE_TYPE_ENTITY', 'entity_id': '14'}},
            ]

            items, mounted = extract_inventory_items(cat, inv_id, nodes, edges)
            self.assertEqual(mounted, 1)  # mounted FR-76
            names_qty = {(r['name'], r['container'], r['quantity']) for r in items}
            self.assertEqual(names_qty, {
                ('FR-76', 'Local Storage', 1),
                ('Pembroke Backpack', 'Local Storage', 1),
                ('Hadanite', 'In Pembroke Backpack', 12),
            })

            # Hangar graph: Hangar (20) -> Keycard (21) ATTACHED_TO Hangar, plus docked Ship (22) -> Shield (23) EXCLUDED
            hangar_inv = '999:Hangar:848868938'
            h_nodes = [
                {'properties': {'entity_properties': {'geid': '20', 'class_guid_crc': hangar_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '21', 'class_guid_crc': keycard_crc, 'stack_size': 2}}},
                {'properties': {'entity_properties': {'geid': '22', 'class_guid_crc': ship_crc, 'stack_size': 1}}},
                {'properties': {'entity_properties': {'geid': '23', 'class_guid_crc': shield_crc, 'stack_size': 1}}},
            ]
            h_edges = [
                {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '20'}, 'end': {'type': 'NODE_TYPE_INVENTORY', 'inventory_id': hangar_inv}},
                {'type': 'ENTITY_EDGE_TYPE_ATTACHED_TO', 'start': {'entity_id': '21'}, 'end': {'type': 'NODE_TYPE_ENTITY', 'entity_id': '20'}},
                {'type': 'ENTITY_EDGE_TYPE_ATTACHED_TO', 'start': {'entity_id': '22'}, 'end': {'type': 'NODE_TYPE_ENTITY', 'entity_id': '20'}},
                {'type': 'ENTITY_EDGE_TYPE_ATTACHED_TO', 'start': {'entity_id': '23'}, 'end': {'type': 'NODE_TYPE_ENTITY', 'entity_id': '22'}},
            ]
            h_items, h_mounted = extract_inventory_items(cat, hangar_inv, h_nodes, h_edges)
            self.assertEqual(h_mounted, 1)
            self.assertEqual([(r['name'], r['container'], r['quantity']) for r in h_items], [
                ('PYAM Supervisor Keycard', 'Persistent Hangar', 2),
            ])

    def test_aggregate_items_sums_identical_stacks_per_location_and_container(self):
        rows = [
            {'crc': 1, 'name': 'TS-2', 'category': 'ship_components', 'category_label': 'Ship Components', 'sub_type': 'QuantumDrive', 'manufacturer': '', 'size': 3, 'grade': 1, 'is_wikelo': False, 'is_crafting': False, 'is_comp_board': False, 'is_ship_component': True, 'location_id': '848868938', 'location_name': 'Orbituary', 'system': 'Pyro', 'storage_kind': 'location', 'container': 'Local Storage', 'quantity': 2},
            {'crc': 1, 'name': 'TS-2', 'category': 'ship_components', 'category_label': 'Ship Components', 'sub_type': 'QuantumDrive', 'manufacturer': '', 'size': 3, 'grade': 1, 'is_wikelo': False, 'is_crafting': False, 'is_comp_board': False, 'is_ship_component': True, 'location_id': '848868938', 'location_name': 'Orbituary', 'system': 'Pyro', 'storage_kind': 'location', 'container': 'Local Storage', 'quantity': 3},
            {'crc': 1, 'name': 'TS-2', 'category': 'ship_components', 'category_label': 'Ship Components', 'sub_type': 'QuantumDrive', 'manufacturer': '', 'size': 3, 'grade': 1, 'is_wikelo': False, 'is_crafting': False, 'is_comp_board': False, 'is_ship_component': True, 'location_id': '3170699229', 'location_name': 'New Babbage', 'system': 'Stanton', 'storage_kind': 'location', 'container': 'Local Storage', 'quantity': 1},
        ]
        agg = aggregate_items(rows)
        self.assertEqual(len(agg), 2)
        self.assertEqual(agg[0]['location_name'], 'Orbituary')
        self.assertEqual(agg[0]['quantity'], 5)
        self.assertEqual(agg[1]['location_name'], 'New Babbage')
        self.assertEqual(agg[1]['quantity'], 1)

    def test_auto_compboard_counts_sums_dchs_boards_from_knick_knacks_state(self):
        from compboard_inventory import auto_compboard_counts
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertIsNone(auto_compboard_counts(d))
            (d / 'knick_knacks_state.json').write_text(json.dumps({
                'status': 'ok',
                'updated_at': 1700000000,
                'items': [
                    {'name': 'DCHS-01 Executive Access Protocols Comp-Board', 'quantity': 2},
                    {'name': 'DCHS-04 Power Processing Comp-Board', 'quantity': 5},
                    {'name': 'DCHS-05 Orbital Positioning Comp-Board', 'quantity': 6},
                    {'name': 'DCHS-05 Orbital Positioning Comp-Board', 'quantity': 5},
                    {'name': 'MG Scrip', 'quantity': 278},
                ],
            }), encoding='utf-8')
            res = auto_compboard_counts(d)
            self.assertIsNotNone(res)
            assert res is not None
            self.assertTrue(res['auto_synced'])
            self.assertEqual(res['counts'], [2, 0, 0, 5, 11, 0, 0])
            self.assertEqual(res['total'], 18)
            self.assertEqual(res['complete_sets'], 0)

    def test_game_account_rejects_foreign_owner_entitygraph_queries(self):
        import types
        from game_account import OwnAccount
        dummy = object.__new__(OwnAccount)
        dummy.subject = 'urn:sc:global:player:geid:205621716799'
        dummy.metadata = ()
        dummy.channel = types.SimpleNamespace(unary_unary=lambda *a, **kw: (lambda req, **kw2: None))
        req = types.SimpleNamespace(body=types.SimpleNamespace(owner_id='999999999999'))
        with patch('account_permission.require_account_access', return_value=None):
            with self.assertRaises(ValueError):
                OwnAccount.read(dummy, 'entitygraph', 'EntityGraphService', 'GetInventories', req)

    def test_starter_exclusion_covers_gme_gown_and_prison_kit(self):
        from knick_knacks import KnickKnacksCatalog, extract_inventory_items
        cat = KnickKnacksCatalog()
        gown_crc = next((c for c, m in cat.items_by_crc.items() if str(m.get('name') or '').lower() == 'gme 338-10 medical gown'), None)
        prison_crc = next((c for c, m in cat.items_by_crc.items() if str(m.get('name') or '').lower() == 'inmate worksuit'), None)
        self.assertIsNotNone(gown_crc)
        self.assertIsNotNone(prison_crc)
        nodes = [
            {'properties': {'entity_properties': {'geid': '1', 'class_guid_crc': gown_crc, 'stack_size': 2}}},
            {'properties': {'entity_properties': {'geid': '2', 'class_guid_crc': prison_crc, 'stack_size': 1}}},
        ]
        edges = [
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '1'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': '2'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
        ]
        rows, _ = extract_inventory_items(cat, '205621716799:Location:848868938', nodes, edges)
        self.assertEqual(rows, [])

    def test_extract_entitlement_items_groups_rsi_hangar_and_skips_attached_parts(self):
        from knick_knacks import KnickKnacksCatalog, extract_entitlement_items
        cat = KnickKnacksCatalog()
        c1_guid = '9611b8ed-cc96-4b5c-aa1e-baefe7d5bb1c'  # CRUS_Spirit_C1
        attached_urn = 'urn:sc:global:entitlement:uuid:attached-visor'
        snapshots = [
            {'snapshot': {'root_urn': 'urn:root', 'item_urn': attached_urn, 'attach_path': ['helmet_visor']}},
            {'snapshot': {'root_urn': 'urn:ship', 'item_urn': 'urn:ship', 'attach_path': []}},
        ]
        entitlements = [
            {
                'urn': 'urn:ship',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_PLATFORM',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': c1_guid,
                'created_at': '2026-01-10T00:00:00Z',
                'metadata': {'name': 'CRUS_Spirit_C1', 'stack_size': 1, 'real_money': True, 'source_sku': 'UNDEFINED'},
            },
            {
                'urn': attached_urn,
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_PLATFORM',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': 'b48e460e-6809-4547-a7b1-3ebb3c5930ac',
                'metadata': {'name': 'FP_Visor', 'stack_size': 1, 'real_money': True},
            },
            {
                'urn': 'urn:ltp',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_INGAME_PERSISTENT',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': c1_guid,
                'metadata': {'name': 'CRUS_Spirit_C1', 'stack_size': 1, 'real_money': False},
            },
            {
                'urn': 'urn:rental',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_RENTAL',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': c1_guid,
                'metadata': {'name': 'CRUS_Spirit_C1', 'stack_size': 1},
            },
        ]
        items, counts = extract_entitlement_items(cat, entitlements, snapshots)
        self.assertEqual(len(items), 2)
        self.assertEqual(counts['rsi_hangar'], 1)
        self.assertEqual(counts['ingame_ltp'], 1)
        self.assertEqual(items[0]['source_kind'], 'rsi_hangar')
        self.assertEqual(items[0]['category'], 'ships')
        self.assertTrue(items[0]['real_money'])
        self.assertEqual(items[1]['source_kind'], 'ingame_ltp')

    def test_snapshot_decoding_extracts_crafted_ingredients_and_material_quality_tiers(self):
        import base64
        import struct
        from knick_knacks import (
            KnickKnacksCatalog,
            _SNAPSHOT_VAR_CRAFTED,
            _SNAPSHOT_VAR_RESOURCE,
            aggregate_items,
            extract_inventory_items,
        )
        cat = KnickKnacksCatalog()
        beradom_crc = next((c for c, m in cat.items_by_crc.items() if str(m.get('name') or '').lower() == 'beradom'), None)
        self.assertIsNotNone(beradom_crc)
        p4ar_crc = next((c for c, m in cat.items_by_crc.items() if 'p4-ar' in str(m.get('name') or '').lower() and m.get('type') == 'WeaponPersonal'), None)
        self.assertIsNotNone(p4ar_crc)
        mat_guid_le = next(iter(cat.name_by_guid_le.keys()))
        mat_name = cat.name_by_guid_le[mat_guid_le]

        lot_hi = base64.b64encode(struct.pack('<BIHQI', 1, 0x11223344, 881, 1000, 1)).decode()
        lot_lo = base64.b64encode(struct.pack('<BIHQI', 1, 0x11223344, 287, 1000, 1)).decode()
        craft_blob = base64.b64encode(struct.pack('<H', 1) + mat_guid_le + struct.pack('<HQB', 916, 40000, 0)).decode()
        empty_craft_blob = base64.b64encode(struct.pack('<H17x', 0)).decode()

        nodes = [
            {'properties': {'entity_properties': {'geid': 'm1', 'class_guid_crc': beradom_crc, 'stack_size': 10}}},
            {'properties': {'entity_properties': {'geid': 'm2', 'class_guid_crc': beradom_crc, 'stack_size': 5}}},
            {'properties': {'entity_properties': {'geid': 'w1', 'class_guid_crc': p4ar_crc, 'stack_size': 1}}},
            {'properties': {'entity_properties': {'geid': 'w2', 'class_guid_crc': p4ar_crc, 'stack_size': 1}}},
        ]
        edges = [
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': 'm1'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': 'm2'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': 'w1'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
            {'type': 'ENTITY_EDGE_TYPE_STOWED_IN', 'start': {'entity_id': 'w2'}, 'end': {'type': 'NODE_TYPE_INVENTORY'}},
        ]
        snapshots = [
            {'entity_id': 'm1', 'variables': [{'name_crc': _SNAPSHOT_VAR_RESOURCE, 'snapshot': lot_hi}]},
            {'entity_id': 'm2', 'variables': [{'name_crc': _SNAPSHOT_VAR_RESOURCE, 'snapshot': lot_lo}]},
            {'entity_id': 'w1', 'variables': [{'name_crc': _SNAPSHOT_VAR_CRAFTED, 'snapshot': craft_blob}]},
            {'entity_id': 'w2', 'variables': [{'name_crc': _SNAPSHOT_VAR_CRAFTED, 'snapshot': empty_craft_blob}]},
        ]
        raw, _ = extract_inventory_items(cat, '205621716799:Location:848868938', nodes, edges, snapshots)
        agg = aggregate_items(raw)

        mat_rows = [r for r in agg if r['crc'] == beradom_crc]
        self.assertEqual(len(mat_rows), 1)
        self.assertEqual(mat_rows[0]['quantity'], 15)
        self.assertEqual(mat_rows[0]['max_quality'], 881)
        self.assertEqual(mat_rows[0]['min_quality'], 287)
        self.assertEqual(len(mat_rows[0]['quality_tiers']), 2)
        self.assertEqual(mat_rows[0]['quality_tiers'][0]['quality'], 881)
        self.assertEqual(mat_rows[0]['quality_tiers'][0]['units'], 10)
        self.assertAlmostEqual(mat_rows[0]['total_scu'], 0.015, places=4)

        gun_rows = [r for r in agg if r['crc'] == p4ar_crc]
        self.assertEqual(len(gun_rows), 2)
        crafted_row = next(r for r in gun_rows if r['is_crafted'])
        plain_row = next(r for r in gun_rows if not r['is_crafted'])
        self.assertEqual(crafted_row['crafted_quality'], 916)
        self.assertEqual(crafted_row['crafted_ingredients'][0]['name'], mat_name)
        self.assertFalse(plain_row['is_crafted'])

    def test_classify_entitlement_filters_hull_subparts_and_noise(self):
        from knick_knacks import KnickKnacksCatalog
        cat = KnickKnacksCatalog()
        for raw_name in (
            'banu_lum_jacket',
            'orig_armor_heavy',
            'ESPR_BallisticCannon_S5',
            'AEGS_Retaliator_PrisonPod',
            'DRAK_Cutlass_SeatAccess',
            'ShipATCDataManager_123',
            'ANVL_Hornet_Decoy',
        ):
            res = cat.classify_entitlement('', raw_name, '')
            if res is not None:
                self.assertNotEqual(res['category'], 'ships', f'{raw_name} misclassified as ships')

    def test_build_fleet_summary_tracks_earned_pledged_and_unowned(self):
        from knick_knacks import KnickKnacksCatalog, build_fleet_summary
        cat = KnickKnacksCatalog()
        self.assertTrue(len(cat.earnable_ships) > 100)
        dealer_ship = next(s for s in cat.earnable_ships if s['channel'] == 'dealership')
        wikelo_ship = next(s for s in cat.earnable_ships if s['channel'] == 'wikelo')
        unowned_ship = next(
            s for s in cat.earnable_ships
            if int(s['crc']) not in {int(dealer_ship['crc']), int(wikelo_ship['crc'])}
        )
        account_items = [
            {
                'crc': int(dealer_ship['crc']),
                'name': dealer_ship['name'],
                'category': 'ships',
                'source_kind': 'ingame_ltp',
                'manufacturer': dealer_ship['company'],
                'sub_type': dealer_ship['role'],
                'quantity': 1,
            },
            {
                'crc': int(wikelo_ship['crc']),
                'name': wikelo_ship['name'],
                'category': 'ships',
                'source_kind': 'rsi_hangar',
                'manufacturer': wikelo_ship['company'],
                'sub_type': wikelo_ship['role'],
                'quantity': 1,
            },
        ]
        fleet, counts = build_fleet_summary(cat, account_items)
        by_key = {(r['crc'], r['ownership']): r for r in fleet}
        self.assertIn((int(dealer_ship['crc']), 'ingame_earned'), by_key)
        self.assertIn((int(wikelo_ship['crc']), 'pledged'), by_key)
        self.assertIn((int(unowned_ship['crc']), 'unowned'), by_key)
        self.assertEqual(counts['ingame_earned'], 1)
        self.assertEqual(counts['pledged'], 1)
        self.assertGreater(counts['unowned'], 50)
        self.assertEqual(counts['exec_hangar'], 8)

    def test_extract_entitlement_items_excludes_packaged_sku_stubs_and_starfarer_loaner(self):
        from knick_knacks import KnickKnacksCatalog, extract_entitlement_items
        cat = KnickKnacksCatalog()
        ents = [
            {
                'urn': 'urn:1',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_PLATFORM',
                'status': 'ENTITLEMENT_STATUS_PACKAGED',
                'entity_class_guid': 'ec956be2-8e3a-460d-b3a8-97df4cb12b78',
                'metadata': {'name': 'S-RSI-AURORA-MK2', 'source_sku': 'S-RSI-AURORA-MK2', 'real_money': True, 'stack_size': 1},
            },
            {
                'urn': 'urn:2',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_PLATFORM',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': '13a02a6d-7d67-4d22-8530-d4d2c8443f66',
                'metadata': {'name': 'MISC_Starfarer', 'source_sku': 'S-MISC-STARFARER-TANKER', 'real_money': True, 'stack_size': 1},
            },
            {
                'urn': 'urn:3',
                'source_type': 'ENTITLEMENT_SOURCE_TYPE_PLATFORM',
                'status': 'ENTITLEMENT_STATUS_DELIVERED',
                'entity_class_guid': '9611b8ed-cc96-4b5c-aa1e-baefe7d5bb1c',
                'metadata': {'name': 'CRUS_Spirit_C1', 'source_sku': 'S-CRUS-SPIRIT-C1', 'real_money': True, 'stack_size': 1},
            },
        ]
        items, counts = extract_entitlement_items(cat, ents, [])
        ship_names = [r['name'] for r in items if r['category'] == 'ships']
        self.assertEqual(ship_names, ['Crusader C1 Spirit'])
        self.assertEqual(counts['ships'], 1)


if __name__ == '__main__':
    unittest.main()
