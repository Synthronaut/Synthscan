"""Actual signature/ZIP/file transactions; never starts a GUI or controls a game."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from app_updates import stage,manifest,activate,recover,active_token,inspect_archive,safe_member,write,AppUpdateService,UpdateDeferred
from update_signing import generate_key,envelope,verify,canonical,signature,protect


@unittest.skipUnless(os.name=='nt','Windows CNG release signing')
class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private,cls.public=generate_key();cls.key_id=hashlib.sha256(cls.public).hexdigest()[:16]
        cls.trust=dict(schema=1,keys={cls.key_id:base64.b64encode(cls.public).decode()},
                       manifest_url='https://updates.example.test/current.json',allowed_hosts=['updates.example.test'])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.root=self.directory/'Programs/SynthScan';self.root.mkdir(parents=True)
        self.profile=self.directory/'profile';self.profile.mkdir()
        (self.root/'SynthScan.exe').write_bytes(b'previous stable bootstrap')
        write(self.root/'release.json',dict(version='0.1.0-alpha.9',setup_schema=1,updater_schema=1))
        write(self.root/'update_trust.json',self.trust)
        write(self.profile/'setup_result.json',dict(complete=True,app_version='0.1.0-alpha.9',build_id='unchanged-build'))
        (self.profile/'inventory.json').write_bytes(b'player inventory must survive')
        write(self.profile/'workspace_library.json',dict(rows=[dict(id='item')]))
        self.now=time.time();self.url='https://updates.example.test/app.zip'
        self.make_payload()
    def tearDown(self):self.temp.cleanup()
    def make_payload(self,extra=None):
        self.files={name:b'test payload' for name in ('SynthScan.exe','app_launcher.py','app_updates.py','update_agent.py','update_signing.py','update_trust.json',
                    'runtime/pythonw.exe','runtime/python314.dll','runtime/Lib/encodings/__init__.py','dist/native/SynthScan.exe','dist/native/build_manifest.json')}
        self.files['release.json']=canonical(dict(version='0.1.0-alpha.10',updater_schema=1,setup_schema=1))
        self.files['update_trust.json']=canonical(self.trust)
        if extra:self.files.update(extra)
        integrity=dict(version='0.1.0-alpha.10',files={name:hashlib.sha256(raw).hexdigest() for name,raw in self.files.items()})
        self.files['release_integrity.json']=canonical(integrity)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as zipped:
            for name,raw in self.files.items():zipped.writestr('SynthScan/'+name,raw)
        self.archive=buffer.getvalue();self.sha=hashlib.sha256(self.archive).hexdigest()
        self.payload=dict(schema=1,kind='application',platform='windows-x64',version='0.1.0-alpha.10',sequence=100,
                          issued_at=self.now-1,expires_at=self.now+86400,minimum_updater=1,url=self.url,
                          sha256=self.sha,size=len(self.archive),unpacked_size=sum(map(len,self.files.values())))
    def signed(self,**changes):return canonical(envelope(dict(self.payload,**changes),self.private,self.public))
    def opener(self,url,trust):return io.BytesIO(self.signed() if url==self.trust['manifest_url'] else self.archive)
    def staged(self):return stage(self.root,self.profile,self.trust,self.opener,self.now)
    def test_signature_authentication_and_wrong_key(self):
        self.assertEqual(verify(self.signed(),self.trust)['sha256'],self.sha)
        value=json.loads(self.signed());value['signature']=base64.b64encode(b'\0'*64).decode()
        with self.assertRaises(ValueError):verify(canonical(value),self.trust)
        with self.assertRaises(ValueError):verify(self.signed(),dict(keys={}))
    def test_dpapi_private_key_roundtrip(self):
        encrypted=protect(self.private);self.assertNotIn(self.private,encrypted);self.assertEqual(protect(encrypted,True),self.private)
    def test_signed_payload_duplicate_json_keys_are_rejected(self):
        raw=b'{"schema":1,"schema":2}'
        value=dict(schema=1,key_id=self.key_id,payload=base64.b64encode(raw).decode(),signature=base64.b64encode(signature(self.private,raw)).decode())
        with self.assertRaises(ValueError):verify(canonical(value),self.trust)
    def test_expired_wrong_platform_and_untrusted_url_are_rejected(self):
        for changes in (dict(expires_at=self.now-1),dict(platform='linux-arm64'),dict(url='http://updates.example.test/app.zip'),dict(url='https://elsewhere.test/app.zip')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):manifest(self.signed(**changes),self.trust,self.now)
    def test_stage_verifies_whole_package_without_replacing_current_app(self):
        result=self.staged();self.assertEqual(result['status'],'staged')
        self.assertEqual((self.root/'SynthScan.exe').read_bytes(),b'previous stable bootstrap')
        self.assertFalse((self.root/'active_version.txt').exists())
        self.assertEqual(json.loads((self.profile/'updates/pending.json').read_text())['sha256'],self.sha)
    def test_download_corruption_retains_current_app_and_leaves_no_pending_update(self):
        def broken(url,trust):return io.BytesIO(self.signed() if url==self.trust['manifest_url'] else self.archive+b'bad')
        with self.assertRaises(ValueError):stage(self.root,self.profile,self.trust,broken,self.now)
        self.assertFalse((self.profile/'updates/pending.json').exists());self.assertFalse(list((self.profile/'updates').glob('*.part')))
    def test_payload_path_traversal_and_windows_aliases_are_rejected(self):
        for name in ('SynthScan/../escape','/SynthScan/x','SynthScan/C:/x','SynthScan/a\\b','SynthScan/a./x','SynthScan/CON.txt','SynthScan/a//b'):
            with self.subTest(name=name),self.assertRaises(ValueError):safe_member(name)
        self.make_payload({'../escape':b'bad'})
        with self.assertRaises(ValueError):self.staged()
        self.assertFalse((self.directory/'escape').exists())
    def test_equal_sequence_cannot_identify_another_payload(self):
        write(self.profile/'updates/verified.json',dict(sequence=100,sha256='f'*64))
        with self.assertRaises(ValueError):self.staged()
    def test_successful_activation_preserves_stable_launcher_and_profile(self):
        self.staged();launches=[]
        result=activate(self.root,self.root,self.profile,health=lambda target:True,launch=lambda target,health:launches.append(target),trust=self.trust)
        target=self.root/'versions'/self.sha
        self.assertEqual(result['phase'],'applied');self.assertEqual(active_token(self.root),self.sha)
        self.assertEqual((self.root/'SynthScan.exe').read_bytes(),b'previous stable bootstrap')
        self.assertEqual((self.profile/'inventory.json').read_bytes(),b'player inventory must survive')
        self.assertEqual(json.loads((self.profile/'setup_result.json').read_text())['app_version'],'0.1.0-alpha.10')
        self.assertEqual(json.loads((target/'dist/native/native_runtime.json').read_text())['workspace'],str(target))
        self.assertEqual(launches,[target]);self.assertFalse((self.root/'activation_pending.txt').exists())
    def test_failed_readiness_rolls_back_and_quarantines_same_payload(self):
        self.staged()
        with self.assertRaises(RuntimeError):activate(self.root,self.root,self.profile,health=lambda target:False,launch=lambda *args:None,trust=self.trust)
        self.assertIsNone(active_token(self.root))
        self.assertEqual(json.loads((self.profile/'setup_result.json').read_text())['app_version'],'0.1.0-alpha.9')
        self.assertEqual(json.loads((self.profile/'updates/transaction.json').read_text())['phase'],'rolled_back')
        self.assertEqual(self.staged()['status'],'rejected')
    def test_interrupted_activation_is_recoverable_from_stable_runtime(self):
        class PowerLoss(BaseException):pass
        self.staged()
        def lost(*args):raise PowerLoss()
        with self.assertRaises(PowerLoss):activate(self.root,self.root,self.profile,health=lost,launch=lambda *args:None,trust=self.trust)
        self.assertEqual(active_token(self.root),self.sha);self.assertTrue((self.root/'activation_pending.txt').exists())
        self.assertEqual(recover(self.root,self.profile)['phase'],'rolled_back');self.assertIsNone(active_token(self.root))
        self.assertFalse((self.root/'activation_pending.txt').exists())
    def test_recovery_rejects_an_unsafe_previous_pointer(self):
        write(self.profile/'updates/transaction.json',dict(schema=1,phase='activated',previous='../../outside'))
        with self.assertRaises(ValueError):recover(self.root,self.profile)
    def test_game_start_during_preparation_defers_without_quarantining_payload(self):
        self.staged()
        with self.assertRaises(UpdateDeferred):activate(self.root,self.root,self.profile,health=lambda target:True,launch=lambda *args:None,trust=self.trust,can_activate=lambda:False)
        self.assertIsNone(active_token(self.root));self.assertTrue((self.profile/'updates/pending.json').exists())
        self.assertFalse((self.profile/'updates/failed.json').exists())
    def test_no_activation_or_agent_preparation_while_game_is_running(self):
        self.staged();service=AppUpdateService(self.profile,self.root)
        try:
            with patch('app_updates.stage',return_value=dict(status='staged')),patch('update_agent.idle_windows') as idle:
                service.tick(game_running=True);service.future.result(timeout=3);service.tick(game_running=True)
                idle.assert_not_called();self.assertIsNone(service.preparing);self.assertFalse(service.started)
        finally:service.close()

    def test_early_agent_exit_allows_automatic_retry_without_app_restart(self):
        from unittest.mock import Mock
        self.staged();service=AppUpdateService(self.profile,self.root)
        service.started=True;service.agent_process=Mock();service.agent_process.poll.return_value=0
        service.next_check=time.time()+3600
        try:
            service.tick(game_running=True)
            self.assertFalse(service.started);self.assertIsNone(service.agent_process)
            self.assertGreater(service.prepare_after,time.time())
        finally:service.close()


if __name__=='__main__':unittest.main()
