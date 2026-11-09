import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from installation import profile_scope
from game_text_lifecycle import Manager,INI,enabled


class IsolatedInstallationTests(unittest.TestCase):
    def test_validation_receipt_overrides_inherited_personal_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);profile=root/'separate profile';env=dict(LOCALAPPDATA=str(root),SYNTHSCAN_DATA_DIR=str(root/'SynthScan/native'))
            (root/'validation-install.txt').write_text(str(profile),encoding='utf-8-sig')
            self.assertEqual(profile_scope(root,env),(True,profile))
            (root/'validation-install.txt').write_text(env['SYNTHSCAN_DATA_DIR'])
            with self.assertRaises(ValueError):profile_scope(root,env)
    def test_test_install_cannot_write_restore_or_repair_real_game_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);game=root/'game';target=game/INI;target.parent.mkdir(parents=True);target.write_bytes(b'personal game text')
            manager=Manager(game,root/'test-profile')
            with patch('installation.ISOLATED_TEST',True):
                self.assertFalse(enabled(game,manager.profile))
                with self.assertRaises(ValueError):manager.write(INI,b'replacement')
                with self.assertRaises(ValueError):manager.set_enabled(True)
                from game_text_access import text_targets
                with self.assertRaises(ValueError):text_targets(game)
                self.assertTrue(manager.restore(archive_legacy=True)['isolated_test'])
            self.assertEqual(target.read_bytes(),b'personal game text')
