import unittest
from unittest.mock import MagicMock, patch
import time

from memory_recovery_hud import MemoryRecoveryButton, memory_button_position, GAUGE_WIDTH_NORMAL, GAUGE_WIDTH_CONFIRM
from session_recovery import read_game_memory

class TestMemoryRecoveryHud(unittest.TestCase):
    def test_memory_button_position(self):
        bar = (500, 10, 800, 28)
        bounds = {'left': 0, 'top': 0, 'width': 2560, 'height': 1440}
        left, top, w, h = memory_button_position(bar, bounds, width=GAUGE_WIDTH_NORMAL)
        self.assertEqual(left, 500 - GAUGE_WIDTH_NORMAL - 3)
        self.assertEqual(top, 10)
        self.assertEqual(w, GAUGE_WIDTH_NORMAL)
        self.assertEqual(h, 28)

    def test_read_game_memory_no_pids(self):
        with patch('app_lifecycle.game_process_ids', return_value=frozenset()):
            res = read_game_memory()
            self.assertIsNone(res)

    def test_button_confirm_transition(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            btn = MemoryRecoveryButton(root, None, 1234)
            self.assertEqual(btn.confirm_until, 0.0)
            self.assertIsNone(btn.status_text)
            
            # First click: arms confirmation
            btn.click()
            self.assertTrue(btn.confirm_until > time.time())
            self.assertEqual(btn.width, GAUGE_WIDTH_CONFIRM)

            # Second click: triggers recovery
            with patch('memory_recovery_hud.execute_recovery_async') as mock_exec:
                btn.click()
                mock_exec.assert_called_once()
                self.assertEqual(btn.status_text, "CLEANING EAC...")
            btn.close()
        finally:
            root.destroy()

    def test_render_ribbon_with_memory_pill(self):
        import tkinter as tk
        from hud_appearance import render_original_bar
        root = tk.Tk()
        root.withdraw()
        try:
            class DummyRibbon:
                def __init__(self):
                    self.bar_canvas = tk.Canvas(root, width=800, height=24)
                    self.BAR_HEIGHT = 24
                    self.bar_width = 800
                    self.compact = True
                    self.state = {
                        'session_token': 'test_token',
                        'shard_id': '320',
                        'callsign': 'Shard 320',
                        'connection_status': 'connected'
                    }
                    self._last_rendered_key = None
                    self.memory_recovery = MagicMock()
                    self.memory_recovery.cache_state.return_value = (33.0, 0, None)
                    self.memory_recovery.get_memory_info.return_value = {'commit_gb': 33.2, 'working_set_gb': 14.0}
                    self.memory_recovery.status_text = None
                    self.memory_recovery.confirm_until = 0.0
                    self.shard_tracker = MagicMock()
                    self.shard_tracker.get_last_visited.return_value = None

            ribbon = DummyRibbon()
            render_original_bar(ribbon)
            self.assertIsNotNone(getattr(ribbon, 'memory_hit', None))
            hit = ribbon.memory_hit
            self.assertEqual(hit['left'], 12)
            # 12 + pill width (around 120-140px)
            self.assertTrue(hit['right'] > 100)
            self.assertTrue(ribbon._content_width > hit['right'])
        finally:
            root.destroy()

if __name__ == '__main__':
    unittest.main()
