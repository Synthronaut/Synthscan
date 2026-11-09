import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from shard_names import clean_name
from telemetry_core import ShardHistory,IncrementalGameLog,utc_iso
from region_history_hud import recent_visits
from native_session_hud import hud_state

A='pub_use1b_12881860_310'
B='pub_asia1_12881860_310'
class ShardNameTests(unittest.TestCase):
    def test_log_name_validation(self):
        self.assertEqual(clean_name('Triumphant_Penguin'),'TRIUMPHANT PENGUIN')
        for value in ('GAME-7','shard 310','Main Menu','Connecting to',None):
            self.assertIsNone(clean_name(value))

    def test_rejoins_work_without_any_screen_reading_modules(self):
        from native_bridge import SessionService
        unavailable={name:None for name in ('capture_privacy','screen_readers','windows_capture','rapidocr_onnxruntime')}
        with tempfile.TemporaryDirectory() as d,patch.dict('sys.modules',unavailable),patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
            root=Path(d);log=root/'Game.log'
            log.write_text(f'<{utc_iso(100)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[{A}]\n<{utc_iso(101)}> OpenLoadingScreen\n')
            service=SessionService(root,log)
            try:
                first=service.tick(True,102)
                self.assertTrue(first['is_loading_screen'])
                self.assertEqual(first['shard_name'],'Shard 310')
                self.assertIsNone(first['game_shard_name'])
                with log.open('a') as stream:
                    stream.write(f'<{utc_iso(110)}> [Notice] <Join PU> address[192.0.2.2] port[64001] shard[{B}]\n<{utc_iso(111)}> OpenLoadingScreen\n')
                second=service.tick(True,112)
                self.assertEqual(second['full_shard_id'],B)
                self.assertNotEqual(first['session_token'],second['session_token'])
                self.assertIsNone(second['game_shard_name'])
                self.assertEqual(second['shard_name'],'Shard 310')
            finally:service.close()

    def test_history_is_persistent_and_full_identity_scoped(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shard_history.json';h=ShardHistory(path,clock=lambda:100)
            self.assertTrue(h.observe_game_name(A,'Triumphant Penguin','game_log',100))
            self.assertTrue(h.observe_game_name(B,'Curious Otter','loading_screen_ocr',101))
            self.assertTrue(h.observe_game_name(A,'Triumphant Penguin','game_log',200))
            self.assertFalse(h.observe_game_name(A,'Wrong Name','game_log',150))
            self.assertFalse(h.observe_game_name('local_shard','Wrong Name','game_log',102))
            self.assertFalse(h.observe_game_name(A,'Invented Name','generated',102))
            h.set_shard_name('use1b','310','My Label',A)
            h=ShardHistory(path);self.assertEqual(h.get_game_name(A),'TRIUMPHANT PENGUIN')
            self.assertEqual(h.get_game_name(B),'CURIOUS OTTER');self.assertEqual(h.shards[A]['name'],'MY LABEL')
            self.assertIsNone(h.get_game_name(A.replace('12881860','99999999')))

    def test_log_accepts_only_populated_remote_names(self):
        r=IncrementalGameLog(Path('nonexistent-test-log'))
        r._parse_line(f'<{utc_iso(100)}> ShardId[{A}], ShardName[Triumphant Penguin]')
        events=r.drain_events();self.assertEqual(len(events),1);self.assertEqual(events[0]['full_shard_id'],A)
        for text in ('ShardId[local_shard], ShardName[Triumphant Penguin]',f'ShardId[{A}], ShardName[]'):
            r._parse_line(f'<{utc_iso(101)}> '+text)
        self.assertFalse(r.drain_events())

    def test_dropdown_and_ribbon_keep_name_and_number(self):
        snapshot=dict(owner_pid=42,written_at=100,session_token='join',full_shard_id=A,game_shard_name='TRIUMPHANT PENGUIN',shard_name='Shard 310',
                      hud_state=dict(region_raw='use1b'),sessions=[dict(joined_at=utc_iso(100),full_shard_id=A,shard_id='310',
                      server_name='Shard 310',game_shard_name='TRIUMPHANT PENGUIN',active=True),
                      dict(joined_at=utc_iso(90),full_shard_id=B,shard_id='310',game_shard_name='CURIOUS OTTER')])
        rows=recent_visits(snapshot);self.assertEqual(rows[0]['server'],'TRIUMPHANT PENGUIN · Shard 310')
        self.assertEqual(rows[1]['server'],'CURIOUS OTTER · Shard 310')
        self.assertEqual(hud_state(snapshot,42,101)['callsign'],'TRIUMPHANT PENGUIN')

    def test_bridge_updates_current_and_recent_rows_from_profile_cache(self):
        from native_bridge import SessionService
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=root/'Game.log';log.write_text(f'<{utc_iso(100)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[{A}]\n')
            with patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
                service=SessionService(root,log)
                try:
                    service.history.observe_game_name(A,'Triumphant Penguin','game_log',100)
                    state=service.tick(True,101)
                    self.assertEqual(state['game_shard_name'],'TRIUMPHANT PENGUIN')
                    self.assertEqual(state['sessions'][0]['game_shard_name'],'TRIUMPHANT PENGUIN')
                    self.assertEqual(service.sessions._get_known_name('use1b','310',A),'TRIUMPHANT PENGUIN')
                finally:service.close()
