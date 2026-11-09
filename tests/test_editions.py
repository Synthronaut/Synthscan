"""Edition boundaries: signed update rejection and actual installed-file rules."""
import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app_edition
from edition_payload import forbidden_standard_path,check_update_edition
import test_app_updates as updates
from app_updates import stage,activate,inspect_archive,write
from update_signing import canonical

class EditionTests(unittest.TestCase):
    def test_standard_and_full_are_explicit_and_unknown_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for value in ('standard','full'):
                (root/'release.json').write_text(json.dumps({'edition':value}))
                self.assertEqual(app_edition.edition(root),value)
            (root/'release.json').write_text('{"edition":"typo"}')
            with self.assertRaises(ValueError):app_edition.edition(root)
    def test_standard_capture_command_is_not_a_preference(self):
        with patch('app_edition.edition',return_value='standard'):
            with self.assertRaises(PermissionError):app_edition.require_screen_reading()
    def test_capture_packages_and_models_are_forbidden_but_manual_tools_remain(self):
        for path in ('detector.py','native/synthscan/src/SynthGameCapture.cpp','runtime/Lib/site-packages/windows_capture/__init__.py','runtime/Lib/site-packages/PIL/ImageGrab.py','runtime/Lib/site-packages/onnxruntime/capi/a.dll','data/digits.onnx','dist/native/mining_worker.exe'):
            self.assertTrue(forbidden_standard_path(path),path)
        for path in ('native_bridge.py','account_permission.py','item_directory.py','refinery_orders.py','runtime/python314._pth','dist/native/SynthScan.exe'):
            self.assertFalse(forbidden_standard_path(path),path)
    def test_legacy_full_updates_remain_compatible(self):
        self.assertEqual(check_update_edition({},{}),'full')

class SignedEditionTests(updates.UpdateTests):
    def test_standard_rejects_signed_full_update_before_download(self):
        write(self.root/'release.json',dict(version='0.1.0-alpha.9',edition='standard'))
        with self.assertRaisesRegex(ValueError,'edition'):self.staged()
        self.assertFalse((self.profile/'updates/pending.json').exists())
    def test_full_rejects_signed_standard_update(self):
        self.payload['edition']='standard'
        with self.assertRaisesRegex(ValueError,'edition'):self.staged()
    def test_signed_manifest_and_archive_must_agree_on_edition(self):
        self.payload['edition']='standard'
        with io.BytesIO(self.archive) as f:
            with self.assertRaisesRegex(ValueError,'edition'):inspect_archive(f,self.payload)
    def test_standard_rejects_capture_file_even_with_valid_digests(self):
        self.make_payload({'release.json':canonical(dict(version='0.1.0-alpha.10',updater_schema=1,edition='standard')),'edition_payload.py':b'edition policy','detector.py':b'forbidden capture component'})
        self.payload['edition']='standard'
        with io.BytesIO(self.archive) as f:
            with self.assertRaisesRegex(ValueError,'screen-reading'):inspect_archive(f,self.payload)
    def test_activation_rechecks_edition_after_staging(self):
        self.staged()
        write(self.root/'release.json',dict(version='0.1.0-alpha.9',edition='standard'))
        with self.assertRaisesRegex(ValueError,'edition'):activate(self.root,self.root,self.profile,health=lambda _:True,launch=lambda *_:None,trust=self.trust)
