import unittest
from activity_hud import button_position,toggle_request,fresh_activity_status,notify_native
from unittest.mock import Mock
from types import SimpleNamespace
import time

class ActivityHUDTests(unittest.TestCase):
    def test_toggle_is_explicit_owner_bound_and_rejects_stale_state(self):
        state=dict(pid=42,at=100,activity_expanded=True)
        command=toggle_request(state,42,101,'one')
        self.assertFalse(command['expanded']);self.assertEqual(command['owner_pid'],42)
        self.assertEqual(command['action'],'set_activity_expanded')
        for owner,now in [(41,101),(42,104),(42,99)]:
            with self.assertRaises(ValueError):toggle_request(state,owner,now)
        state['activity_expanded']=False
        self.assertTrue(toggle_request(state,42,101)['expanded'])
    def test_button_follows_ribbon_and_stays_on_screen(self):
        bounds=dict(left=-1920,top=-100,width=1920,height=1080)
        self.assertEqual(button_position((-1800,0,600,24),bounds),(-1197,0,52,24))
        x,y,w,h=button_position((-700,900,695,24),bounds)
        self.assertEqual(x,-755)
        self.assertGreaterEqual(x,bounds['left']);self.assertLessEqual(x+w,0)
        self.assertGreaterEqual(y,-100);self.assertLessEqual(y+h,980)
    def test_malformed_status_is_unavailable(self):
        self.assertFalse(fresh_activity_status(dict(pid=42,at=None),42,100))

    def test_native_wakeup_checks_window_owner(self):
        api=SimpleNamespace(FindWindowW=Mock(return_value=123),GetWindowThreadProcessId=Mock(),PostMessageW=Mock(return_value=1))
        status=dict(pid=42,at=time.time())
        api.GetWindowThreadProcessId.side_effect=lambda hwnd,pid:setattr(pid._obj,'value',41)
        self.assertFalse(notify_native(status,42,api));api.PostMessageW.assert_not_called()
        api.GetWindowThreadProcessId.side_effect=lambda hwnd,pid:setattr(pid._obj,'value',42)
        self.assertTrue(notify_native(status,42,api));api.PostMessageW.assert_called_once_with(123,0x8000+42,0,0)

if __name__=='__main__':unittest.main()
