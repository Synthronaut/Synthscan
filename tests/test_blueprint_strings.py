import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from blueprint_strings import BlueprintTextSync, annotate_blueprint_text, native_owned_names, sync_blueprint_text


class BlueprintStringsTests(unittest.TestCase):
    def test_multiple_pools_update_names_titles_and_preserve_other_strings(self):
        original = ('\ufeffFaction=Adagio Holdings (249 / 800)\r\n'
            'Mission_Title_001,P=<EM4>[BP]</EM4> Mission\r\n'
            'Mission_Desc_001=Original mission details\\n<EM4>Reputation Awarded:</EM4> 4,000'
            '\\n<EM4>Multiple Blueprint Pools</EM4>\\n<EM4>Pool 1</EM4>\\n- Bellator Jacket'
            '\\n<EM4>Pool 2</EM4>\\n- LH86 Pistol\\n- F55 LMG\\n\r\nOther=Unchanged\r\n')
        result, stats = annotate_blueprint_text(original, {'LH86 Pistol', 'Bellator Jacket'})
        self.assertIn('Faction=Adagio Holdings (249 / 800)\r\n', result)
        self.assertIn('[BP: 1 LEFT]', result)
        self.assertIn('- [OWNED] LH86 Pistol', result)
        self.assertIn('- [OWNED] Bellator Jacket', result)
        self.assertIn('- [  ] F55 LMG', result)
        self.assertIn('<EM4>Reputation Awarded:</EM4> 4,000', result)
        self.assertTrue(result.startswith('\ufeff'))
        self.assertEqual(stats['partial_missions'], 1)
        self.assertEqual(annotate_blueprint_text(result, {'LH86 Pistol', 'Bellator Jacket'})[0], result)

    def test_exact_identities_do_not_unlock_other_sizes_or_magazines(self):
        text = ('M_Desc_1=<EM4>Potential Blueprints (Nyx Only)</EM4>\\n'
                '- Singe Cannon (S1)\\n- Singe Cannon (S2)\\n- F55 LMG\\n'
                '- F55 LMG Magazine (150 cap)\\n- HeatSafe (Cooler)\n')
        result, _ = annotate_blueprint_text(text, {'Singe Cannon (S1)', 'F55 LMG', 'Ind/1/B HeatSafe'})
        self.assertIn('- [OWNED] Singe Cannon (S1)', result)
        self.assertIn('- [  ] Singe Cannon (S2)', result)
        self.assertIn('- [  ] F55 LMG Magazine (150 cap)', result)
        self.assertIn('- [OWNED] HeatSafe (Cooler)', result)

    def test_removed_ownership_and_description_after_title(self):
        text = ('m_title_1=[ALL BP OWNED] Test\n'
                'm_desc_1=<EM4>Potential Blueprints</EM4>\\n- [OWNED] LH86 Pistol\n')
        result, _ = annotate_blueprint_text(text, set())
        self.assertIn('m_title_1=[BP] Test', result)
        self.assertIn('- [  ] LH86 Pistol', result)

    def test_long_description_key_and_comma_suffix_find_title(self):
        text = ('Cargo_Description,P=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\n'
                'Cargo_Title=[BP] Cargo\n')
        result, _ = annotate_blueprint_text(text, {'LH86 Pistol'})
        self.assertIn('Cargo_Title=[ALL BP OWNED] Cargo', result)

    def test_non_blueprint_lists_and_native_format_are_left_alone(self):
        text = ('m_desc_1=Instructions\\n- Do a thing\\n<EM4>Potential Blueprints</EM4>'
                '\\n- LH86 Pistol\\nWarning: End of rewards\\n- Another instruction\n'
                'native=<EM4>BLUEPRINTS</EM4>\\n<EM4>• F55 LMG</EM4>\n')
        result, _ = annotate_blueprint_text(text, {'LH86 Pistol'})
        self.assertIn('Instructions\\n- Do a thing', result)
        self.assertIn('Warning: End of rewards\\n- Another instruction', result)
        self.assertIn('native=<EM4>BLUEPRINTS</EM4>\\n<EM4>• F55 LMG</EM4>', result)

    def test_atomic_replace_failure_keeps_original_and_can_retry(self):
        with tempfile.TemporaryDirectory() as d:
            ini = Path(d)/'LIVE/Data/Localization/english/global.ini'
            ini.parent.mkdir(parents=True)
            profile=Path(d)/'profile'
            original = b'\xef\xbb\xbfm_desc_1=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\r\n'
            ini.write_bytes(original)
            import os
            replace=os.replace
            def fail(source,destination):
                if Path(destination).resolve()==ini.resolve():raise PermissionError('locked')
                return replace(source,destination)
            with patch('game_text_lifecycle.os.replace', side_effect=fail):
                with self.assertRaises(PermissionError):
                    sync_blueprint_text(ini, {'LH86 Pistol'}, profile)
            self.assertEqual(ini.read_bytes(), original)
            self.assertEqual(list(Path(d).glob('*.tmp')), [])
            self.assertTrue(sync_blueprint_text(ini, {'LH86 Pistol'}, profile)['changed'])
            stamp = ini.stat().st_mtime_ns
            self.assertFalse(sync_blueprint_text(ini, {'LH86 Pistol'}, profile)['changed'])
            self.assertEqual(ini.stat().st_mtime_ns, stamp)
            self.assertEqual(next(profile.rglob('*-original.bin')).read_bytes(), original)
            self.assertFalse(list(ini.parent.glob('*.bak')))

    def test_native_library_manual_denials_and_truncated_save(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'owned.txt'
            path.write_text('owned\tstamp\tLH86 Pistol\tlog\nnot-owned\tstamp\tlh86 pistol\thand\n')
            self.assertEqual(native_owned_names(path), set())
            path.write_text('owned\tstamp\tLH86 Pis')
            with self.assertRaises(ValueError):
                native_owned_names(path)

    def test_background_startup_unlock_and_restart_repair_without_game(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); profile=root/'profile';profile.mkdir()
            game=root/'LIVE';ini=game/'Data/Localization/english/global.ini';ini.parent.mkdir(parents=True)
            original='Faction=Org (100 / 800)\nm_desc_1=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\n'
            ini.write_text(original)
            library=profile/'owned_blueprints.txt'
            service=BlueprintTextSync(profile,game/'Game.log')
            service.tick(100)  # A missing library must not clear ownership.
            self.assertFalse(json.loads((profile/'blueprint_strings_status.json').read_text())['ok'])
            library.write_text('owned\t2026-10-31\tLH86 Pistol\tlog\n')
            service.tick(104)
            self.assertIn('[OWNED] LH86 Pistol',ini.read_text())
            self.assertIn('Faction=Org (100 / 800)',ini.read_text())
            self.assertTrue(json.loads((profile/'blueprint_strings_status.json').read_text())['ok'])
            # An unexpected external edit must be preserved and surfaced.
            ini.write_text(original)
            service.tick(108)
            self.assertEqual(ini.read_text(),original)
            self.assertFalse(json.loads((profile/'blueprint_strings_status.json').read_text())['ok'])
            BlueprintTextSync(profile,game/'Game.log').tick(112)
            self.assertEqual(ini.read_text(),original)

    def test_channel_ownership_is_not_mixed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);profile=root/'profile';profile.mkdir()
            (profile/'owned_blueprints.txt').write_text('owned\tstamp\tLH86 Pistol\tlog\n')
            (profile/'owned_blueprints_PTU.txt').write_text('# Empty PTU library\n')
            ini=root/'PTU/Data/Localization/english/global.ini';ini.parent.mkdir(parents=True)
            ini.write_text('m_desc_1=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\n')
            BlueprintTextSync(profile,root/'PTU/Game.log').tick(100)
            self.assertIn('[  ] LH86 Pistol',ini.read_text())

    def test_powerplant_radar_fuel_nozzle_and_base_armor_matching(self):
        text = ('M_Desc_1=<EM4>Potential Blueprints</EM4>\\n'
                '- Endurance (Powerplant)\\n'
                '- Sunflare (Radar)\\n'
                '- S3 Fuel Nozzle (Fuel Nozzle)\\n'
                '- Venture Arms Base (Armor)\\n'
                '- Argus Helmet Base (Armor)\n'
                'M_Title=[BP] Test Mission\n')
        # User owns Endurance, Sunflare, S3 Fuel Nozzle, Venture Arms, Argus Helmet Base
        owned = {'Ind/1/C Endurance', 'Sunflare', 'Civ/1/A S3 Fuel Nozzle', 'Venture Arms', 'Argus Helmet Base'}
        result, stats = annotate_blueprint_text(text, owned)
        self.assertIn('- [OWNED] Endurance (Powerplant)', result)
        self.assertIn('- [OWNED] Sunflare (Radar)', result)
        self.assertIn('- [OWNED] S3 Fuel Nozzle (Fuel Nozzle)', result)
        self.assertIn('- [OWNED] Venture Arms Base (Armor)', result)
        self.assertIn('- [OWNED] Argus Helmet Base (Armor)', result)
        self.assertIn('M_Title=[ALL BP OWNED] Test Mission', result)
        self.assertEqual(stats['complete_missions'], 1)

    def test_complex_mission_title_resolution(self):
        # 1. Truncate suffix: covalex_haulcargo_atob_desc_deliverall -> covalex_haulcargo_atob_title
        # 2. Name ending: rain_collectresources_multiple_gen_desc_01 -> rain_collectresources_multiple_gen_name_01
        # 3. Middle qualifier: vaughn_eliminatespecific_fps_rockcracker_maintenance_desc_001 -> vaughn_eliminatespecific_fps_rockcracker_title_001
        text = ('covalex_haulcargo_atob_title=[BP] Covalex Mission\n'
                'covalex_haulcargo_atob_desc_deliverall=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\n'
                'rain_collectresources_multiple_gen_name_01=[BP] Rain Mission\n'
                'rain_collectresources_multiple_gen_desc_01=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\\n- F55 LMG\n'
                'vaughn_eliminatespecific_fps_rockcracker_title_001=[BP] Vaughn Mission\n'
                'vaughn_eliminatespecific_fps_rockcracker_maintenance_desc_001=<EM4>Potential Blueprints</EM4>\\n- LH86 Pistol\n')
        result, stats = annotate_blueprint_text(text, {'LH86 Pistol'})
        self.assertIn('covalex_haulcargo_atob_title=[ALL BP OWNED] Covalex Mission', result)
        self.assertIn('rain_collectresources_multiple_gen_name_01=[BP: 1 LEFT] Rain Mission', result)
        self.assertIn('vaughn_eliminatespecific_fps_rockcracker_title_001=[ALL BP OWNED] Vaughn Mission', result)
        self.assertEqual(stats['complete_missions'], 2)
        self.assertEqual(stats['partial_missions'], 1)


if __name__ == '__main__':
    unittest.main()
