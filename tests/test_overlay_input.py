import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from overlay_input import protect_game_input,set_passthrough,input_blocked
from activity_hud import ActivityButton
from region_history_hud import RegionHistory

class OverlayInputTests(unittest.TestCase):
    def test_game_and_unknown_foreground_are_protected(self):
        for foreground in (42,99,0):self.assertTrue(protect_game_input(foreground,{1,2},True))
        self.assertFalse(protect_game_input(1,{1,2},True))
        self.assertFalse(protect_game_input(42,{1,2},False))
    def test_styles_preserve_topmost_and_prevent_activation(self):
        api=SimpleNamespace(GetWindowLongW=Mock(return_value=0x80008),SetWindowLongW=Mock())
        style=set_passthrough(123,True,api)
        self.assertTrue(style&0x20);self.assertTrue(style&0x08000000);self.assertTrue(style&8)
        api.GetWindowLongW.return_value=style
        set_passthrough(123,True,api);self.assertEqual(api.SetWindowLongW.call_count,1)
        unlocked=set_passthrough(123,False,api);self.assertFalse(unlocked&0x20);self.assertTrue(unlocked&0x08000000)
    def test_live_guard_overrides_stale_desktop_poll_state(self):
        self.assertTrue(input_blocked(SimpleNamespace(input_protected=False,input_guard=lambda:True)))
        self.assertTrue(input_blocked(SimpleNamespace()))
        self.assertFalse(input_blocked(SimpleNamespace(input_guard=lambda:False)))
    def test_activity_release_outside_button_cannot_toggle_hud(self):
        button=ActivityButton.__new__(ActivityButton);button.pressed=True;button.height=24;button.pending=None
        with patch('activity_hud.publish_json') as publish:
            button.release(SimpleNamespace(x=100,y=100))
            publish.assert_not_called()
        self.assertFalse(button.pressed)
    def test_queued_region_action_cannot_open_popup_or_change_lock(self):
        history=RegionHistory.__new__(RegionHistory);history.input_guard=lambda:True;history.open=False
        history.popup=Mock();history.ribbon=Mock()
        history.toggle();history.toggle_lock()
        history.popup.deiconify.assert_not_called();history.ribbon._save_preferences.assert_not_called()

if __name__=='__main__':unittest.main()
