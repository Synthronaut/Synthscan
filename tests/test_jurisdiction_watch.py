import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jurisdiction_watch import JurisdictionWatch
from telemetry_core import IncrementalGameLog, utc_iso
from native_bridge import SessionService


def notice(title, at=101, number=17, tag='SHUDEvent_OnNotification'):
    return f'<{utc_iso(at)}> [Notice] <{tag}> Added notification "{title}: " [{number}] to queue. New queue size: 1\n'


def join(at=100, shard='pub_use1b_100_020'):
    return f'<{utc_iso(at)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[{shard}]\n'


class JurisdictionTests(unittest.TestCase):
    def test_all_verified_monitoring_transitions_and_no_replay_pulse(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Entered Monitored Space'), 101, 'game_log_timestamp')
        first = watch.view(102, session_token='a')
        self.assertEqual(first['monitoring'], 'monitored')
        self.assertIsNone(first['changed_at'])
        for at, title, expected in [(103, 'Exited Monitored Space', 'unmonitored'),
                                    (104, 'Monitored Space Restored', 'monitored'),
                                    (105, 'Monitored Space Down', 'down')]:
            watch.feed(notice(title, at), at, 'game_log_timestamp')
            value = watch.view(at, session_token='a')
            self.assertEqual(value['monitoring'], expected)
            self.assertEqual(value['changed_at'], at)
        self.assertIsNone(watch.view(108, session_token='a')['changed_at'])

    def test_jurisdiction_never_implies_monitoring_or_permission(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Entered UEE Jurisdiction'), 101, 'game_log_timestamp')
        view = watch.view(102, session_token='a')
        self.assertEqual(view['jurisdiction'], 'UEE')
        self.assertEqual(view['monitoring'], 'unknown')
        self.assertEqual(view['armistice'], 'unknown')
        self.assertEqual(view['security_hostility'], 'unknown')
        self.assertNotIn('safe', view)
        watch.feed(notice('Entered Ungoverned Jurisdiction', 103), 103, 'game_log_timestamp')
        self.assertEqual(watch.view(104, session_token='a')['monitoring'], 'unknown')

    def test_armistice_and_monitoring_are_independent(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Entered Monitored Space'), 101, 'game_log_timestamp')
        watch.feed(notice('Entering Armistice Zone - Combat Prohibited', 102), 102, 'game_log_timestamp')
        watch.feed(notice('Leaving Armistice Zone - Caution Advised', 103), 103, 'game_log_timestamp')
        view = watch.view(104, session_token='a')
        self.assertEqual(view['armistice'], 'outside')
        self.assertEqual(view['monitoring'], 'monitored')
        watch.feed(notice('Monitored Space Down', 105), 105, 'game_log_timestamp')
        self.assertEqual(watch.view(106, session_token='a')['armistice'], 'outside')

    def test_noise_repeated_updates_and_missing_timestamps_do_not_change_state(self):
        watch = JurisdictionWatch()
        self.assertFalse(watch.feed(notice('Entered Monitored Space'), 101, 'observation'))
        self.assertFalse(watch.feed(notice('Entered Monitored Space', tag='UpdateNotificationItem'), 101, 'game_log_timestamp'))
        self.assertFalse(watch.feed(notice('New Objective: Entered Monitored Space'), 101, 'game_log_timestamp'))
        watch.feed(notice('Exited Monitored Space', 104), 104, 'game_log_timestamp')
        self.assertFalse(watch.feed(notice('Entered Monitored Space', 101), 101, 'game_log_timestamp'))
        self.assertEqual(watch.view(105, session_token='a')['monitoring'], 'unmonitored')

    def test_repeat_same_condition_retains_time_without_retriggering_flash(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Entered Monitored Space'), 101, 'game_log_timestamp')
        watch.view(102, session_token='a')
        watch.feed(notice('Entered Monitored Space', 103), 103, 'game_log_timestamp')
        value = watch.view(103, session_token='a')
        self.assertIsNone(value['changed_at'])
        self.assertEqual(value['observations']['monitoring']['observed_at'], 103)

    def test_inactive_future_and_reset_states_are_unknown(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Exited Monitored Space', 105), 105, 'game_log_timestamp')
        for kwargs in (dict(now=104, session_token='a'), dict(now=106), dict(now=106, active=False, session_token='a')):
            value = watch.view(**kwargs)
            self.assertEqual(value['monitoring'], 'unknown')
            self.assertFalse(value['available'])
        watch.reset()
        self.assertEqual(watch.view(106, session_token='b')['observations'], {})

    def test_last_report_timestamp_is_not_refreshed_by_drawing(self):
        watch = JurisdictionWatch()
        watch.feed(notice('Entered Monitored Space'), 101, 'game_log_timestamp')
        for now in (102, 105, 1000):
            value = watch.view(now, session_token='a')
            self.assertEqual(value['observations']['monitoring']['observed_at'], 101)
            self.assertEqual(value['observations']['monitoring']['age_s'], now-101)
            self.assertEqual(value['semantics'], 'last_reported')

    def test_reader_clears_across_shard_change_loading_and_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'Game.log'
            path.write_text(join()+notice('Exited Monitored Space'))
            reader = IncrementalGameLog(path)
            self.assertEqual(reader.jurisdiction.view(102, session_token=reader.session_token)['monitoring'], 'unmonitored')
            reader.feed(join(103, 'pub_use1b_100_021').encode())
            self.assertEqual(reader.jurisdiction.view(104, session_token=reader.session_token)['monitoring'], 'unknown')
            reader.feed(notice('Entered Monitored Space', 105).encode())
            reader.feed(f'<{utc_iso(106)}> OpenLoadingScreen\n'.encode())
            self.assertEqual(reader.jurisdiction.fields, {})
            reader.feed(f'<{utc_iso(107)}> Connection closed\n'.encode())
            self.assertFalse(reader.connected)
            self.assertEqual(reader.jurisdiction.fields, {})

    def test_real_bridge_model_uses_existing_reader_and_clears_on_game_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); log = root/'Game.log'
            log.write_text(join()+notice('Entered UEE Jurisdiction')+notice('Entered Monitored Space', 102))
            with patch('native_bridge.read_network_ping', return_value=None), patch('native_bridge.read_client_fps', return_value=None):
                service = SessionService(root, log)
                try:
                    state = service.tick(True, 103)
                    self.assertEqual(state['jurisdiction']['monitoring'], 'monitored')
                    self.assertEqual(state['jurisdiction']['session_token'], state['session_token'])
                    self.assertIsNone(state['jurisdiction']['changed_at'])
                    with log.open('a') as file:
                        file.write(notice('Exited Monitored Space', 104))
                    changed = service.tick(True, 105)
                    self.assertEqual(changed['jurisdiction']['changed_at'], 104)
                    self.assertEqual(changed['jurisdiction']['security_hostility'], 'unknown')
                    self.assertFalse(service.tick(False, 106)['jurisdiction']['available'])
                finally:
                    service.close()


if __name__ == '__main__':
    unittest.main()
