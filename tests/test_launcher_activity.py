import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from launcher_activity import LauncherActivity,DirectoryChanges
from app_lifecycle import launcher_process_ids


class FakeWatch:
    def __init__(self,path):self.fire=False;self.closed=False
    def changed(self):
        value=self.fire;self.fire=False;return value
    def close(self):self.closed=True


class LauncherActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.game=self.root/'LIVE';self.game.mkdir()
        (self.game/'Data.p4k').write_bytes(b'archive')
        (self.game/'build_manifest.id').write_bytes(b'manifest')
        self.now=time.time();os.utime(self.game/'Data.p4k',(self.now-500,self.now-500))
        self.activity=LauncherActivity(self.root/'profile',FakeWatch);self.addCleanup(self.activity.close)
        self.discovery=patch('launcher_activity.channels',return_value=[self.game]).start();self.addCleanup(patch.stopall)
        patch('launcher_activity.launcher_session_key',side_effect=lambda pids:','.join(map(str,sorted(pids)))).start()
        self.request=patch('launcher_activity.request_check').start()

    def update(self,now=None,launchers=(10,),games=()):
        return self.activity.update(launchers,games,self.now if now is None else now)

    def test_idle_or_playing_without_launcher_does_no_file_checks(self):
        with patch('launcher_activity.signature') as read:
            for _ in range(10):self.update(launchers=(),games=())
            for _ in range(10):self.update(launchers=(),games=(50,))
            read.assert_not_called();self.request.assert_not_called();self.discovery.assert_not_called()

    def test_uninstalled_strings_never_queues_or_watches_patch_checks(self):
        activity=LauncherActivity(self.root/'without-strings',FakeWatch,enabled=False)
        with patch('launcher_activity.signature') as read,patch('launcher_activity.launcher_session_key') as session:
            for launchers,games in (((10,),()),((10,),(50,)),((),())):
                self.assertFalse(activity.update(launchers,games,self.now))
            session.assert_not_called();read.assert_not_called()
        self.request.assert_not_called();self.discovery.assert_not_called()
        self.assertEqual(activity.rows,{})
        self.assertFalse((self.root/'without-strings').exists())

    def test_launcher_opens_one_check_not_a_recurring_scan(self):
        from launcher_activity import signature
        with patch('launcher_activity.signature',wraps=signature) as read:
            self.assertTrue(self.update())
            for i in range(1,300):self.update(self.now+i)
            self.assertEqual(read.call_count,1);self.assertEqual(self.request.call_count,1)
            self.assertEqual(self.request.call_args.args[1],'launcher_open')

    def test_patch_file_events_trigger_start_and_one_settled_completion(self):
        self.update();watch=self.activity.rows[self.game]['watch']
        (self.game/'Data.p4k').write_bytes(b'new archive');watch.fire=True
        self.update(self.now+1)
        self.assertEqual(self.request.call_args.args[1],'patch_started')
        # More writes postpone completion without issuing more start checks.
        (self.game/'build_manifest.id').write_bytes(b'new manifest');watch.fire=True
        self.update(self.now+60);self.assertEqual(self.request.call_count,2)
        self.update(self.now+179);self.assertEqual(self.request.call_count,2)
        self.update(self.now+181);self.assertEqual(self.request.call_args.args[1],'patch_finished')
        self.update(self.now+600);self.assertEqual(self.request.call_count,3)

    def test_unrelated_root_file_event_does_not_start_a_patch_check(self):
        self.update();self.activity.rows[self.game]['watch'].fire=True
        self.update(self.now+10);self.assertEqual(self.request.call_count,1)

    def test_game_start_stops_file_watching_and_suppresses_completion(self):
        self.update();watch=self.activity.rows[self.game]['watch']
        watch.fire=True;(self.game/'Data.p4k').write_bytes(b'patch')
        self.update(self.now+1);self.update(self.now+2,games=(50,))
        self.assertTrue(watch.closed)
        with patch('launcher_activity.signature') as read:
            for i in range(10):self.update(self.now+500+i,games=(50,))
            read.assert_not_called()
        self.assertEqual(self.request.call_count,2)

    def test_launcher_opened_during_play_waits_until_game_closes(self):
        self.update(games=(50,));self.request.assert_not_called();self.discovery.assert_not_called()
        self.update(self.now+10);self.assertEqual(self.request.call_count,1)

    def test_closing_launcher_cancels_pending_completion(self):
        self.update();watch=self.activity.rows[self.game]['watch'];watch.fire=True
        (self.game/'Data.p4k').write_bytes(b'new');self.update(self.now+1)
        self.update(self.now+2,launchers=());self.update(self.now+500,launchers=())
        self.assertTrue(watch.closed);self.assertEqual(self.request.call_count,2)

    def test_electron_renderer_restarts_do_not_count_as_new_launcher(self):
        with patch('app_lifecycle.named_processes',return_value={10:('rsi launcher.exe',1),11:('rsi launcher.exe',10)}):
            first=launcher_process_ids()
        with patch('app_lifecycle.named_processes',return_value={10:('rsi launcher.exe',1),15:('rsi launcher.exe',10)}):
            self.assertEqual(first,launcher_process_ids())

    @unittest.skipUnless(os.name=='nt','Windows file notifications')
    def test_os_notification_arrives_without_polling_game_file_contents(self):
        watch=DirectoryChanges(self.game)
        try:
            self.assertFalse(watch.changed())
            (self.game/'build_manifest.id').write_bytes(b'published build')
            deadline=time.monotonic()+2
            while not watch.changed():
                if time.monotonic()>deadline:self.fail('No OS file-change notification')
                time.sleep(.01)
        finally:watch.close()


if __name__=='__main__':unittest.main()
