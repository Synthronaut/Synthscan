import ctypes
from unittest.mock import patch, MagicMock
import unittest

from session_recovery import (
    read_game_memory,
    terminate_sc_and_eac,
    focus_rsi_launcher,
    execute_recovery_async,
)


class TestSessionRecovery(unittest.TestCase):
    def test_read_game_memory_empty_pids(self):
        with patch('app_lifecycle.game_process_ids', return_value=frozenset()):
            self.assertIsNone(read_game_memory())

    @patch('time.sleep')
    @patch('subprocess.run')
    @patch('app_lifecycle.game_process_ids')
    @patch('ctypes.windll.user32.FindWindowW')
    @patch('ctypes.windll.user32.PostMessageW')
    def test_terminate_sc_and_eac_graceful(self, mock_post, mock_find, mock_pids, mock_run, mock_sleep):
        # Game window found and responds gracefully
        mock_find.return_value = 0x12345
        mock_pids.side_effect = [frozenset({100}), frozenset(), frozenset(), frozenset()]

        terminate_sc_and_eac()

        # Should post WM_CLOSE (0x0010) to the window
        mock_post.assert_called_with(0x12345, 0x0010, 0, 0)
        # Should call taskkill without /F first
        mock_run.assert_any_call(["taskkill", "/IM", "starcitizen.exe"], capture_output=True, text=True)

    @patch('time.sleep')
    @patch('subprocess.run')
    @patch('app_lifecycle.game_process_ids')
    @patch('ctypes.windll.user32.FindWindowW')
    def test_terminate_sc_and_eac_fallback_force(self, mock_find, mock_pids, mock_run, mock_sleep):
        # Game window not found and fails to close gracefully
        mock_find.return_value = 0
        mock_pids.return_value = frozenset({100})

        terminate_sc_and_eac()

        # Should fallback to force taskkill
        mock_run.assert_any_call(["taskkill", "/F", "/T", "/IM", "starcitizen.exe"], capture_output=True, text=True)

    @patch('ctypes.windll.user32.OpenInputDesktop', return_value=1)
    @patch('ctypes.windll.user32.SetThreadDesktop', return_value=1)
    @patch('ctypes.windll.user32.EnumDesktopWindows')
    @patch('ctypes.windll.user32.ShowWindow')
    @patch('ctypes.windll.user32.SetForegroundWindow')
    @patch('ctypes.windll.user32.keybd_event')
    def test_focus_rsi_launcher_and_dismiss_modal(self, mock_key, mock_set_fg, mock_show, mock_enum, mock_set_desk, mock_open_desk):
        # Simulate finding RSI Launcher window
        def fake_enum(hdesk, cb, lp):
            # Simulate calling callback with hwnd that has title 'RSI Launcher'
            with patch('ctypes.windll.user32.GetWindowTextW', side_effect=lambda h, buf, n: buf.__setattr__('value', 'RSI Launcher') or 1):
                cb(0x9999, 0)
            return 1
        mock_enum.side_effect = fake_enum

        res = focus_rsi_launcher()
        self.assertTrue(res)
        mock_show.assert_called_with(0x9999, 9)
        # Should have sent Escape key (0x1B) down and up to dismiss crash dialog
        mock_key.assert_any_call(0x1B, 0, 0, 0)
        mock_key.assert_any_call(0x1B, 0, 2, 0)

    @patch('session_recovery.terminate_sc_and_eac')
    @patch('session_recovery.focus_rsi_launcher')
    @patch('session_recovery.auto_rejoin_watcher')
    def test_execute_recovery_async_flow(self, mock_watcher, mock_focus, mock_term):
        statuses = []
        def on_status(msg):
            if msg:
                statuses.append(msg)

        execute_recovery_async(callback=on_status)
        import time
        time.sleep(0.8)

        mock_term.assert_called_once()
        mock_focus.assert_called_once()
        mock_watcher.assert_called_once()
        self.assertIn("CLOSING GAME...", statuses)
        self.assertIn("RESTORING LAUNCHER...", statuses)
        self.assertIn("CLICK LAUNCH IN RSI", statuses)


if __name__ == '__main__':
    unittest.main()
