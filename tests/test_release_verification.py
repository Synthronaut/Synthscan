import hashlib,json,tempfile,unittest
from pathlib import Path
from tools.verify_reproducible import compare

class ReleaseVerificationTests(unittest.TestCase):
    def pair(self,folder):
        a=Path(folder)/'one';b=Path(folder)/'two'
        for p in (a,b):
            p.mkdir();(p/'SynthScan.exe').write_bytes(b'same unsigned artifact')
            manifest=dict(source_files={'src/example.cpp':'source-hash'},toolchain={'msvc':'pinned','sdk':'pinned'},binary_files={'SynthScan.exe':hashlib.sha256((p/'SynthScan.exe').read_bytes()).hexdigest()})
            (p/'build_manifest.json').write_text(json.dumps(manifest))
        return a,b
    def test_matching_artifacts_are_not_claimed_independently_reviewed(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder);result=compare(a,b);self.assertTrue(result['reproduced']);self.assertFalse(result['independent_review'])
    def test_modified_binary_cannot_hide_behind_unchanged_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder);(b/'SynthScan.exe').write_bytes(b'changed')
            with self.assertRaises(ValueError):compare(a,b)
    def test_internally_consistent_but_different_builds_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder);(b/'SynthScan.exe').write_bytes(b'changed');p=b/'build_manifest.json';m=json.loads(p.read_text());m['binary_files']['SynthScan.exe']=hashlib.sha256(b'changed').hexdigest();p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):compare(a,b)
    def test_source_and_toolchain_must_match(self):
        for key in ('source_files','toolchain'):
            with tempfile.TemporaryDirectory() as folder:
                a,b=self.pair(folder);p=b/'build_manifest.json';m=json.loads(p.read_text());m[key]={'changed':'value'};p.write_text(json.dumps(m))
                with self.assertRaises(ValueError):compare(a,b)
    def test_personal_runtime_settings_are_outside_binary_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=self.pair(folder);(a/'native_runtime.json').write_text('{"workspace":"one"}');(b/'native_runtime.json').write_text('{"workspace":"two"}')
            self.assertTrue(compare(a,b)['reproduced'])
