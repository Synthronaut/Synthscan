import tempfile
from pathlib import Path
import unittest
from native_bridge import optional_state


class FirstRunStateTests(unittest.TestCase):
    def test_absent_and_damaged_preferences_do_not_stop_first_run_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'native_settings.json'
            self.assertEqual(optional_state(path),{})
            path.write_text('damaged settings')
            self.assertEqual(optional_state(path),{})
            self.assertEqual(path.read_text(),'damaged settings')
            path.write_text('{"hud_mode":"hangars"}')
            self.assertEqual(optional_state(path),{'hud_mode':'hangars'})
