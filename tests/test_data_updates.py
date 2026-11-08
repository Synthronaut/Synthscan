import copy
from concurrent.futures import Future
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from data_updates import DataUpdateService,download,check_scmdb,status_lines,local_reference_status,version_key,feed_entries
from reference_catalogs import NAMES,catalogue_path,publish_catalogues
from executive_hangar import HangarScheduleService
from hangar_verification import HangarVerification
from hangar_card import HangarPublisher

ROOT=Path(__file__).resolve().parents[1]


class ReferencePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bundle={n:{'value':'old'} for n in NAMES}

    def test_all_catalogues_switch_together_and_previous_generation_is_retained(self):
        old=publish_catalogues(self.root,self.bundle,'a')
        fresh=publish_catalogues(self.root,{n:{'value':'new'} for n in NAMES},'b')
        for name in NAMES:
            self.assertEqual(catalogue_path(self.root,name).parent,fresh)
            self.assertEqual(json.loads((old/name).read_text())['value'],'old')

    def test_patch_change_before_commit_keeps_previous_generation_active(self):
        old=publish_catalogues(self.root,self.bundle,'a')
        def changed():raise RuntimeError('Game changed')
        with self.assertRaises(RuntimeError):publish_catalogues(self.root,{n:{'value':'new'} for n in NAMES},'b',changed)
        self.assertEqual(catalogue_path(self.root,NAMES[0]).parent,old)

    def test_missing_file_and_corrupt_download_never_fall_back_to_old_unverified_files(self):
        folder=publish_catalogues(self.root,self.bundle,'a')
        (folder/NAMES[0]).write_text('corrupt')
        with self.assertRaises(ValueError):catalogue_path(self.root,NAMES[0])
        (folder/NAMES[1]).unlink()
        with self.assertRaises(OSError):catalogue_path(self.root,NAMES[1])

    def test_partial_generation_is_not_published(self):
        with self.assertRaises(ValueError):publish_catalogues(self.root,{NAMES[0]:{}},'a')
        self.assertFalse((self.root/'data/catalogue_current.json').exists())

    def test_pointer_cannot_leave_the_catalogue_directory(self):
        publish_catalogues(self.root,self.bundle,'a')
        pointer=self.root/'data/catalogue_current.json'
        pointer.write_text(json.dumps(dict(generation='../outside',hashes={})))
        with self.assertRaises(ValueError):catalogue_path(self.root,NAMES[0])


class UpdateServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.now=1793808000

    def service(self,checks=None,local=None):
        value=DataUpdateService(self.directory,checks or {'test':Mock(return_value=dict(status='unchanged',revision='a'))},
            local_check=local or (lambda:dict(status='current')))
        self.addCleanup(value.close);return value

    def settle(self,service,now):
        service.tick(now)
        for f in list(service.futures.values()):
            try:f.result(timeout=2)
            except Exception:pass
        return service.tick(now+1)

    def test_first_run_missing_command_is_safe_and_checks_are_not_repeated_each_tick(self):
        check=Mock(return_value=dict(status='unchanged',revision='a'))
        service=self.service({'test':check});state=self.settle(service,self.now)
        self.assertEqual(state['sources']['test']['status'],'unchanged')
        service.tick(self.now+2);check.assert_called_once()

    def test_network_failure_keeps_last_revision_but_never_claims_current(self):
        check=Mock(return_value=dict(status='unchanged',revision='a'))
        service=self.service({'test':check});self.settle(service,self.now)
        check.side_effect=OSError('private response')
        service.tick(self.now+31,force=True)
        try:service.futures['test'].result(timeout=2)
        except OSError:pass
        state=service.tick(self.now+32);row=state['sources']['test']
        self.assertEqual(row['revision'],'a');self.assertEqual(row['status'],'unavailable')
        self.assertEqual(row['last_success_at'],self.now+1)
        self.assertNotIn('private',json.dumps(row))

    def test_manual_check_is_rate_limited_and_survives_window_close(self):
        check=Mock(return_value=dict(status='unchanged',revision='a'))
        service=self.service({'test':check});self.settle(service,self.now)
        command=self.directory/'data_update_command.json'
        command.write_text(json.dumps(dict(id='manual',at=self.now+31)))
        service.tick(self.now+31)
        service.futures['test'].result(timeout=2);service.tick(self.now+32)
        self.assertEqual(check.call_count,2)
        service.tick(self.now+33,force=True);self.assertEqual(check.call_count,2)
        saved=self.service({'test':check});saved.tick(self.now+40);self.assertEqual(check.call_count,2)

    def test_changed_source_is_reported_without_applying_remote_code(self):
        check=Mock(return_value=dict(status='review_required',revision='a'))
        service=self.service({'test':check});self.settle(service,self.now)
        check.return_value=dict(status='review_required',revision='b')
        service.tick(self.now+31,force=True);service.futures['test'].result(timeout=2)
        state=service.tick(self.now+32)
        self.assertTrue(state['sources']['test']['source_changed'])
        self.assertEqual(state['sources']['test']['status'],'review_required')

    def test_local_rebuild_is_deferred_until_game_closes_and_failure_retries_are_bounded(self):
        service=self.service(local=lambda:dict(status='refresh_required'))
        with patch('data_updates.rebuild_references',return_value=1) as rebuild:
            self.assertTrue(service.tick(self.now,game_running=True)['deferred']);rebuild.assert_not_called()
            service.tick(self.now+1,game_running=False);service.refresh_future.result(timeout=2)
            state=service.tick(self.now+2,game_running=False)
            self.assertIn('failed',state['refresh_result']);rebuild.assert_called_once()

    def test_scmdb_website_update_is_never_reported_as_fresh_game_data(self):
        with patch('data_updates.download',return_value=b'<title>SCMDB</title><script src="/assets/index-abc.js"></script>'):
            self.assertEqual(check_scmdb()['status'],'unverified')
        with patch('data_updates.download',return_value=b'<title>Access denied</title>'):
            with self.assertRaises(ValueError):check_scmdb()

    def test_old_snapshot_is_labelled_overdue(self):
        self.settle(self.service(),self.now)
        text=status_lines(self.directory,self.now+86400)
        self.assertIn('check overdue',text);self.assertIn('background status unavailable',text)

    def test_corrupt_status_cannot_stop_monitor_startup_or_the_status_window(self):
        for bad in [[],{'sources':[],'local':[]},{'sources':{'scmdb':{'checked_at':'bad','status':None}}}]:
            with self.subTest(bad=bad):
                (self.directory/'data_update_status.json').write_text(json.dumps(bad))
                self.assertIn('SCMDB',status_lines(self.directory,self.now))
                service=self.service();self.settle(service,self.now);service.close()

    def test_download_rejects_redirects_and_oversized_responses(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.geturl.return_value='https://other.invalid/'
        with self.assertRaises(ValueError):download('https://scmdb.net/',Mock(return_value=response))
        response.geturl.return_value='https://scmdb.net/';response.read.return_value=b'x'*(4*1024*1024+1)
        with self.assertRaises(ValueError):download('https://scmdb.net/',Mock(return_value=response))

    def test_release_order_never_offers_a_downgrade_and_numeric_alpha_versions_sort_correctly(self):
        self.assertGreater(version_key('0.1.0-alpha.10'),version_key('v0.1.0-alpha.8'))
        self.assertGreater(version_key('0.1.0'),version_key('0.1.0-alpha.10'))
        self.assertGreater(version_key('0.2.0-alpha.1'),version_key('0.1.0'))

    def test_unexpected_or_entity_bearing_release_feeds_are_rejected(self):
        for raw in [b'<html>Unavailable</html>',b'<feed xmlns="http://www.w3.org/2005/Atom"/>',b'<!DOCTYPE feed><feed/>']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):feed_entries(raw)


class HangarUpdateReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.now=1793808000
        self.schedule=json.loads((ROOT/'data/executive_hangar_schedule.json').read_text())
        self.reset=dict(ok=True,checked_at=self.now,latest_reset_at=0)

    def service(self,schedule=None,reset=None):
        service=HangarScheduleService(self.directory,schedule or Mock(return_value=self.schedule),reset or Mock(return_value=self.reset))
        self.addCleanup(service.close);return service

    def test_official_resets_refresh_when_timing_website_is_down(self):
        failure=Mock(side_effect=OSError('offline'))
        reset=dict(self.reset,latest_reset_at=self.schedule['anchor_ms']/1000+60)
        service=self.service(failure,Mock(return_value=reset));service.tick(True,self.now)
        for future in (service.future,service.reset_future):
            try:future.result(timeout=2)
            except OSError:pass
        service.tick(True,self.now+1)
        self.assertEqual(service.reset_state()['latest_reset_at'],reset['latest_reset_at'])
        self.assertTrue(service.note)
        verify=HangarVerification(self.directory).evaluate(dict(patch='4.10.2',fingerprint='a',built_on='2026-10-12'),service.schedule,self.now+1,self.now,reset_check=service.reset_state())
        self.assertFalse(verify['community_synced']);self.assertIn('maintenance',verify['reason'])

    def test_reset_cache_survives_restart_and_feed_failure(self):
        service=self.service();service.tick(True,self.now);service.reset_future.result(timeout=2);service.future.result(timeout=2);service.tick(True,self.now+1)
        reloaded=self.service(reset=Mock(side_effect=OSError('offline')))
        self.assertEqual(reloaded.reset_state()['checked_at'],self.now)
        reloaded.tick(True,self.now+301)
        try:reloaded.reset_future.result(timeout=2)
        except OSError:pass
        reloaded.tick(True,self.now+302)
        self.assertFalse(reloaded.reset_state()['ok']);self.assertEqual(reloaded.reset_state()['checked_at'],self.now)

    def test_failed_cache_write_does_not_replace_active_schedule(self):
        newer=dict(self.schedule,anchor_ms=self.schedule['anchor_ms']+60000)
        service=self.service(Mock(return_value=newer));service.tick(True,self.now)
        service.future.result(timeout=2);service.reset_future.result(timeout=2)
        with patch('telemetry_ipc.publish_json',return_value=False):service.tick(True,self.now+1)
        self.assertEqual(service.schedule['anchor_ms'],self.schedule['anchor_ms']);self.assertTrue(service.note)

    def test_missing_reset_feed_and_ptu_are_never_verified_by_live_schedule(self):
        verify=HangarVerification(self.directory);build=dict(patch='4.10.2',fingerprint='a',built_on='2026-10-12')
        self.assertFalse(verify.evaluate(build,self.schedule,self.now,self.now)['community_synced'])
        self.assertFalse(verify.evaluate(dict(build,channel='PTU'),self.schedule,self.now,self.now,reset_check=self.reset)['community_synced'])

    def test_sync_continues_when_another_hud_mode_is_selected(self):
        service=self.service();publisher=HangarPublisher(self.directory,123);publisher.game=None
        publisher.tick(service,False,self.now)
        self.assertIsNotNone(service.future);self.assertIsNotNone(service.reset_future)
        self.assertFalse((self.directory/'hangar_hud.png').exists())
        self.assertTrue((self.directory/'hangar_update_status.json').exists())


class RecipeRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);folder=self.root/'libs/foundry/records/crafting/blueprints'
        folder.mkdir(parents=True);(folder/'recipe.json').write_text('{}')
        self.slot=dict(name='Frame',material='Iron',amount=2,unit='SCU',min_quality=1,effects=[])
        self.item=dict(guid='item-guid',name='Test item',size=1,type='WeaponPersonal',grade='A',manufacturer='TEST',description='Fresh description')
        self.raw=dict(_RecordId_='recipe-guid',_RecordName_='test',_RecordValue_=dict(blueprint=dict(
            processSpecificData=dict(_Type_='CraftingProcess_Creation',entityClass='item'),
            tiers=[dict(recipe=dict(costs=dict(craftTime=dict(days=0,hours=0,minutes=1,seconds=0))))])))
        self.records=Mock(root=self.root);self.records.read.return_value=self.raw;self.records.item.return_value=self.item
        self.base=dict(blueprints=[dict(id='old-id',name='Test item',size=1,slots=[dict(self.slot,amount=1)],sources=[0])],
            materials=[dict(name='Iron')],missions=[dict(title='Retained annotation')])

    def export(self):
        from tools.export_local_blueprints import export
        with patch('tools.export_local_blueprints.slots_for',return_value=[copy.deepcopy(self.slot)]):
            return export(self.records,self.base,dict(Data=dict(BuildId='new-build')))

    def test_changed_quantity_updates_without_changing_reference_identity(self):
        result=self.export();bp=result['blueprints'][0]
        self.assertEqual(bp['slots'][0]['amount'],2);self.assertEqual(bp['id'],'old-id')
        self.assertTrue(bp['native_verified']);self.assertEqual(bp['sources'],[0])

    def test_new_recipe_and_material_are_added_with_unknown_unlock(self):
        self.item['name']='New item';self.slot['material']='New material'
        result=self.export();fresh=next(b for b in result['blueprints'] if b.get('native_id')=='recipe-guid')
        self.assertEqual(fresh['id'],'game:recipe-guid');self.assertEqual(fresh['sources'],[])
        self.assertFalse(fresh['known_from_start']);self.assertTrue(fresh['native_verified'])
        self.assertIn('New material',[m['name'] for m in result['materials']])
        self.assertFalse(result['blueprints'][0]['native_verified'])
        self.assertIn('not verified',result['blueprints'][0]['recipe_source'])

    def test_stable_guid_survives_localized_item_rename(self):
        self.base['blueprints'][0]['native_id']='recipe-guid';self.item['name']='Renamed item'
        self.assertTrue(self.export()['blueprints'][0]['native_verified'])


if __name__=='__main__':unittest.main()
