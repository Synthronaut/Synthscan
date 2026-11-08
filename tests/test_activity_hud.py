import unittest
from activity_hud import button_position,toggle_request,afk_request,fresh_activity_status,notify_native,ActivityButton,ActivityCollapseButton,ActivityQuickControls,collapse_position
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


    def control(self,kind=ActivityButton,expanded=True):
        from pathlib import Path
        button=kind.__new__(kind);button.height=24;button.pending=None;button.owner=42
        button.status=dict(pid=42,at=time.time(),activity_expanded=expanded)
        button.directory=Path('unused-fixture');button.paint=Mock()
        # Gameplay protection on the body must not disable this explicit control.
        button.input_guard=lambda:True
        return button
    def test_explicit_button_click_works_during_game_without_foreground_change(self):
        from unittest.mock import patch
        button=self.control();event=SimpleNamespace(x=4,y=4)
        with patch('activity_hud.publish_json',return_value=True) as publish,patch('activity_hud.notify_native') as wake:
            button.press(event);button.release(event)
            self.assertFalse(publish.call_args.args[1]['expanded']);wake.assert_called_once()
    def test_no_press_outside_release_or_stale_owner_does_not_dispatch(self):
        from unittest.mock import patch
        event=SimpleNamespace(x=4,y=4)
        for scenario in ('no_press','outside_release','stale','wrong_owner'):
            button=self.control()
            if scenario=='stale':button.status['at']-=10
            if scenario=='wrong_owner':button.status['pid']=9
            with patch('activity_hud.publish_json') as publish:
                if scenario!='no_press':button.press(event)
                button.release(SimpleNamespace(x=200,y=4) if scenario=='outside_release' else event)
                publish.assert_not_called()
    def test_docked_minus_never_expands_an_already_collapsed_hud(self):
        from unittest.mock import patch
        button=self.control(ActivityCollapseButton,False);event=SimpleNamespace(x=4,y=4)
        with patch('activity_hud.publish_json',return_value=True) as publish,patch('activity_hud.notify_native'):
            button.press(event);button.release(event)
            self.assertFalse(publish.call_args.args[1]['expanded'])
    def test_docked_minus_stays_beside_panel_and_inside_negative_monitor(self):
        bounds=dict(left=-1920,top=0,width=1920,height=1080)
        self.assertEqual(collapse_position(dict(left=-500,top=2,right=0,bottom=400),bounds),(-526,2,24,24))
        self.assertEqual(collapse_position(dict(left=-1920,top=2,right=-1420,bottom=400),bounds),(-1418,2,24,24))

    def test_afk_request_is_explicit_and_owner_bound(self):
        state=dict(pid=42,at=100,afk_jiggler=dict(armed=False))
        request=afk_request(state,42,101,'afk-one')
        self.assertEqual(request['action'],'set_afk_armed');self.assertTrue(request['armed'])
        self.assertEqual(request['owner_pid'],42)
        state['afk_jiggler']['armed']=True
        self.assertFalse(afk_request(state,42,101)['armed'])
        for owner,now in [(9,101),(42,104),(42,99)]:
            with self.assertRaises(ValueError):afk_request(state,owner,now)

    def test_quick_strip_dispatches_afk_and_collapse_independently(self):
        from unittest.mock import patch
        for x,action in [(10,'set_activity_expanded'),(40,'set_afk_armed')]:
            button=self.control(ActivityQuickControls);event=SimpleNamespace(x=x,y=10)
            with patch('activity_hud.publish_json',return_value=True) as publish,patch('activity_hud.notify_native') as wake:
                button.press(event);button.release(event)
                request=publish.call_args.args[1]
                self.assertEqual(request['action'],action)
                if action=='set_afk_armed':self.assertTrue(request['armed']);self.assertNotIn('expanded',request)
                else:self.assertFalse(request['expanded']);self.assertNotIn('armed',request)
                wake.assert_called_once()

    def test_quick_strip_requires_press_and_release_on_same_button(self):
        from unittest.mock import patch
        for start,end in [(10,40),(40,10),(25,40),(40,25),(40,100),(-1,40)]:
            button=self.control(ActivityQuickControls)
            with patch('activity_hud.publish_json') as publish:
                button.press(SimpleNamespace(x=start,y=10));button.release(SimpleNamespace(x=end,y=10))
                publish.assert_not_called()

    def test_quick_strip_ignores_stale_owner_pending_and_duplicate_release(self):
        from unittest.mock import patch
        event=SimpleNamespace(x=40,y=10)
        for scenario in ('stale','owner','pending','unpressed'):
            button=self.control(ActivityQuickControls)
            if scenario=='stale':button.status['at']-=10
            if scenario=='owner':button.status['pid']=99
            if scenario=='pending':button.pending={'id':'pending'}
            with patch('activity_hud.publish_json') as publish:
                if scenario!='unpressed':button.press(event)
                button.release(event);publish.assert_not_called()
        button=self.control(ActivityQuickControls)
        with patch('activity_hud.publish_json',return_value=True) as publish,patch('activity_hud.notify_native'):
            button.press(event);button.release(event);button.pending=None;button.release(event)
            publish.assert_called_once()

    def test_quick_strip_stays_on_screen_with_both_buttons(self):
        bounds=dict(left=-1920,top=0,width=1920,height=1080)
        for left,right in [(-500,0),(-1920,-1420)]:
            x,y,width,height=collapse_position(dict(left=left,top=2,right=right,bottom=400),bounds,ActivityQuickControls.WIDTH)
            self.assertGreaterEqual(x,-1920);self.assertLessEqual(x+width,0)
            self.assertEqual((width,height),(78,24))

    def test_quick_strip_paints_actual_armed_error_and_pending_states(self):
        for armed,status,pending,label,color in [
            (False,'off',None,'AFK ○','#cbd5e1'),
            (True,'waiting for inactivity',None,'AFK ●','#8ee2bd'),
            (False,'error (input not sent)',None,'AFK !','#f0b35b'),
            (False,'off',{'action':'set_afk_armed'},'AFK ·','#cbd5e1')]:
            button=self.control(ActivityQuickControls);button.canvas=Mock();button.window=Mock()
            button.status['afk_jiggler']=dict(armed=armed,status=status);button.pending=pending
            ActivityQuickControls.paint(button)
            afk=button.canvas.create_text.call_args.kwargs
            self.assertEqual(afk['text'],label);self.assertEqual(afk['fill'],color)

    def test_quick_strip_shows_countdown_and_actual_pulse_feedback(self):
        from unittest.mock import patch
        for details,label in [
            ({'next_in_seconds':10},'AFK 10'),
            ({'next_in_seconds':3},'AFK 3'),
            ({'next_in_seconds':240},'AFK ●'),
            ({'pulse_active':True},'AFK ↔'),
            ({'last_pulse_at':99},'AFK ✓'),
            ({'last_pulse_at':97},'AFK ●')]:
            button=self.control(ActivityQuickControls);button.canvas=Mock();button.window=Mock()
            button.status['at']=100;button.status['afk_jiggler']=dict(armed=True,**details)
            with patch('activity_hud.time.time',return_value=100):ActivityQuickControls.paint(button)
            self.assertEqual(button.canvas.create_text.call_args.kwargs['text'],label)

if __name__=='__main__':unittest.main()
