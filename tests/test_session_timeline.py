import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from telemetry_core import timestamp,utc_iso,IncrementalGameLog
from session_store import ServerLogManager
from session_timeline import timeline,export_timeline,date_bounds
from native_bridge import SessionService

def visit(key,joined,left=None,full='pub_use1b_100_020',**kw):
    return dict(id=key,joined_at=joined,left_at=left,full_shard_id=full,shard_id=full.rsplit('_',1)[-1],
                region_raw=full.split('_')[1],server_name='Example label',locations=[],notes='',active=False,**kw)

class TimelineTests(unittest.TestCase):
    def test_local_clock_and_exact_utc_source_remain_separate(self):
        rows=timeline([visit('one','2026-10-21T07:00:00.123Z','2026-10-21T10:00:00.987Z',joined_time_source='game_log_timestamp',left_time_source='game_log_timestamp')],0)['rows']
        self.assertEqual(rows[0]['joined_local'],'2026-10-21 15:00:00');self.assertEqual(rows[0]['left_local'],'2026-10-21 18:00:00')
        self.assertEqual(rows[0]['joined_utc'],'2026-10-21T07:00:00.123Z');self.assertEqual(rows[0]['leave_source'],'Game log timestamp')
    def test_date_filter_matches_overlapping_sessions_and_region_query(self):
        sessions=[visit('overlap','2026-10-20T15:00:00Z','2026-10-20T17:00:00Z'),visit('ended','2026-10-20T14:00:00Z','2026-10-20T16:00:00Z'),
                  visit('future','2026-10-21T16:00:00Z','2026-10-21T17:00:00Z')]
        view=timeline(sessions,0,dict(date_from='2026-10-21',date_to='2026-10-21',region='use1b',query='Example 020'))
        self.assertEqual([r['id'] for r in view['rows']],['overlap'])
    def test_invalid_dates_and_reversed_dates_rejected(self):
        for lo,hi in [('2026-02-30',''),('','garbage'),('2026-10-22','2026-10-21')]:
            with self.assertRaises(ValueError):date_bounds(lo,hi)
    def test_repeat_visits_use_full_shard_identity(self):
        records=[visit('a',utc_iso(100),utc_iso(200)),visit('b',utc_iso(300),utc_iso(400),full='pub_use1b_101_020'),visit('c',utc_iso(500),utc_iso(600))]
        rows=timeline(records,700)['rows'];self.assertEqual(rows[0]['visit'],'Return #2');self.assertEqual(rows[1]['visit'],'First recorded visit')
    def test_unknown_exit_is_not_still_playing_and_keeps_last_seen(self):
        row=timeline([visit('unknown',utc_iso(100),last_confirmed_at=utc_iso(160))],1000)['rows'][0]
        self.assertEqual(row['status'],'Exit unknown');self.assertEqual(row['left_local'],'Unknown');self.assertEqual(row['duration'],'At least 1m 0s')
    def test_detected_end_and_next_join_bounds_are_labelled(self):
        for source,prefix in [('process_observation','Detected '),('next_join_bound','By '),('absence_on_startup','By ')]:
            row=timeline([visit('bound',utc_iso(100),utc_iso(200),left_time_source=source)],0)['rows'][0]
            self.assertTrue(row['left_local'].startswith(prefix));self.assertNotEqual(row['leave_source'],'Game log timestamp')
    def test_export_preserves_utc_and_notes_without_spreadsheet_execution(self):
        record=visit('one',utc_iso(100),utc_iso(200));record['notes']='=HYPERLINK("bad")'
        view=timeline([record],0)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'history.csv';self.assertEqual(export_timeline(p,view,'csv'),1)
            with p.open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
            self.assertTrue(row['notes'].startswith("'="));self.assertEqual(row['joined_utc'],utc_iso(100));self.assertEqual(row['region'],'USE1B')
            p=Path(d)/'history.json';export_timeline(p,view,'json');self.assertEqual(json.loads(p.read_text())['visits'][0]['notes'],record['notes'])

class LifecycleTests(unittest.TestCase):
    def test_reader_carries_timestamp_quality_and_implicit_hop_is_bound(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text('');reader=IncrementalGameLog(p)
            reader.feed(f'<{utc_iso(100)}> <Join PU> shard[pub_use1b_100_020]\n<{utc_iso(200)}> <Join PU> shard[pub_use1b_100_021]\n'.encode())
            events=reader.drain_events();self.assertEqual(events[0]['time_source'],'game_log_timestamp');self.assertEqual(events[1]['time_source'],'next_join_bound')
    def test_app_restart_does_not_fabricate_logout(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'history.json';store=ServerLogManager(p,clock=lambda:100)
            store.start_new_session('use1b','100','020',joined_at=100);store.confirm_seen(150);store.flush()
            reopened=ServerLogManager(p,clock=lambda:200)
            row=timeline(reopened.sessions,200)['rows'][0];self.assertEqual(row['status'],'Exit unknown');self.assertIsNone(row['left_utc'])
    def test_closed_game_replay_keeps_previous_detected_exit(self):
        with tempfile.TemporaryDirectory() as d,patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
            root=Path(d);p=root/'Game.log';p.write_text(f'<{utc_iso(100)}> <Join PU> shard[pub_use1b_100_020]\n')
            service=SessionService(root,p)
            try:service.tick(True,101);service.tick(False,150)
            finally:service.close()
            service=SessionService(root,p)
            try:
                state=service.tick(False,300);self.assertEqual(len(state['sessions']),1);self.assertEqual(state['sessions'][0]['left_at'],utc_iso(150))
            finally:service.close()
    def test_session_view_and_export_flow_through_bridge_queue(self):
        with tempfile.TemporaryDirectory() as d,patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
            root=Path(d);p=root/'Game.log';p.write_text(f'<{utc_iso(100)}> <Join PU> shard[pub_use1b_100_020]\n<{utc_iso(200)}> Connection closed\n')
            service=SessionService(root,p)
            try:
                state=service.tick(True,300);folder=root/'diary_commands';folder.mkdir()
                command=dict(id='filter',action='session_view',region='use1b',date_from='1970-01-01',date_to='1970-01-01')
                (folder/'01.json').write_text(json.dumps(command));service.diary_commands();self.assertEqual(service.tick(True,301)['session_log']['count'],1)
                command=dict(id='export',action='session_export',format='csv',path=str(root/'export.csv'))
                (folder/'02.json').write_text(json.dumps(command));service.diary_commands();self.assertTrue((root/'export.csv').exists())
                self.assertFalse(list(folder.glob('*.json')))
            finally:service.close()
    def test_timeline_pages_do_not_limit_retention_or_export(self):
        with tempfile.TemporaryDirectory() as d,patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
            root=Path(d);p=root/'Game.log';p.write_text('');service=SessionService(root,p)
            try:
                service.sessions.sessions=[visit(str(i),utc_iso(100+i*20),utc_iso(110+i*20)) for i in range(130)]
                state=service.tick(False,3000);self.assertEqual(len(state['session_rows']),100);self.assertEqual(state['session_log']['count'],130)
                service.command(dict(id='page',action='session_view',offset=100))
                state=service.tick(False,3000);self.assertEqual(len(state['session_rows']),30);self.assertEqual(state['session_log']['offset'],100)
                path=root/'full.json';service.command(dict(id='full-export',action='session_export',path=str(path),format='json'))
                self.assertEqual(len(json.loads(path.read_text())['visits']),130);self.assertEqual(len(service.sessions.sessions),130)
            finally:service.close()

if __name__=='__main__':unittest.main()
