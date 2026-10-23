import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from telemetry_core import IncrementalGameLog,utc_iso
from interdiction_watch import InterdictionNotifications,InterdictionJournal,AlertGate,piracy_alerts_enabled
from native_bridge import SessionService
from session_timeline import timeline

def notification(at=100,num=170,name='ExamplePilot',tag='SHUDEvent_OnNotification'):
    return f'<{utc_iso(at)}> [Notice] <{tag}> Added notification "Crime Committed: Unauthorized Interdiction\n<{utc_iso(at)}> against {name}: " [{num}] to queue. New queue size: 1\n'

def event(at=100,num='170',**kw):
    return dict(at=at,target='ExamplePilot',notification_id=num,full_shard_id='pub_use1b_100_020',joined_at=90,
                session='join',source='game_log_interdiction_crime_notification',**kw)

class ParserTests(unittest.TestCase):
    def test_split_bytes_and_notification_updates_are_not_extra_events(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'Game.log';path.write_text('');reader=IncrementalGameLog(path)
            text=f'<{utc_iso(90)}> <Join PU> shard[pub_use1b_100_020]\n'+notification()
            text+=f'<{utc_iso(100)}> [Notice] <UpdateNotificationItem> Notification "Crime Committed: Unauthorized Interdiction\n<{utc_iso(100)}> against ExamplePilot: " [170], Action: Next\n'
            text+=f'<{utc_iso(100)}>    "Crime Committed: Unauthorized Interdiction\n<{utc_iso(100)}> against ExamplePilot: " [170]\n'
            for b in text.encode():reader.feed(bytes([b]))
            reports=[e for e in reader.drain_events() if e['type']=='interdiction']
            self.assertEqual(len(reports),1);self.assertEqual(reports[0]['target'],'ExamplePilot');self.assertEqual(reports[0]['at'],100)
    def test_noise_truncation_reset_and_other_crimes_rejected(self):
        parser=InterdictionNotifications();start=notification().splitlines()[0]
        parser.feed(start,100,'game_log_timestamp');parser.reset()
        self.assertIsNone(parser.feed('against ExamplePilot: " [170] to queue.',100,'game_log_timestamp'))
        parser.feed(start,100,'game_log_timestamp');self.assertIsNone(parser.feed('against ExamplePilot: " [170] to queue.',103,'game_log_timestamp'))
        for line in notification().replace('Unauthorized Interdiction','Assault').splitlines():self.assertIsNone(parser.feed(line,100,'game_log_timestamp'))
    def test_missing_timestamps_do_not_create_fresh_events(self):
        parser=InterdictionNotifications()
        for line in notification().splitlines():self.assertIsNone(parser.feed(line,100,'observation'))
    def test_two_victims_at_same_time_have_distinct_notifications(self):
        parser=InterdictionNotifications();out=[]
        for line in (notification()+notification(num=171,name='SecondPilot')).splitlines():
            result=parser.feed(line,100,'game_log_timestamp')
            if result:out.append(result)
        self.assertEqual([e['notification_id'] for e in out],['170','171'])

class JournalTests(unittest.TestCase):
    def test_replay_is_silent_and_deduplicates_across_reader_generations(self):
        with tempfile.TemporaryDirectory() as d:
            journal=InterdictionJournal(d);journal.observe(event(replayed=True),101)
            self.assertEqual(journal.view('join',101)['alerts'],[])
            reopened=InterdictionJournal(d);e=event();e['session']='new-generation';reopened.observe(e,102)
            self.assertEqual(len(reopened.entries),1);self.assertEqual(reopened.view('new-generation',102)['alerts'],[])
    def test_live_reports_expire_and_do_not_follow_server_hops(self):
        with tempfile.TemporaryDirectory() as d:
            journal=InterdictionJournal(d);journal.observe(event(),101)
            self.assertEqual(len(journal.view('join',102)['alerts']),1)
            self.assertEqual(journal.view('other',102)['alerts'],[]);self.assertEqual(journal.view('join',110)['alerts'],[])
    def test_corrupt_storage_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'interdiction_log.json';p.write_text('{bad');journal=InterdictionJournal(d)
            journal.observe(event(),101);self.assertTrue(journal.read_only);self.assertEqual(p.read_text(),'{bad')
    def test_same_handle_can_report_again_at_a_new_time(self):
        with tempfile.TemporaryDirectory() as d:
            j=InterdictionJournal(d);j.observe(event(),100);j.observe(event(at=101,num='171'),101)
            self.assertEqual(len(j.entries),2)
    def test_current_visit_counts_do_not_include_an_earlier_visit_or_other_shard(self):
        with tempfile.TemporaryDirectory() as d:
            j=InterdictionJournal(d);j.observe(event(replayed=True),101)
            view=j.view('new-generation',102,'pub_use1b_100_020',90)
            self.assertEqual(view['current_count'],1);self.assertEqual(view['current'][0]['target'],'ExamplePilot')
            self.assertEqual(j.view('other-join',102,'pub_use1b_100_020',101)['current_count'],0)
            self.assertEqual(j.view('other-shard',102,'pub_use1b_100_021',90)['current_count'],0)

class AlertTests(unittest.TestCase):
    def test_piracy_mode_and_visibility_switch_gate_audio(self):
        self.assertFalse(piracy_alerts_enabled({},True))
        self.assertTrue(piracy_alerts_enabled(dict(hud_mode='piracy'),True))
        for kw in [dict(hud_mode='mining'),dict(hud_mode='piracy',show_hud=False),dict(hud_mode='piracy',snare_alerts=False)]:self.assertFalse(piracy_alerts_enabled(kw,True))
        self.assertFalse(piracy_alerts_enabled(dict(hud_mode='piracy'),False))
    def snapshot(self):
        return dict(owner_pid=42,written_at=101,session_token='join',interdictions=dict(alerts=[dict(event(),id='alert',session_token='join',received_at=101)]))
    def test_one_shot_and_no_delayed_sound_after_muting(self):
        snap=self.snapshot();gate=AlertGate(100)
        self.assertEqual(len(gate.consume(snap,42,102,True)),1);self.assertEqual(gate.consume(snap,42,102,True),[])
        gate=AlertGate(100);self.assertEqual(gate.consume(snap,42,102,False),[]);self.assertEqual(gate.consume(snap,42,102,True),[])
    def test_stale_wrong_owner_replayed_and_restart_are_silent(self):
        for owner,now,started,replay in [(99,102,100,False),(42,110,100,False),(42,102,102,False),(42,102,100,True)]:
            snap=self.snapshot();snap['interdictions']['alerts'][0]['replayed']=replay
            self.assertEqual(AlertGate(started).consume(snap,owner,now,True),[])

class BridgeTests(unittest.TestCase):
    def test_bootstrap_records_history_without_sounding_then_new_report_is_live(self):
        with tempfile.TemporaryDirectory() as d,patch('native_bridge.read_network_ping',return_value=None),patch('native_bridge.read_client_fps',return_value=None):
            root=Path(d);log=root/'Game.log';log.write_text(f'<{utc_iso(90)}> <Join PU> shard[pub_use1b_100_020]\n'+notification())
            service=SessionService(root,log)
            try:
                state=service.tick(True,101);self.assertEqual(state['interdictions']['count'],1);self.assertEqual(state['interdictions']['alerts'],[])
                with log.open('a') as f:f.write(notification(at=102,num=176,name='SecondPilot'))
                state=service.tick(True,103);self.assertEqual(state['interdictions']['count'],2)
                self.assertEqual(len(state['interdictions']['alerts']),1);self.assertEqual(state['interdictions']['alerts'][0]['target'],'SecondPilot')
                self.assertEqual(state['session_rows'][0]['interdiction_reports'],2)
                self.assertIn('SecondPilot',state['session_rows'][0]['detail'])
            finally:service.close()

if __name__=='__main__':unittest.main()
