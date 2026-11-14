import json
from pathlib import Path
import tempfile
import time
import unittest

from daylight_service import DaylightService
import daylight_catalogue as catalogue


class DaylightServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # copy bundled catalogue
        (self.dir/'daylight_catalogue.json').write_text(
            Path('data/daylight_catalogue.json').read_text(encoding='utf-8'),
            encoding='utf-8'
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_service_initialization_and_publish(self):
        now = 1762776000.0
        service = DaylightService(self.dir, owner=1234, clock=lambda: now, build=lambda: None)
        published = service.publish(force=True)
        self.assertTrue(published)

        state_path = self.dir/'daylight_state.json'
        self.assertTrue(state_path.is_file())
        data = json.loads(state_path.read_text(encoding='utf-8'))
        self.assertEqual(data['kind'], 'daylight_state')
        self.assertEqual(data['schema'], 1)
        self.assertEqual(data['owner_pid'], 1234)
        self.assertEqual(data['revision'], 1)
        self.assertIn('bodies', data['catalogue'])
        self.assertIn('sites', data['catalogue'])
        self.assertIn('Crusader', data['calibration'])

    def test_service_preferences_command(self):
        now = 1762776000.0
        service = DaylightService(self.dir, owner=1234, clock=lambda: now, build=lambda: None)
        cmd = {
            'action': 'daylight_preferences',
            'owner_pid': 1234,
            'at': now,
            'system': 'Stanton',
            'body': 'microTech',
            'site': 'New Babbage',
        }
        service.command(cmd, now)
        self.assertEqual(service.preferences['body'], 'microTech')
        self.assertEqual(service.preferences['site'], 'New Babbage')

        prefs_file = self.dir/'daylight_preferences.json'
        self.assertTrue(prefs_file.is_file())
        saved = json.loads(prefs_file.read_text(encoding='utf-8'))
        self.assertEqual(saved['body'], 'microTech')

    def test_service_drain_command_queue(self):
        now = 1762776000.0
        service = DaylightService(self.dir, owner=1234, clock=lambda: now, build=lambda: None)
        cmd_dir = self.dir/'daylight_commands'
        cmd_file = cmd_dir/'0001.json'
        cmd_file.write_text(json.dumps({
            'action': 'daylight_preferences',
            'owner_pid': 1234,
            'at': now,
            'system': 'Stanton',
            'body': 'ArcCorp',
            'site': 'Area18',
        }), encoding='utf-8')

        service.drain()
        self.assertFalse(cmd_file.exists())
        self.assertEqual(service.preferences['body'], 'ArcCorp')
        self.assertEqual(service.preferences['site'], 'Area18')


if __name__ == '__main__':
    unittest.main()
