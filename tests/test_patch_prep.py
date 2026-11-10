import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from patch_prep import (
    backup_control_mappings,
    clear_shader_cache,
    deploy_ptu_to_live,
    get_drive_space,
    get_game_root,
    get_patch_status,
    get_shader_cache_info,
    inspect_channel,
    restore_control_mappings,
    seed_ptu_from_live,
)


class TestPatchPrep(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sc_root = self.tmp / 'StarCitizen'
        self.sc_root.mkdir()

        # Create mock LIVE
        self.live_dir = self.sc_root / 'LIVE'
        self.live_dir.mkdir()
        (self.live_dir / 'Data.p4k').write_bytes(b'p4k_data_mock' * 100)
        (self.live_dir / 'build_manifest.id').write_text(json.dumps({
            'Data': {
                'Branch': 'sc-alpha-4.10.2',
                'BuildId': 'mock-build-live',
                'BuildDateStamp': 'Mon Oct 12 2026',
                'RequestedP4ChangeNum': '12913470',
                'Version': '4.10.197.2878'
            }
        }), encoding='utf-8')

        # Create mock actionmaps.xml
        controls_dir = self.live_dir / 'user' / 'client' / '0' / 'Profiles' / 'default'
        controls_dir.mkdir(parents=True)
        self.actionmaps = controls_dir / 'actionmaps.xml'
        self.actionmaps.write_text('<ActionMaps version="1"><actionmap name="seat_general"/></ActionMaps>', encoding='utf-8')

        # Create mock custom character (.chf)
        chars_dir = self.live_dir / 'user' / 'client' / '0' / 'CustomCharacters'
        chars_dir.mkdir(parents=True)
        self.mock_char = chars_dir / 'pilot_appearance.chf'
        self.mock_char.write_bytes(b'chf_binary_mesh_data')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_inspect_channel(self):
        info = inspect_channel(self.live_dir)
        self.assertTrue(info['exists'])
        self.assertTrue(info['has_p4k'])
        self.assertEqual(info['version'], '4.10.197.2878')
        self.assertEqual(info['change_num'], 12913470)
        self.assertTrue(info['has_controls'])
        self.assertEqual(info['character_count'], 1)
        self.assertEqual(info['character_names'], ['pilot_appearance.chf'])

    def test_backup_and_restore_controls(self):
        # Backup
        res = backup_control_mappings(self.live_dir)
        self.assertTrue(res['success'])
        self.assertEqual(res['character_count'], 1)
        backup_path = Path(res['backup_path'])
        self.assertTrue((backup_path / 'actionmaps.xml').is_file())
        self.assertTrue((backup_path / 'CustomCharacters' / 'pilot_appearance.chf').is_file())

        # Modify original & delete original character
        self.actionmaps.write_text('<Modified/>', encoding='utf-8')
        self.assertEqual(self.actionmaps.read_text(encoding='utf-8'), '<Modified/>')
        self.mock_char.unlink()
        self.assertFalse(self.mock_char.exists())

        # Restore
        restore_res = restore_control_mappings(self.live_dir)
        self.assertTrue(restore_res['success'])
        self.assertEqual(restore_res['character_count'], 1)
        self.assertIn('seat_general', self.actionmaps.read_text(encoding='utf-8'))
        self.assertTrue(self.mock_char.exists())
        self.assertEqual(self.mock_char.read_bytes(), b'chf_binary_mesh_data')

    def test_get_patch_status(self):
        status = get_patch_status(self.sc_root)
        self.assertEqual(status['root'], self.sc_root)
        self.assertTrue(status['live']['exists'])
        self.assertFalse(status['ptu']['exists'])
        self.assertFalse(status['rc_detected'])

    def test_rc_detection_when_ptu_ahead(self):
        ptu_dir = self.sc_root / 'PTU'
        ptu_dir.mkdir()
        (ptu_dir / 'Data.p4k').write_bytes(b'newer_p4k')
        (ptu_dir / 'build_manifest.id').write_text(json.dumps({
            'Data': {
                'Branch': 'sc-alpha-4.11.0',
                'BuildId': 'mock-build-ptu',
                'RequestedP4ChangeNum': '13000000',
                'Version': '4.11.0.9999'
            }
        }), encoding='utf-8')

        status = get_patch_status(self.sc_root)
        self.assertTrue(status['ptu']['exists'])
        self.assertTrue(status['rc_detected'])
        self.assertIn('4.11.0.9999', status['rc_status_text'])

    def test_seed_ptu_from_live(self):
        seed_res = seed_ptu_from_live(self.sc_root, check_processes=False)
        self.assertTrue(seed_res['success'])
        ptu_dir = self.sc_root / 'PTU'
        self.assertTrue(ptu_dir.is_dir())
        self.assertTrue((ptu_dir / 'Data.p4k').is_file())
        self.assertEqual((ptu_dir / 'Data.p4k').read_bytes(), (self.live_dir / 'Data.p4k').read_bytes())

    def test_deploy_ptu_to_live_swap(self):
        ptu_dir = self.sc_root / 'PTU'
        ptu_dir.mkdir()
        (ptu_dir / 'Data.p4k').write_bytes(b'ptu_final_release_candidate')
        (ptu_dir / 'build_manifest.id').write_text(json.dumps({
            'Data': {
                'Branch': 'sc-alpha-4.10.3',
                'RequestedP4ChangeNum': '12999999',
                'Version': '4.10.3.0001'
            }
        }), encoding='utf-8')

        # Deploy PTU to LIVE
        deploy_res = deploy_ptu_to_live(self.sc_root, keep_backup=False, check_processes=False)
        self.assertTrue(deploy_res['success'])

        # Now LIVE should have the PTU files
        live_info = inspect_channel(self.live_dir)
        self.assertEqual(live_info['version'], '4.10.3.0001')
        self.assertEqual((self.live_dir / 'Data.p4k').read_bytes(), b'ptu_final_release_candidate')

        # Controls and custom character should have been preserved and restored into the new LIVE
        restored_controls = self.live_dir / 'user' / 'client' / '0' / 'Profiles' / 'default' / 'actionmaps.xml'
        self.assertTrue(restored_controls.is_file())
        self.assertIn('seat_general', restored_controls.read_text(encoding='utf-8'))

        restored_char = self.live_dir / 'user' / 'client' / '0' / 'CustomCharacters' / 'pilot_appearance.chf'
        self.assertTrue(restored_char.is_file())
        self.assertEqual(restored_char.read_bytes(), b'chf_binary_mesh_data')


if __name__ == '__main__':
    unittest.main()
