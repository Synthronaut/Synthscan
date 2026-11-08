import threading
import unittest
from unittest.mock import Mock

from finder_services import FinderServices


class FinderServicesTests(unittest.TestCase):
    def test_one_failed_source_does_not_block_other_finder_source(self):
        shops, market = Mock(), Mock()
        shops.tick.side_effect = OSError('unavailable')
        worker = FinderServices(shops, market)
        worker.current_patch = '4.10.2'
        with self.assertLogs(level='ERROR'):
            worker.tick()
        market.tick.assert_called_once_with(current_patch='4.10.2')
        worker.close()

    def test_finder_runs_without_waiting_for_session_collector_and_stops_cleanly(self):
        ready = threading.Event()
        shops, market = Mock(), Mock()
        market.tick.side_effect = lambda **kw: ready.set()
        worker = FinderServices(shops, market)
        worker.start()
        try:
            self.assertTrue(ready.wait(2), 'Finder should run without a session tick')
        finally:
            worker.close()
        self.assertFalse(worker.thread.is_alive())
        shops.close.assert_called_once()
        market.close.assert_called_once()
