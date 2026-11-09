import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from community_startup import owns_shortcut


class StartupOwnershipTests(unittest.TestCase):
    def test_versioned_runtime_owns_its_stable_startup_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);shortcut=root/'watcher.lnk';shortcut.write_bytes(b'fixture')
            value=json.dumps(dict(target=str(root/'SynthScan.exe'),arguments='--watch'))
            with patch('auto_launch.shortcut_path',return_value=shortcut),patch('installation.RELEASE',True),patch('installation.INSTALL_ROOT',root),patch('subprocess.check_output',return_value=value):
                self.assertTrue(owns_shortcut())
    def test_another_install_or_different_action_is_not_owned(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);shortcut=root/'watcher.lnk';shortcut.write_bytes(b'fixture')
            with patch('auto_launch.shortcut_path',return_value=shortcut),patch('installation.RELEASE',True),patch('installation.INSTALL_ROOT',root):
                for value in (dict(target=str(root/'another/SynthScan.exe'),arguments='--watch'),dict(target=str(root/'SynthScan.exe'),arguments='--uninstall')):
                    with patch('subprocess.check_output',return_value=json.dumps(value)):self.assertFalse(owns_shortcut())
