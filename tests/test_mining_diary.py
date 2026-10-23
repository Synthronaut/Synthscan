import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from mining_diary import MiningDiary, share_text, render_card

class MiningDiaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.diary=MiningDiary(self.root)
    def tearDown(self):self.diary.close();self.temp.cleanup()
    def observation(self,key='rock-1',at=100,**extra):
        return dict(id=key,at=at,settled=True,mass_kg=98000,material='Quantanium',system='Stanton',location='Wala',ship='MOLE',patch='4.10.2',**extra)
    def manual(self,kind='haul',**extra):
        fields=dict(kind=kind,material='Gold',scu=100,mass_kg=50000,proceeds=123400,quality=800,system='Stanton',location='Wala',patch='4.10.2')
        fields.update(extra);return self.diary.save(fields)
    def test_hundred_frames_one_encounter_and_no_inferred_haul(self):
        for i in range(100):self.diary.observe(self.observation(at=100+i))
        self.assertEqual(len(self.diary.entries()),1)
        self.assertEqual(self.diary.get('rock-1')['observations'],100)
        records=self.diary.view()['records']
        self.assertEqual(records[0]['value'],'98,000 kg')
        self.assertEqual(records[2]['value'],'No record yet')
        self.assertEqual(records[4]['value'],'No record yet')
    def test_only_complete_composition_establishes_quality(self):
        parts=[dict(material='Quantanium',percent=10,quality=900),dict(material='',percent=90,quality=0,inert=True)]
        self.diary.observe(self.observation(parts=parts))
        self.assertNotIn('quality',self.diary.get('rock-1'))
        self.diary.observe(self.observation(at=101,parts=parts,composition_complete=True))
        self.assertEqual(self.diary.get('rock-1')['quality'],900)
    def test_confirmation_and_corrections_survive_more_observations(self):
        self.diary.observe(self.observation())
        self.diary.save(dict(id='rock-1',kind='mined',mass_kg=97000,notes='Crew effort'))
        self.diary.observe(self.observation(at=101))
        e=self.diary.get('rock-1');self.assertEqual(e['kind'],'mined');self.assertEqual(e['mass_kg'],97000)
        self.assertEqual(self.diary.view()['records'][1]['value'],'97,000 kg')
        self.assertEqual(self.diary.view()['records'][2]['value'],'No record yet')
    def test_deleted_auto_encounter_does_not_reappear(self):
        self.diary.observe(self.observation());self.diary.delete('rock-1');self.diary.observe(self.observation(at=101))
        self.assertEqual(self.diary.entries(),[])
    def test_invalid_values_never_create_records(self):
        for value in ['NaN','inf',-10]:
            with self.assertRaises(ValueError):self.manual(mass_kg=value)
        with self.assertRaises(ValueError):self.manual(quality=1001)
        with self.assertRaises(ValueError):self.manual(occurred_at='2026-10-21T12:00:00')
        with self.assertRaises(ValueError):self.manual('sale',proceeds=None)
        self.assertEqual(self.diary.entries(),[])
    def test_command_replay_after_restart_is_idempotent(self):
        c=dict(id='user-click-1',action='diary_save',entry=dict(kind='haul',material='Gold',scu=50))
        result=self.diary.execute(c);self.diary.close();self.diary=MiningDiary(self.root)
        self.assertEqual(self.diary.execute(c),result);self.assertEqual(len(self.diary.entries()),1)
    def test_filters_record_groups_and_patch_boundaries(self):
        self.manual('haul',scu=10);self.manual('haul',scu=1000,system='Pyro');self.manual('haul',scu=200,patch='4.9')
        self.manual('scanned',mass_kg=999999)
        view=self.diary.view(query='Gold',system='Stanton',patch='4.10.2')
        self.assertEqual(view['records'][2]['value'],'10 SCU');self.assertEqual(view['count'],2)
        self.assertEqual(self.diary.view(query='Wala',mode='Haul SCU')['rows'][0]['entry']['scu'],1000)
        self.assertEqual(self.diary.view(query='no-such-location')['count'],0)
    def test_merge_keeps_max_mass_and_does_not_sum_scans(self):
        self.diary.observe(self.observation('a'));self.diary.observe(self.observation('b'))
        merged=self.diary.merge(['a','b']);self.assertEqual(merged['mass_kg'],98000)
        self.diary.observe(self.observation('b',at=101));self.assertEqual(len(self.diary.entries()),1)
        haul=self.manual()
        with self.assertRaises(ValueError):self.diary.merge(['a',haul['id']])
    def test_share_is_allowlisted_and_optional_details_are_opt_in(self):
        entry=self.manual('sale',crew='CrewSecret',notes='NoteSecret')
        entry.update(account_id='AccountSecret',ip='IPSecret',shard_id='ShardSecret',coordinates='CoordinateSecret',screenshot='PathSecret')
        public=share_text(entry,{})
        for secret in ['CrewSecret','NoteSecret','AccountSecret','IPSecret','ShardSecret','CoordinateSecret','PathSecret','Wala','123,400']:self.assertNotIn(secret,public)
        chosen=share_text(entry,dict(crew=True,notes=True,location=True,value=True,name='Captain Example'))
        for selected in ['CrewSecret','NoteSecret','Wala','123,400','Captain Example']:self.assertIn(selected,chosen)
        self.assertIn('Player-entered / confirmed',public)
    def test_card_renders_locally_with_selected_photo_and_no_metadata(self):
        photo=self.root/'photo.jpg';Image.new('RGB',(640,360),'purple').save(photo)
        e=self.manual(screenshot=str(photo),notes='Long story '*30)
        target=self.root/'exports/card.png';render_card(e,target,dict(screenshot=True,notes=True))
        with Image.open(target) as image:
            self.assertEqual(image.width,1080);self.assertGreater(image.height,500);self.assertNotIn('exif',image.info)
    def test_partial_composition_and_duplicate_timestamp_do_not_inflate_counts(self):
        o=self.observation(parts=[dict(material='Gold',quality=999,percent=1)],composition_complete=True)
        self.diary.observe(o);self.diary.observe(o)
        self.assertNotIn('quality',self.diary.get('rock-1'));self.assertEqual(self.diary.get('rock-1')['observations'],1)
    def test_paging_keeps_complete_personal_records(self):
        for i in range(205):self.manual('haul',scu=i+1)
        view=self.diary.view(offset=200);self.assertEqual(view['count'],205);self.assertEqual(len(view['rows']),5)
        self.assertEqual(view['records'][2]['value'],'205 SCU')
    def test_story_only_trip_does_not_award_a_haul_record(self):
        entry=self.diary.save(dict(kind='trip',title='An evening scouting Wala',notes='The crew had a good time.'))
        self.assertEqual(entry['kind'],'trip');self.assertEqual(self.diary.view()['records'][2]['value'],'No record yet')

class DiaryBridgeTests(unittest.TestCase):
    def test_native_inbox_and_user_commands_flow_to_view(self):
        from native_bridge import SessionService
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=root/'Game.log';log.write_text('')
            folder=root/'diary_inbox';folder.mkdir();path=folder/'encounter.json'
            path.write_text(json.dumps(dict(id='encounter',at=100,settled=True,mass_kg=98000,material='Quantanium')),encoding='utf-8')
            service=SessionService(root,log)
            try:
                state=service.tick(False);self.assertFalse(path.exists());self.assertEqual(state['diary']['count'],1)
                service.command(dict(id='save',action='diary_save',entry=dict(id='encounter',kind='mined',notes='A team effort')))
                state=service.tick(False);self.assertEqual(state['diary']['records'][1]['value'],'98,000 kg')
                service.command(dict(id='bad',action='diary_save',entry=dict(kind='haul',material='Gold',scu=-1)))
                self.assertTrue(service.tick(False)['diary_result']['error'])
            finally:service.close()
