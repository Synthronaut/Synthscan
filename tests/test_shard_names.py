import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import Future
from unittest.mock import Mock,patch
from shard_names import clean_name,loading_name,ShardNameCollector
from telemetry_core import ShardHistory,IncrementalGameLog,utc_iso
from region_history_hud import recent_visits
from native_session_hud import hud_state

A='pub_use1b_12881860_310'
B='pub_asia1_12881860_310'
class Executor:
    def __init__(self):self.jobs=[]
    def submit(self,fn):
        f=Future();self.jobs.append((fn,f));return f
    def finish(self,value=None):self.jobs[-1][1].set_result(value)
    def shutdown(self,**kwargs):pass

class ShardNameTests(unittest.TestCase):
    def test_label_confidence_and_ambiguity(self):
        box=lambda s,c=.99:SimpleNamespace(text=s,confidence=c,top=0,left=0)
        self.assertEqual(loading_name([box('Connecting to shard: Triumphant Penguin')]),'TRIUMPHANT PENGUIN')
        self.assertEqual(loading_name([box('SHARD NAME: Triumphant_Penguin')]),'TRIUMPHANT PENGUIN')
        for boxes in ([box('Triumphant Penguin')],[box('Connecting to Main Menu')],[box('Connecting to Triumphant Penguin',.7)],
                      [box('Shard: Triumphant Penguin Shard: Curious Otter')]):
            self.assertIsNone(loading_name(boxes))
        self.assertIsNone(clean_name('GAME-7'));self.assertIsNone(clean_name('shard 310'))

    def test_two_matching_reads_and_no_more_capture(self):
        e=Executor();c=ShardNameCollector(True,lambda:None,e)
        self.assertIsNone(c.tick(A,'join',True,100));e.finish('Triumphant Penguin')
        self.assertIsNone(c.tick(A,'join',True,101));e.finish('Triumphant Penguin')
        result=c.tick(A,'join',True,102)
        self.assertEqual(result['full_shard_id'],A);self.assertEqual(result['name'],'TRIUMPHANT PENGUIN')
        c.tick(A,'join',True,110);self.assertEqual(len(e.jobs),2)

    def test_stale_read_not_assigned_to_next_shard_or_after_loading(self):
        e=Executor();c=ShardNameCollector(True,lambda:None,e)
        c.tick(A,'first',True,100);e.finish('Triumphant Penguin')
        self.assertIsNone(c.tick(B,'second',True,101));self.assertEqual(c.count,0)
        e.finish('Curious Otter');c.tick(B,'second',True,102)
        e.finish('Curious Otter');self.assertIsNone(c.tick(B,'second',False,103));self.assertIsNone(c.done)

    def test_standard_and_nonloading_do_not_start_worker(self):
        for enabled,loading in ((False,True),(True,False)):
            c=ShardNameCollector(enabled=enabled,sample=Mock(side_effect=AssertionError('capture')))
            for now in range(100,105):self.assertIsNone(c.tick(A,'join',loading,now))
            self.assertIsNone(c.executor);c.close()

    def test_timeout_and_errors_fail_closed(self):
        e=Executor();c=ShardNameCollector(True,lambda:None,e)
        c.tick(A,'join',True,100);e.jobs[-1][1].set_exception(RuntimeError('unavailable'))
        c.tick(A,'join',True,221);self.assertEqual(len(e.jobs),1);self.assertIsNone(c.done)

    def test_capture_uses_existing_verified_window_api(self):
        import numpy as np
        c=ShardNameCollector(True);capture=Mock();capture.grab.return_value=np.zeros((100,200,3),dtype=np.uint8)
        c.capture=capture
        with patch('app_edition.require_screen_reading'),patch('screen_readers.read_image',return_value=[]) as read:
            self.assertIsNone(c._sample());self.assertEqual(read.call_args.args[0].shape,(58,136,3))
        capture.grab.assert_called_once_with();c._release();capture.stop.assert_called_once()

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
