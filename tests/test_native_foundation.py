"""Native foundation services: temporary profiles and simulated launch states."""
import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from native_control import RecoveryPolicy
from native_workspace_data import migrate,plan_rows
from native_bridge import SessionService
from telemetry_core import utc_iso

class NativeRecoveryTests(unittest.TestCase):
    def test_failed_initialization_retries_then_stops(self):
        p=RecoveryPolicy()
        self.assertTrue(p.update({1},False,False,now=100))
        self.assertFalse(p.update({1},False,False,now=102))
        self.assertTrue(p.update({1},False,False,now=105))
        self.assertTrue(p.update({1},False,False,now=120))
        self.assertFalse(p.update({1},False,False,now=200))
        self.assertTrue(p.update({2},False,False,now=300))

    def test_readiness_and_voluntary_exit_are_distinct_from_spawn(self):
        p=RecoveryPolicy();self.assertTrue(p.update({1},False,False,now=100))
        self.assertFalse(p.update({1},True,False,now=101))
        self.assertFalse(p.update({1},True,True,now=102))
        self.assertFalse(p.update({1},False,False,quit_at=103,now=104))
        self.assertFalse(p.update({1},False,False,quit_at=103,now=200))
        self.assertTrue(p.update({2},False,False,quit_at=103,now=300))

    def test_already_running_app_and_later_user_quit(self):
        p=RecoveryPolicy();self.assertFalse(p.update({1},True,True,now=100))
        self.assertFalse(p.update({1},False,False,quit_at=105,now=106))

    def test_crash_after_readiness_can_recover(self):
        p=RecoveryPolicy();p.update({1},False,False,now=100);p.update({1},True,True,now=101)
        self.assertTrue(p.update({1},False,False,now=110))
        self.assertFalse(p.update(set(),False,False,now=111))

    def test_repeated_short_lived_ready_processes_do_not_reset_retry_budget(self):
        p=RecoveryPolicy()
        for at in [100,110,130]:
            self.assertTrue(p.update({1},False,False,now=at))
            self.assertFalse(p.update({1},True,True,now=at+1))
        self.assertFalse(p.update({1},False,False,now=200))

class NativeProfileTests(unittest.TestCase):
    def test_import_is_copy_only_idempotent_and_preserves_unknown_records(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();dest=Path(d)/'native'
            owned={'Unknown old blueprint':{'source':'pre-wipe log','name':'Unknown old blueprint'}}
            original=json.dumps(owned).encode();(root/'blueprints_library.json').write_bytes(original)
            report=migrate(dest,root)
            self.assertEqual((root/'blueprints_library.json').read_bytes(),original)
            self.assertEqual((dest/'legacy/blueprints_library.json').read_bytes(),original)
            self.assertFalse((dest/'owned_blueprints.txt').exists())
            self.assertEqual(migrate(dest,root),report)

    def test_corrupt_player_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();(root/'inventory.json').write_text('{broken')
            with self.assertRaises(ValueError):migrate(Path(d)/'native',root)
            self.assertEqual((root/'inventory.json').read_text(),'{broken')

    def test_material_picker_reports_configured_weights_and_secondaries(self):
        rows=plan_rows(['Taranite'])
        self.assertTrue(rows)
        self.assertIn('not measured live spawn rates',rows[0]['detail'])
        self.assertIn('secondaries',rows[0]['detail'])
        self.assertEqual(plan_rows(['unobtainium-does-not-exist']),[])

class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
        self.log=self.root/'Game.log'
        self.log.write_text(f'<{utc_iso(100)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[pub_use1b_100_020]\n')
        self.service=SessionService(self.root,self.log)
        self.patches=[patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None)]
        for p in self.patches:p.start()
    def tearDown(self):
        self.service.close()
        for p in self.patches:p.stop()
        self.directory.cleanup()
    def test_real_log_reader_feeds_native_session_model_and_clears_on_exit(self):
        state=self.service.tick(True,101)
        self.assertEqual(state['full_shard_id'],'pub_use1b_100_020')
        self.assertEqual(state['shard_name'],'Shard 020')
        self.assertIn('FIRST VISIT',state['summary'])
        self.assertEqual(state['metrics'],[])
        self.assertNotIn('server_fps',state)
        self.assertTrue(state['session_rows'])
        stopped=self.service.tick(False,102)
        self.assertIsNone(stopped['session_token'])
        self.assertEqual(stopped['summary'],'Game closed')

    def test_current_join_required_for_name_and_cooldown_commands(self):
        state=self.service.tick(True,101);token=state['session_token']
        with self.assertRaises(ValueError):self.service.command(dict(id='old',action='name',session_token='old',name='Wrong'))
        self.service.command(dict(id='name',action='name',session_token=token,name='My shard'))
        self.service.command(dict(id='cd',action='cooldown',session_token=token,label='Components',minutes=60))
        updated=self.service.tick(True,102)
        self.assertIn('MY SHARD',updated['summary']);self.assertEqual(updated['cooldowns'][0]['label'],'Components')
        self.service.command(dict(id='diary-filter',action='diary_view',query='Gold'))
        self.service.command(dict(id='cd',action='cooldown',session_token=token,label='Duplicate',minutes=60))
        self.assertEqual(len(self.service.history.active_cooldowns()),1)

    def test_initial_log_catchup_does_not_recount_intermediate_historical_joins(self):
        from telemetry_core import ShardHistory
        profile=self.root/'replay';profile.mkdir()
        history=ShardHistory(profile/'shard_history.json')
        history.observe_shard('use1b','020',full_shard_id='pub_use1b_100_020',join_token='previous:100')
        history.leave_current()
        path=self.root/'large.log'
        join=lambda at:f'<{utc_iso(at)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[pub_use1b_100_020]\n'
        path.write_text(join(100)+'padding\n'*160000+f'<{utc_iso(200)}> Connection closed\n')
        service=SessionService(profile,path)
        try:
            state=service.tick(True,201)
            self.assertIsNone(state['session_token'])
            self.assertEqual(service.history.shards['pub_use1b_100_020']['visits'],1)
            self.assertEqual(service.reader.last_pos,path.stat().st_size)
        finally:service.close()

    def test_relaunch_catches_up_old_log_before_publishing_current_shard(self):
        self.service.tick(True,101)
        self.service.tick(False,102)
        # A process may appear before it has replaced the previous run's log.
        self.log.write_text(self.log.read_text()+'padding\n'*160000+f'<{utc_iso(200)}> Connection closed\n')
        state=self.service.tick(True,201)
        self.assertIsNone(state['session_token'])
        self.assertEqual(self.service.history.shards['pub_use1b_100_020']['visits'],1)
        self.assertEqual(self.service.reader.last_pos,self.log.stat().st_size)

    def test_reader_generation_change_does_not_create_another_visit(self):
        from telemetry_core import ShardHistory
        path=self.root/'generations.json'
        h=ShardHistory(path)
        h.observe_shard('use1b','020',full_shard_id='pub_use1b_100_020',join_token='2:pub_use1b_100_020:100.000')
        h.leave_current()
        h=ShardHistory(path)
        h.observe_shard('use1b','020',full_shard_id='pub_use1b_100_020',join_token='0:pub_use1b_100_020:100.000')
        self.assertEqual(h.shards['pub_use1b_100_020']['visits'],1)
        h.observe_shard('use1b','020',full_shard_id='pub_use1b_100_020',join_token='0:pub_use1b_100_020:100.200')
        self.assertEqual(h.shards['pub_use1b_100_020']['visits'],2)

if __name__=='__main__':unittest.main()
