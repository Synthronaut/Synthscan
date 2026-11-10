import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_updates import version_key
from tools.compute_update_version import compute_next
from tools.package_modules import production_file
from tools.verify_auto_update import verify_auto_update


class TestAutoUpdateAndWebView(unittest.TestCase):
    def test_version_and_sequence_monotonicity(self):
        v1 = compute_next(base_version='0.1.0-alpha.11', run_number=10, check_remote=False)
        v2 = compute_next(base_version='0.1.0-alpha.11', run_number=11, check_remote=False)
        self.assertGreater(version_key(v1['version']), version_key('0.1.0-alpha.11'))
        self.assertGreater(version_key(v2['version']), version_key(v1['version']))
        self.assertGreater(v2['sequence'], 0)

    def test_ui_dist_bundled_in_production_and_source_excluded(self):
        self.assertTrue((ROOT / 'ui/dist/index.html').is_file())
        self.assertTrue((ROOT / 'ui/dist/assets/app.js').is_file())
        self.assertTrue((ROOT / 'ui/dist/assets/index.css').is_file())
        self.assertTrue(production_file('ui/dist/index.html'))
        self.assertTrue(production_file('ui/dist/assets/app.js'))
        self.assertTrue(production_file('ui/dist/assets/index.css'))
        self.assertFalse(production_file('ui/src/main.ts'))
        self.assertFalse(production_file('ui/package.json'))

    def test_isolated_update_and_rollback_lifecycle(self):
        report = verify_auto_update()
        self.assertTrue(report['passed'])
        self.assertTrue(report['modular_update_applied'])
        self.assertTrue(report['player_tags_preserved'])
        self.assertTrue(report['history_preserved'])
        self.assertTrue(report['broken_update_rolled_back'])
        self.assertTrue(report['broken_update_marked_rejected'])
        self.assertTrue(report['legacy_channel_update_applied'])


if __name__ == '__main__':
    unittest.main()
