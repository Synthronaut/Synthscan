import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from frame_telemetry import FrameWindow
from frame_source import read_client_fps
from telemetry_ipc import read_shared_json, publish_json


class FrameTests(unittest.TestCase):
    def add_frames(self, window, chain, count, hz, end, received_at):
        for index in range(count):
            stamp = end-(count-1-index)/hz
            window.add({'ProcessID': '42', 'SwapChainAddress': chain,
                        'QPCTime': str(round(stamp*10000000))}, received_at)

    def test_application_present_rate_and_dominant_swapchain(self):
        window = FrameWindow(42, 10000000)
        self.add_frames(window, 'game', 61, 60, 100, 100)
        self.add_frames(window, 'secondary', 11, 10, 100, 100)
        sample = window.sample(100, 200)
        self.assertAlmostEqual(sample['client_fps'], 60)
        self.assertEqual(sample['observed_at'], 200)
        self.assertIsNone(window.sample(103, 203))

    def test_batched_frames_keep_actual_event_time(self):
        window = FrameWindow(42, 10000000)
        self.add_frames(window, 'game', 31, 30, 100, 101.2)
        sample = window.sample(101.2, 201.2)
        self.assertAlmostEqual(sample['client_fps'], 30)
        self.assertAlmostEqual(sample['observed_at'], 200)

    def test_other_pid_future_and_duplicate_events_are_rejected(self):
        window = FrameWindow(42, 10000000)
        self.assertFalse(window.add({'ProcessID':'99','SwapChainAddress':'a','QPCTime':'1000000000'}, 100))
        self.assertFalse(window.add({'ProcessID':'42','SwapChainAddress':'a','QPCTime':'1100000000'}, 100))
        row = {'ProcessID':'42','SwapChainAddress':'a','QPCTime':'1000000000'}
        self.assertTrue(window.add(row, 100))
        self.assertFalse(window.add(row, 100))

    def test_source_pid_and_age_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'frames.json'
            value = {'game_pid':42,'status':'capturing','source':'presentmon_application_presents',
                     'written_at':200,'sample':{'source':'presentmon_application_presents',
                     'observed_at':199,'client_fps':60,'frames_in_window':60}}
            path.write_text(json.dumps(value))
            self.assertEqual(read_client_fps(200,path,{42})['client_fps'],60)
            self.assertIsNone(read_client_fps(200,path,{43}))
            self.assertIsNone(read_client_fps(204,path,{42}))


class IpcTests(unittest.TestCase):
    def test_shared_json_limits_and_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'metadata.json'
            self.assertTrue(publish_json(path, {'sample':12}))
            self.assertEqual(read_shared_json(path), {'sample':12})
            with self.assertRaises(ValueError):
                read_shared_json(path, 2)

    def test_transient_share_failure_retries_and_permanent_failure_returns_false(self):
        with patch('telemetry_ipc.atomic_json', side_effect=[PermissionError(), None]) as write:
            with patch('telemetry_ipc.time.sleep'):
                self.assertTrue(publish_json('unused', {'sample':12}))
            self.assertEqual(write.call_count, 2)
        with patch('telemetry_ipc.atomic_json', side_effect=PermissionError()):
            with patch('telemetry_ipc.time.sleep'):
                self.assertFalse(publish_json('unused', {'sample':12}))
