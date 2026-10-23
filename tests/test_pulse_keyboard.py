"""Input guards without sending any Windows input or opening a window."""
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from tools.test_displayinfo_keyboard import Keyboard, Cancelled, ConsoleGuard, wait_visibility


class KeyboardGuardTests(unittest.TestCase):
    def keyboard(self):
        keyboard = Keyboard.__new__(Keyboard)
        keyboard.hwnd = 123
        keyboard.hold = .06
        keyboard.char_hold = .012
        keyboard.gap = .012
        keyboard.layout = None
        keyboard.user = Mock()
        keyboard.user.GetForegroundWindow.return_value = 123
        keyboard.user.GetAsyncKeyState.return_value = 0
        keyboard.user.MapVirtualKeyExW.return_value = 30
        keyboard.event = Mock()
        return keyboard

    def test_focus_loss_prevents_any_input(self):
        keyboard = self.keyboard()
        keyboard.user.GetForegroundWindow.return_value = 456
        with self.assertRaises(Cancelled):
            keyboard.key(65)
        keyboard.event.assert_not_called()

    def test_escape_prevents_any_input(self):
        keyboard = self.keyboard()
        keyboard.user.GetAsyncKeyState.return_value = 0x8000
        with self.assertRaises(Cancelled):
            keyboard.key(65)
        keyboard.event.assert_not_called()

    def test_burst_text_does_not_send_anything_after_focus_loss(self):
        keyboard = self.keyboard()
        keyboard.user.GetForegroundWindow.return_value = 456
        with self.assertRaises(Cancelled):
            keyboard.text_burst("r_displayinfo 1")
        keyboard.user.SendInput.assert_not_called()

    def test_interruption_still_releases_own_key(self):
        keyboard = self.keyboard()
        with patch("tools.test_displayinfo_keyboard.time.sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                keyboard.key(65)
        self.assertEqual(keyboard.event.call_args_list[0].args, (30,))
        self.assertEqual(keyboard.event.call_args_list[1].args, (30,))
        self.assertEqual(keyboard.event.call_args_list[1].kwargs, {"up": True})

    def test_focused_tester_can_handoff_to_game(self):
        keyboard = self.keyboard()
        keyboard.foreground_details = Mock(side_effect=[{"pid": 100, "hwnd": 456, "is_game": False},
                                                       {"pid": 200, "hwnd": 123, "is_game": True}])
        with patch("tools.test_displayinfo_keyboard.os.getpid", return_value=100):
            result = keyboard.handoff_from_tester()
        keyboard.user.SetForegroundWindow.assert_called_once_with(123)
        self.assertTrue(result["after"]["is_game"])
        keyboard.event.assert_not_called()

    def test_handoff_does_not_steal_focus_from_another_app(self):
        keyboard = self.keyboard()
        keyboard.foreground_details = Mock(return_value={"pid": 300, "hwnd": 456, "is_game": False})
        with patch("tools.test_displayinfo_keyboard.os.getpid", return_value=100):
            with self.assertRaises(Cancelled):
                keyboard.handoff_from_tester()
        keyboard.user.SetForegroundWindow.assert_not_called()
        keyboard.event.assert_not_called()


class ConsoleGuardTests(unittest.TestCase):
    def test_missing_or_single_marker_does_not_authorize_console_typing(self):
        guard = ConsoleGuard.__new__(ConsoleGuard)
        guard.cv2 = cv2
        rng = np.random.default_rng(52)
        marker = rng.integers(0, 256, (12, 48), dtype=np.uint8)
        guard.template = marker.astype("float32")
        image = np.zeros((200, 200, 3), dtype=np.uint8)
        self.assertFalse(guard.classify(image))
        image[20:32, 8:56] = marker[:, :, None]
        self.assertIsNone(guard.classify(image))
        image[60:72, 8:56] = marker[:, :, None]
        self.assertTrue(guard.classify(image))


class VisibilityConfirmationTests(unittest.TestCase):
    def test_held_status_does_not_count_as_new_absent_frames(self):
        frames = [{"at": at, "visible": False} for at in [100, 100, 100, 100.1, 100.2]]
        with patch("tools.test_displayinfo_keyboard.read_status", side_effect=frames) as read:
            with patch("tools.test_displayinfo_keyboard.time.sleep"):
                result = wait_visibility(None, False, 1, Mock(), after=99, stable_for=.15)
        self.assertEqual(result["at"], 100.2)
        self.assertEqual(read.call_count, 5)

    def test_panel_reappearing_resets_off_confirmation(self):
        frames = [{"at": at, "visible": visible} for at, visible in
                  [(100, False), (100.1, True), (100.2, False), (100.3, False), (100.4, False)]]
        with patch("tools.test_displayinfo_keyboard.read_status", side_effect=frames) as read:
            with patch("tools.test_displayinfo_keyboard.time.sleep"):
                result = wait_visibility(None, False, 1, Mock(), after=99, stable_for=.15)
        self.assertEqual(result["at"], 100.4)
        self.assertEqual(read.call_count, 5)


if __name__ == "__main__":
    unittest.main()
