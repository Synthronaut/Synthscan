import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from network_source import read_network_ping


class NetworkSourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/'live.json'
        self.reader = SimpleNamespace(connected=True, full_shard_id='pub_use1_100_020',
                                      joined_at=90, ip_address='192.0.2.1', port='64000')
        self.state = {'status': 'capturing', 'source': 'game_udp_ping_pong',
                      'full_shard_id': self.reader.full_shard_id, 'joined_at': 90,
                      'endpoint': ['192.0.2.1', '64000'], 'written_at': 100,
                      'sample': {'source': 'game_udp_ping_pong', 'average_ms': 12.5,
                                 'timing_method': 'game_clock_calibrated',
                                 'average_samples': 4, 'observed_at': 99.5}}

    def tearDown(self):
        self.directory.cleanup()

    def read(self):
        self.path.write_text(json.dumps(self.state))
        return read_network_ping(self.reader, 100, self.path)

    def test_fresh_session_matched_sample(self):
        sample = self.read()
        self.assertEqual(sample['ping_ms'], 12.5)
        self.assertEqual(sample['observed_at'], 99.5)

    def test_old_join_and_other_endpoint_are_rejected(self):
        self.state['joined_at'] = 89
        self.assertIsNone(self.read())
        self.state['joined_at'] = 90
        self.state['endpoint'][1] = '65000'
        self.assertIsNone(self.read())

    def test_stopped_stale_and_future_reader_are_rejected(self):
        self.state['status'] = 'stopped'
        self.assertIsNone(self.read())
        self.state['status'] = 'capturing'
        self.state['written_at'] = 97
        self.assertIsNone(self.read())
        self.state['written_at'] = 100
        self.state['sample']['observed_at'] = 90
        self.assertIsNone(self.read())
        self.state['sample']['observed_at'] = 101
        self.assertIsNone(self.read())

    def test_nonfinite_and_insufficient_samples_are_rejected(self):
        self.state['sample']['average_ms'] = float('nan')
        self.assertIsNone(self.read())
        self.state['sample']['average_ms'] = 12
        self.state['sample']['average_samples'] = 1
        self.assertIsNone(self.read())

    def test_missing_truncated_and_oversized_files_are_unavailable(self):
        self.assertIsNone(read_network_ping(self.reader, 100, self.path))
        self.path.write_text('{')
        self.assertIsNone(read_network_ping(self.reader, 100, self.path))
        self.path.write_text(' '*17000)
        self.assertIsNone(read_network_ping(self.reader, 100, self.path))
