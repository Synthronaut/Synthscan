import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from performance_lab import snapshot, setting_inventory, summarize_frame_csv, compare_runs, config_values, parse_cvar_group, packaged_setting_evidence


class PerformanceLabTests(unittest.TestCase):
    def test_packaged_evidence_refuses_a_different_game_build(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            path.write_text(json.dumps({'build': {'RequestedP4ChangeNum': '123'}, 'groups': {
                'sys_spec_Shading': {'source': 'shading.cfg', 'sha256': 'test', 'scope': 'static',
                                     'configured_presets': {'1': {'q_ShaderGeneral': '0'}}}}}))
            saved = {'build': {'RequestedP4ChangeNum': '124'}, 'settings': {'SysSpec_Shading': '1'}}
            self.assertIsNone(packaged_setting_evidence(saved, 'SysSpec_Shading', path))
            saved['build']['RequestedP4ChangeNum'] = '123'
            evidence = packaged_setting_evidence(saved, 'SysSpec_Shading', path)
            self.assertEqual(evidence['configured_values']['q_ShaderGeneral'], '0')
            self.assertEqual(evidence['scope'], 'static')

    def test_real_presentmon_26_v1_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'real-header.csv'
            path.write_text('Application,ProcessID,SwapChainAddress,Runtime,SyncInterval,PresentFlags,Dropped,TimeInSeconds,msInPresentAPI,msBetweenPresents,QPCTime\n'
                            'StarCitizen.exe,7292,0x123,DXGI,0,512,0,0.0544,0.278,21.3174,25533097020\n')
            result = summarize_frame_csv(path, 7292)
            self.assertEqual(result['frame_intervals'], 1)
            self.assertAlmostEqual(result['median_ms'], 21.3174)

    def write_frames(self, folder, rows):
        path = Path(folder) / 'frames.csv'
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['ProcessID', 'SwapChainAddress', 'MsBetweenPresents', 'QPCTime'])
            writer.writerows(rows)
        return path

    def test_frame_tails_include_real_stalls_and_separate_swapchains(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [(42, 'main', 10, str(index)) for index in range(990)]
            rows += [(42, 'main', 100, str(index)) for index in range(990, 1000)]
            rows += [(42, 'secondary', 1000, str(index)) for index in range(20)]
            result = summarize_frame_csv(self.write_frames(folder, rows), 42)
            self.assertEqual(result['swap_chain'], 'main')
            self.assertAlmostEqual(result['average_fps'], 1000 / 10.9)
            self.assertEqual(result['one_percent_low_fps'], 10)
            self.assertEqual(result['frames_over_50_ms'], 10)
            self.assertEqual(result['relative_stalls'], 10)

    def test_rejects_invalid_intervals_duplicates_and_other_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [(42, 'main', 20, '1'), (42, 'main', 20, '1'),
                    (42, 'main', 'nan', '2'), (42, 'main', 0, '3'),
                    (42, 'main', -1, '4'), (42, 'main', 20, '5'),
                    (99, 'other', 1, '6')]
            result = summarize_frame_csv(self.write_frames(folder, rows), 42)
            self.assertEqual(result['frame_intervals'], 2)
            self.assertEqual(result['rejected_rows'], 4)
            self.assertEqual(result['average_fps'], 50)
            self.assertTrue(result['warnings'])

    def test_mixed_pids_require_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_frames(folder, [(42, 'a', 10, '1'), (99, 'b', 10, '1')])
            with self.assertRaisesRegex(ValueError, 'multiple process'):
                summarize_frame_csv(path)

    def test_one_second_fps_csv_cannot_masquerade_as_per_frame_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fake.csv'
            path.write_text('time,fps\n1,60\n2,30\n')
            with self.assertRaisesRegex(ValueError, 'PresentMon'):
                summarize_frame_csv(path)

    def test_snapshot_preserves_raw_enums_missing_values_and_override_uncertainty(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            attributes = game / 'user/client/0/Profiles/default/attributes.xml'
            attributes.parent.mkdir(parents=True)
            attributes.write_text('<Attributes><Attr name="SysSpec_PlanetVolumetricClouds" value="1"/>'
                                  '<Attr name="UpscalingTechnique" value="2"/>'
                                  '<Attr name="MouseSensitivity" value="9"/></Attributes>')
            (game / 'USER.cfg').write_text('g_language = english\nsys_spec_PlanetVolumetricClouds = 0\n')
            (game / 'build_manifest.id').write_text(json.dumps({'Data': {'Branch': 'test', 'RequestedP4ChangeNum': '123'}}))
            renderer = game / 'renderer.json'
            renderer.write_text('{"GraphicsSettings":{"GraphicsRenderer":0}}')
            result = snapshot(game, renderer)
            self.assertEqual(result['settings']['UpscalingTechnique'], '2')
            self.assertNotIn('MouseSensitivity', result['settings'])
            self.assertEqual(result['settings']['GraphicsRenderer'], '0')
            self.assertEqual(len(result['potential_overrides']), 1)
            inventory = {row['key']: row for row in setting_inventory(result)}
            self.assertIsNone(inventory['HDR']['saved_raw'])
            self.assertFalse(inventory['HDR']['menu_verified'])
            self.assertFalse(result['errors'])

    def run_fixture(self, quality='1', fps=40):
        return {'scene': 'hangar', 'route': 'fixed-pan', 'background_workload': 'Discord stream',
                'driver_version': '617.42', 'game_build': '123', 'runtime_verified': True,
                'frame_generation': False, 'overrides_verified': True,
                'snapshot': {'settings': {'SysSpec_Shading': quality, 'Width': '2560'},
                             'startup_commands': {}, 'potential_overrides': [], 'errors': []},
                'frames': {'average_fps': fps, 'p99_ms': 40, 'one_percent_low_fps': 25}}

    def test_comparison_refuses_scene_and_multiple_setting_changes(self):
        first, second = self.run_fixture(), self.run_fixture('3', 50)
        second['scene'] = 'space'
        second['snapshot']['settings']['Width'] = '1920'
        result = compare_runs(first, second, 'SysSpec_Shading')
        self.assertEqual(result['status'], 'confounded')
        self.assertTrue(any('scene' in issue for issue in result['issues']))
        self.assertTrue(any('exactly' in issue for issue in result['issues']))

    def test_no_generated_frame_or_missing_raw_frame_claims(self):
        first, second = self.run_fixture(), self.run_fixture('3')
        second['frames'] = None
        second['frame_generation'] = None
        second['runtime_verified'] = False
        result = compare_runs(first, second, 'SysSpec_Shading')
        self.assertEqual(result['status'], 'confounded')
        self.assertNotIn('average_fps_change_pct', result)
        self.assertGreaterEqual(len(result['issues']), 3)

    def test_baseline_repeat_reports_drift_instead_of_claiming_small_gain(self):
        first, second, repeated = self.run_fixture(fps=40), self.run_fixture('3', 41), self.run_fixture(fps=42)
        result = compare_runs(first, second, 'SysSpec_Shading', repeated)
        self.assertEqual(result['status'], 'repeated_comparison')
        self.assertAlmostEqual(result['baseline_drift_pct'], 5)
        self.assertIn('does not exceed', result['note'])

    def test_changed_startup_and_unverified_override_prevent_attribution(self):
        first, second = self.run_fixture(), self.run_fixture('3')
        second['snapshot']['startup_commands'] = {'r_VolumetricClouds': '0'}
        second['snapshot']['potential_overrides'] = [{'command': 'r_VolumetricClouds'}]
        second['overrides_verified'] = False
        result = compare_runs(first, second, 'SysSpec_Shading')
        self.assertEqual(result['status'], 'confounded')
        self.assertTrue(any('Startup commands' in issue for issue in result['issues']))
        self.assertTrue(any('overrides' in issue for issue in result['issues']))

    def test_config_comment_and_first_equals_handling(self):
        self.assertEqual(config_values('; comment\n-- comment\nr_Test = a=b\n'), {'r_Test': 'a=b'})

    def test_packaged_presets_inherit_defaults_without_inventing_an_off_level(self):
        text = '[default]\n=3\nr_PlanetVolumetricClouds=1\nsteps=50\nshadows=1\n[1]\nshadows=0\n[2]\nshadows=0\n[4]\nsteps=200\n'
        result = parse_cvar_group(text)
        self.assertNotIn('0', result['configured_presets'])
        self.assertEqual(result['configured_presets']['1']['r_PlanetVolumetricClouds'], '1')
        self.assertEqual(result['configured_presets']['1'], result['configured_presets']['2'])
        self.assertEqual(result['configured_presets']['3']['shadows'], '1')
        self.assertEqual(result['configured_presets']['4']['steps'], '200')

    def test_commented_physics_settings_are_not_reported_as_active_overrides(self):
        result = parse_cvar_group('[default]\n=3\nphysics=100\n[1]\n;physics=50\n[4]\n')
        self.assertEqual(result['section_overrides']['1'], {})
        self.assertEqual(result['configured_presets']['1'], result['configured_presets']['4'])


if __name__ == '__main__':
    unittest.main()
