import unittest
from weapon_stats import extract
from directory_audit import display_name,validate


class Store:
    def value(self,reference):
        if reference!='exact-ammo':raise ValueError('Wrong ammo identity')
        return dict(speed=1196,projectileParams=dict(_Type_='BulletProjectileParams',damage=dict(DamagePhysical=72.99,DamageEnergy=0,DamageDistortion=5)))


def weapon():
    action=dict(_Type_='SWeaponActionFireSingleParams',fireRate=250,launchParams=dict(_Type_='SProjectileLauncher',pelletCount=1,damageMultiplier=1))
    mode=dict(_Type_='SWeaponActionSequenceParams',name='Single',mode='Looping',sequenceEntries=[dict(repetitions=1,unit='RPM',delay=250,weaponAction=action)])
    return dict(Components=[dict(_Type_='SAmmoContainerComponentParams',ammoParamsRecord='exact-ammo'),dict(_Type_='SCItemWeaponComponentParams',fireActions=[mode])])


class WeaponStatsTests(unittest.TestCase):
    def test_direct_hit_alpha_dps_and_distortion_are_separate(self):
        mode=extract(Store(),weapon())['modes'][0]
        self.assertAlmostEqual(mode['alpha'],72.99)
        self.assertAlmostEqual(mode['burst_dps'],304.125)
        self.assertEqual(mode['distortion_alpha'],5)
        self.assertEqual(mode['projectile_speed'],1196)

    def test_pellets_and_multiplier_without_inventing_burst_timing(self):
        raw=weapon();entry=raw['Components'][1]['fireActions'][0]['sequenceEntries'][0]
        entry['weaponAction']['launchParams'].update(pelletCount=4,damageMultiplier=.5)
        entry['repetitions']=3
        mode=extract(Store(),raw)['modes'][0]
        self.assertAlmostEqual(mode['alpha'],145.98)
        self.assertNotIn('burst_dps',mode)

    def test_unresolved_ammo_and_unsupported_launchers_never_guess(self):
        raw=weapon();raw['Components'][0]['ammoParamsRecord']='wrong'
        self.assertEqual(extract(Store(),raw)['status'],'unavailable')
        raw=weapon();raw['Components'][1]['fireActions'][0]['sequenceEntries'][0]['weaponAction']['launchParams']['_Type_']='BeamLauncher'
        self.assertEqual(extract(Store(),raw)['modes'],[])

    def test_gatling_burst_is_full_rate_and_spin_up_is_kept(self):
        raw=weapon();action=raw['Components'][1]['fireActions'][0]['sequenceEntries'][0]['weaponAction']
        action.update(_Type_='SWeaponActionFireRapidParams',spinUpTime=.374)
        mode=extract(Store(),raw)['modes'][0]
        self.assertAlmostEqual(mode['burst_dps'],304.125)
        self.assertEqual(mode['spin_up_seconds'],.374)

    def test_existing_install_rebuilds_older_weapon_export_automatically(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        import json
        from data_updates import local_reference_status
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            (root/'build_manifest.id').write_text(json.dumps(dict(Data=dict(BuildId='build',Branch='4.10.2'))))
            (root/'data/local_game_catalog.json').write_text(json.dumps(dict(native_provenance=dict(build=dict(BuildId='build'),export_schema=2))))
            library=root/'data/local_game_library.json';library.write_text(json.dumps(dict(provenance=dict(build=dict(BuildId='build')))))
            with patch('installation.game_directory',return_value=root),patch('installation.output_root',return_value=root):
                self.assertEqual(local_reference_status()['status'],'refresh_required')
                library.write_text(json.dumps(dict(provenance=dict(build=dict(BuildId='build'),weapon_stats_schema=1))))
                self.assertEqual(local_reference_status()['status'],'current')

    def test_directory_audit_preserves_distinct_item_and_blueprint_identities(self):
        base=dict(id='item',name='10-Series Greatsword Cannon',kind='Component',category='Weapons & ammunition')
        bp=dict(base,id='blueprint',kind='Blueprint')
        self.assertEqual(validate([base,bp])['unique_ids'],2)
        for bad in ['', '  ', '@missing_localization', 'PLACEHOLDER']:
            self.assertFalse(display_name(bad))
            with self.assertRaises(ValueError):validate([dict(base,name=bad)])
        with self.assertRaises(ValueError):validate([base,base])
        with self.assertRaises(ValueError):validate([dict(base,finder_blueprints=[dict(name='Recipe',materials=[dict(amount=float('nan'))])])])


if __name__=='__main__':unittest.main()
