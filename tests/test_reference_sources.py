import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from reference_sources import installed_version,normalize_annotations,normalize_hardware,refresh,active_annotations,apply_annotations

A='11111111-2222-3333-4444-555555555555'
B='22222222-2222-3333-4444-555555555555'
POOL='33333333-2222-3333-4444-555555555555'
MISSION='44444444-2222-3333-4444-555555555555'
BUILD='55555555-2222-3333-4444-555555555555'
VERSION='4.10.2-live.12913470'


def fixtures():
    blueprints=dict(version=VERSION,meta=dict(totalBlueprints=2),blueprints=[dict(guid=A,isDefault=False),dict(guid=B,isDefault=True)])
    merged=dict(version=VERSION,blueprintPools={POOL:dict(blueprints=[dict(blueprintRecord=A,weight=1)])},contracts=[
        dict(id=MISSION,title='Mission',contractorName='Faction',availableSystems=['Pyro'],minStanding=dict(name='Neutral'),blueprintRewards=[dict(blueprintPool=POOL,chance=1,trigger='complete')])])
    mods=dict(instability=0,optimalChargeWindowSize=0,optimalChargeRate=0,resistance=0,filter=0,shatterDamage=0,catastrophicChargeRate=0,clusterFactor=0)
    raw=dict(version=VERSION,lasers=[dict(name='Laser',size=1,vehicleBuiltIn=None,miningBeam=dict(damagePerSecond=100,fullDamageRange=10,zeroDamageRange=20),extractionBeam=dict(damagePerSecond=50),moduleSlots=1,throttleMinimum=.1,modifiers=mods)],
             modules=[dict(name='Module',type='passive',miningDamageMultiplier=1.25,extractionMultiplier=.85,modifiers=mods)],gadgets=[dict(name='Gadget',modifiers=mods)])
    known=dict(lasers=[dict(id='laser',name='Laser',size=1)],modules=[dict(id='module',name='Module',active=False)],gadgets=[dict(id='gadget',name='Gadget')])
    return blueprints,merged,raw,known


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.game=self.base/'LIVE';self.game.mkdir();self.profile=self.base/'profile'
        self.build=dict(BuildId=BUILD,Branch='sc-alpha-4.10.2',RequestedP4ChangeNum='12913470',Tag='public')
        (self.game/'build_manifest.id').write_text(json.dumps(dict(Data=self.build)))
        self.blueprints,self.merged,self.raw,self.known=fixtures()
    def tearDown(self):self.temp.cleanup()
    def fetch(self,name,limit=0):
        if name=='versions.json':value=[dict(version=VERSION,file='ignored.json')]
        else:value={'crafting_blueprints':self.blueprints,'merged':self.merged,'mining_equipment':self.raw}[name.split('-4.10.2')[0]]
        return copy.deepcopy(value),hashlib.sha256(json.dumps(value).encode()).hexdigest()
    def test_version_requires_exact_build_and_separates_live_from_ptu(self):
        self.assertEqual(installed_version(self.game),(VERSION,BUILD))
        self.game.rename(self.base/'PTU');self.game=self.base/'PTU'
        self.assertEqual(installed_version(self.game)[0],'4.10.2-ptu.12913470')
        result=refresh(self.profile,self.game,self.fetch,self.known)
        self.assertEqual(result['status'],'not_published');self.assertFalse((self.profile/'reference_source_current.json').exists())
    def test_reward_pool_and_default_status_match_blueprint_guid(self):
        value=normalize_annotations(self.blueprints,self.merged,100,VERSION)
        self.assertEqual(value['blueprints'][A]['sources'],[0]);self.assertEqual(value['blueprints'][B]['sources'],[])
        self.assertTrue(value['blueprints'][B]['known_from_start']);self.assertEqual(value['missions'][0]['chance'],100)
    def test_zero_chance_zero_weight_and_acceptance_rewards_are_distinct(self):
        reward=self.merged['contracts'][0]['blueprintRewards'][0];reward['trigger']='accept'
        self.assertIn('on acceptance',normalize_annotations(self.blueprints,self.merged,100,VERSION)['missions'][0]['title'])
        reward['chance']=0;self.assertEqual(normalize_annotations(self.blueprints,self.merged,100,VERSION)['missions'],[])
        reward['chance']=1;self.merged['blueprintPools'][POOL]['blueprints'][0]['weight']=0
        self.assertEqual(normalize_annotations(self.blueprints,self.merged,100,VERSION)['missions'],[])
    def test_hardware_factors_are_not_mistaken_for_percentages(self):
        value=normalize_hardware(self.raw,self.known)
        self.assertEqual(value['modules'][0]['power'],1.25);self.assertAlmostEqual(value['modules'][0]['extraction'],-15)
        self.assertEqual(value['lasers'][0]['fracture'],100)
    def test_built_in_same_named_laser_does_not_replace_swappable_variant(self):
        other=copy.deepcopy(self.raw['lasers'][0]);other['vehicleBuiltIn']='MPUV';other['miningBeam']['damagePerSecond']=999
        self.raw['lasers'].append(other)
        self.assertEqual(normalize_hardware(self.raw,self.known)['lasers'][0]['fracture'],100)
        other['vehicleBuiltIn']=None
        with self.assertRaises(ValueError):normalize_hardware(self.raw,self.known)
    def test_unknown_slots_and_missing_reward_pools_reject_import(self):
        self.raw['lasers'][0]['moduleSlots']=4
        with self.assertRaises(ValueError):normalize_hardware(self.raw,self.known)
        self.merged['blueprintPools']={}
        with self.assertRaises(ValueError):normalize_annotations(self.blueprints,self.merged,100,VERSION)
    def test_complete_reference_generation_and_overlay_preserve_recipes(self):
        state=refresh(self.profile,self.game,self.fetch,self.known);self.assertEqual(state['status'],'applied')
        catalog=dict(native_provenance=dict(build=self.build),missions=[],blueprints=[dict(native_id=A,sources=[],slots=['unchanged recipe'])])
        self.assertEqual(apply_annotations(catalog,self.profile),1);self.assertEqual(catalog['blueprints'][0]['slots'],['unchanged recipe'])
        self.assertEqual(catalog['missions'][0]['title'],'Mission')
        self.assertIsNone(active_annotations(dict(BuildId=B),self.profile))
    def test_mismatched_resource_and_failed_fetch_retain_last_working_generation(self):
        refresh(self.profile,self.game,self.fetch,self.known);before=(self.profile/'reference_source_current.json').read_bytes()
        self.merged['version']='4.10.3-ptu.1'
        with self.assertRaises(ValueError):refresh(self.profile,self.game,self.fetch,self.known)
        self.assertEqual((self.profile/'reference_source_current.json').read_bytes(),before)
    def test_corrupt_reference_file_cannot_override_local_catalog(self):
        refresh(self.profile,self.game,self.fetch,self.known)
        pointer=json.loads((self.profile/'reference_source_current.json').read_text());folder=self.profile/'directory_sources'/pointer['generation']
        (folder/'sources.json').write_text('{}')
        self.assertIsNone(active_annotations(self.build,self.profile))
    def test_incomplete_blueprint_export_is_not_applied(self):
        self.blueprints['meta']['totalBlueprints']=3
        with self.assertRaises(ValueError):normalize_annotations(self.blueprints,self.merged,100,VERSION)


if __name__=='__main__':unittest.main()
