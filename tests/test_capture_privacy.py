"""Privacy boundaries without opening windows, capturing the game or networking."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from capture_privacy import Policy,GameTarget,GameCapture,read_policy,require_account_access,capture_allowed

class FakeCapture:
    def __init__(self,**settings):self.settings=settings;self.handlers={};self.stopped=False
    def event(self,handler):self.handlers[handler.__name__]=handler;return handler
    def start_free_threaded(self):
        self.emit(np.full((100,120,4),47,dtype=np.uint8));return self
    def stop(self):self.stopped=True
    def is_finished(self):return self.stopped
    def emit(self,pixels):self.handlers['on_frame_arrived'](SimpleNamespace(frame_buffer=pixels),self)

class PolicyTests(unittest.TestCase):
    def test_default_capture_policy_keeps_focus_guard(self):
        with tempfile.TemporaryDirectory() as folder:self.assertEqual(read_policy(folder),Policy(False,True))
    def test_invalid_policy_never_resumes_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'capture_privacy.json'
            for value in ('{invalid','[]','{"schema":2}','{"schema":1,"paused":"false"}'):
                path.write_text(value);self.assertTrue(read_policy(folder).paused)
    def test_pause_and_focus_choices_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'capture_privacy.json').write_text(json.dumps(dict(schema=1,paused=True,pause_unfocused=False)))
            self.assertEqual(read_policy(folder),Policy(True,False))
    def test_account_permission_is_separate_and_revocable(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(PermissionError):require_account_access(folder)
            path=Path(folder)/'capture_privacy.json'
            path.write_text(json.dumps(dict(schema=1,paused=True,account_access=True)))
            require_account_access(folder)
            path.write_text(json.dumps(dict(schema=1,account_access=False)))
            with self.assertRaises(PermissionError):require_account_access(folder)
            path.write_text('{bad')
            with self.assertRaises(PermissionError):require_account_access(folder)
    def test_missing_target_and_pause_fail_before_windows_api_calls(self):
        self.assertFalse(capture_allowed(None,Policy()))
        self.assertFalse(capture_allowed(SimpleNamespace(hwnd=1),Policy(paused=True)))

class WindowOnlyTests(unittest.TestCase):
    def setUp(self):
        self.target=GameTarget(123,7,200,100,120,100)
        self.target_patch=patch('capture_privacy.game_target',return_value=self.target);self.target_patch.start()
        self.allowed=patch('capture_privacy.capture_allowed',return_value=True).start()
        self.policy=patch('capture_privacy.read_policy',return_value=Policy()).start()
        self.source=GameCapture(FakeCapture)
    def tearDown(self):self.source.stop();patch.stopall()
    def test_capture_is_window_specific_and_has_no_display_target(self):
        frame=self.source.grab();settings=self.source.capture.settings
        self.assertEqual(settings['window_hwnd'],123)
        self.assertNotIn('monitor_index',settings)
        self.assertEqual(frame.shape,(100,120,3))
        self.assertTrue(settings['draw_border'])
    def test_off_window_crop_is_zero_padded(self):
        image=self.source.grab(dict(left=190,top=95,width=30,height=25))
        self.assertTrue(np.all(image[:5]==0));self.assertTrue(np.all(image[:,:10]==0))
        self.assertTrue(np.all(image[5:,10:]==47))
    def test_permission_loss_stops_capture_and_discards_pixels(self):
        self.source.grab();native=self.source.capture;self.allowed.return_value=False
        self.assertIsNone(self.source.grab());self.assertTrue(native.stopped);self.assertIsNone(self.source.latest)
    def test_pause_stops_an_existing_callback_before_copying(self):
        self.source.grab();native=self.source.capture;self.policy.return_value=Policy(paused=True)
        native.emit(np.full((100,120,4),99,dtype=np.uint8))
        self.assertTrue(native.stopped);self.assertIsNone(self.source.latest)
    def test_window_change_releases_previous_session_and_ignores_old_callbacks(self):
        self.source.grab();old=self.source.capture
        with patch('capture_privacy.game_target',return_value=GameTarget(456,8,0,0,120,100)):
            current=self.source.grab();old.emit(np.zeros((100,120,4),dtype=np.uint8))
            self.assertTrue(old.stopped);self.assertTrue(np.all(self.source.grab()==47))
    def test_no_target_never_falls_back_to_a_monitor(self):
        with patch('capture_privacy.game_target',return_value=None):
            self.allowed.return_value=False
            self.assertIsNone(self.source.grab());self.assertIsNone(self.source.capture)

class MemoryTransferTests(unittest.TestCase):
    def test_worker_image_transfer_creates_no_temporary_image_file(self):
        from native_mining import NativeMiningClient
        client=NativeMiningClient();seen={}
        def request(operation,**fields):
            import mmap
            self.assertEqual(operation,'scan_mapping')
            with mmap.mmap(-1,fields['width']*fields['height']*3,tagname=fields['mapping'],access=mmap.ACCESS_READ) as view:seen['pixels']=bytes(view)
            return {'result':'read'}
        with patch.object(client,'start'),patch.object(client,'request',side_effect=request):
            image=np.full((20,30,3),73,dtype=np.uint8)
            self.assertEqual(client.request_image(image),{'result':'read'})
            self.assertEqual(seen['pixels'],image.tobytes())
        client.close()
    def test_community_package_excludes_privacy_preferences_and_frame_artifacts(self):
        from tools.package_community import PRIVATE
        self.assertTrue({'capture_privacy.json','fabricator_frame.png','fabricator_frame_ack.json'}<=PRIVATE)
    def test_capture_activity_temporary_files_are_not_packaged(self):
        from tools.package_community import copy_tree
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';destination=Path(folder)/'package';source.mkdir()
            (source/'capture_activity.123.tmp').write_text('{"at":100}')
            (source/'definition.json').write_text('{}')
            copy_tree(source,destination)
            self.assertFalse((destination/'capture_activity.123.tmp').exists())
            self.assertTrue((destination/'definition.json').exists())

if __name__=='__main__':unittest.main()
