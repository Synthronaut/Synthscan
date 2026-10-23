import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import queue
import threading

from fabricator_inbox import FabricatorInbox
from refinery_orders import RefineryOrderBook
from main import SynthScanApp


class Label:
    def __init__(self):
        self.options = {}
    def configure(self, **kwargs):
        self.options.update(kwargs)


class TerminalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = SynthScanApp.__new__(SynthScanApp)
        self.app.refinery_orders = RefineryOrderBook(self.root / 'orders.json')
        self.app.fabricator_inbox = FabricatorInbox(self.root / 'inbox.json')
        self.app.fabricator_pending = self.app.fabricator_inbox.pending
        self.app.terminal_panel = SimpleNamespace(status=Label())
        self.app.btn_direct_snap = Label()
        self.app.log_comms = lambda *a, **kw: None

    def tearDown(self):
        self.temp.cleanup()

    def test_reading_reaches_persistent_order_book_without_inventory_credit(self):
        order = dict(station='Levski', number=1, status='completed', parts=[dict(material='Iron', quality=874, scu=2.35)])
        with patch('main.add_haul_record', side_effect=AssertionError('Must not credit cargo')):
            self.app._apply_terminal_reading(dict(observed_at=100, orders=[order], blueprints=[]), manual=True)
            self.app._apply_terminal_reading(dict(observed_at=106, orders=[order], blueprints=[]))
        self.assertEqual(self.app.refinery_orders.snapshot()[0]['parts'][0]['quality'], 874)
        self.assertEqual(self.app.refinery_orders.snapshot()[0]['status'], 'completed')

    def test_blueprint_candidates_persist_without_unlocking(self):
        candidates = [dict(id='test-id', name='FR-76', confidence=.99, ownership='review')]
        self.app._apply_terminal_reading(dict(orders=[], blueprints=candidates))
        self.assertIn('test-id', FabricatorInbox(self.root / 'inbox.json').pending)
        self.app.fabricator_inbox.remove(['test-id'])
        self.assertEqual(FabricatorInbox(self.root / 'inbox.json').pending, {})

    def test_unrelated_screen_creates_no_files(self):
        self.app._apply_terminal_reading(dict(orders=[], blueprints=[]))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_worker_does_not_block_marker_loop(self):
        self.app.terminal_tracking = True
        self.app.last_terminal_scan = 0
        self.app.terminal_job_lock = threading.Lock()
        self.app.ui_events = queue.Queue()
        self.app.detector = SimpleNamespace(grab_full_game_monitor_pil=lambda: 'image')
        entered, release = threading.Event(), threading.Event()
        def slow_reader(*args, **kwargs):
            entered.set()
            release.wait(timeout=3)
            return dict(orders=[], blueprints=[])
        self.app._read_terminal_image = slow_reader
        with patch('main.is_star_citizen_foreground', return_value=True):
            self.app._poll_terminal_screens(100)
            try:
                self.assertTrue(entered.wait(timeout=2))
                self.assertTrue(self.app.terminal_job_lock.locked())
                # Another tick doesn't spawn a concurrent job.
                self.app._poll_terminal_screens(107)
            finally:
                release.set()
        event = self.app.ui_events.get(timeout=3)
        self.assertEqual(event[0], 'terminal_scan')

    def test_automatic_capture_is_foreground_only(self):
        self.app.terminal_tracking = True
        self.app.last_terminal_scan = 0
        with patch('main.is_star_citizen_foreground', return_value=False):
            # No detector or worker is needed if another app is foreground.
            self.app._poll_terminal_screens(100)


if __name__ == '__main__':
    unittest.main()
