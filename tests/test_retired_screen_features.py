import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from native_bridge import SessionService
from activity_hud import toggle_request


class RetiredScreenFeatureTests(unittest.TestCase):
    def test_old_fabricator_commands_never_read_images_or_change_owned_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owned=root/'owned_blueprints.txt';owned.write_bytes(b'owned fixture\n')
            service=SessionService.__new__(SessionService)
            service.directory=root;service.seen_commands=set();service.last_command='';service.note=''
            with patch('screen_readers.read_image',side_effect=AssertionError('OCR must not run')):
                service.command(dict(id='one',action='fabricator_file',path='missing.png'))
                service.command(dict(id='two',action='fabricator_memory',frame_name='old-frame'))
            self.assertIn('retired',service.note)
            self.assertEqual(owned.read_bytes(),b'owned fixture\n')
            self.assertFalse((root/'fabricator_scan_inbox.json').exists())
            self.assertEqual(json.loads((root/'fabricator_frame_ack.json').read_text())['frame_name'],'old-frame')

    def test_server_hud_cannot_expand_a_missing_activity_module(self):
        state=dict(pid=42,at=100,activity_available=False)
        with self.assertRaises(ValueError):toggle_request(state,42,101)


if __name__=='__main__':unittest.main()
