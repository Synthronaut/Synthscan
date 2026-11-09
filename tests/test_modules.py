"""Exercise signed feature installs, removals and rollback without windows/input."""
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

from app_updates import activate,active_token,write,load,stage
from feature_modules import FEATURES,DEFAULTS,resolve,installed
from module_distribution import catalog,prepare,inspect_package,activation_payload
from update_signing import canonical,envelope,generate_key


class ModuleMatrixTests(unittest.TestCase):
    def test_retired_notes_are_removed_from_existing_choices(self):
        self.assertNotIn('notes',FEATURES)
        self.assertEqual(resolve(['notes','people']),['people'])
        with tempfile.TemporaryDirectory() as temporary:
            write(Path(temporary)/'release.json',dict(module_schema=1,modules=['notes','people']))
            self.assertEqual(installed(temporary),{'people'})
    def test_release_matrix_covers_each_feature_alone_and_removed(self):
        from tools.verify_modules import selection_matrix
        cases=[set(row) for row in selection_matrix()]
        self.assertEqual(len(cases),len({tuple(sorted(row)) for row in cases}))
        self.assertIn(set(),cases);self.assertIn(set(FEATURES),cases)
        for name in FEATURES:
            self.assertIn(set(resolve([name])),cases)
            self.assertTrue(any(name not in row and len(row)>=len(FEATURES)-2 for row in cases),name)
        for row in cases:self.assertEqual(row,set(resolve(row)))


@unittest.skipUnless(os.name=='nt','Windows release-signing primitives')
class ModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private,public=generate_key();cls.public=public
        cls.trust=dict(schema=1,keys={hashlib.sha256(public).hexdigest()[:16]:base64.b64encode(public).decode()},
            manifest_url='https://example.test/application.json',standard_manifest_url='https://example.test/application-standard.json',modules_manifest_url='https://example.test/modules.json',allowed_hosts=['example.test'])
    def setUp(self):
        maintenance=patch('app_updates.module_maintenance');maintenance.start();self.addCleanup(maintenance.stop)
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.root=self.base/'app';self.root.mkdir();self.profile=self.base/'profile';self.profile.mkdir()
        self.version='0.1.0-alpha.11';self.now=time.time()
        write(self.root/'release.json',dict(version=self.version,module_schema=1,modules=[],edition='standard',setup_schema=1))
        write(self.root/'update_trust.json',self.trust);(self.root/'SynthScan.exe').write_bytes(b'bootstrap')
        (self.profile/'inventory.json').write_bytes(b'private record')
        self.archives={};self.items={}
        core={'release.json':canonical(dict(version=self.version,module_schema=1,edition='standard',updater_schema=1,setup_schema=1)),
              'SynthScan.exe':b'bootstrap','dist/native/SynthScan.exe':b'standard engine','dist/native/build_manifest.json':b'{}',
              'update_trust.json':canonical(self.trust),'module_setup.py':b'pass'}
        for name in ('core',*FEATURES):
            files=core if name=='core' else {'features/'+name+'.json':canonical(dict(id=name))}
            if name=='mining_recognition':files=dict(files,**{'runtime/Lib/site-packages/onnxruntime/example.dll':b'optional OCR','dist/native/SynthScan.exe':b'full engine','dist/native/build_manifest.json':b'{}'})
            if name=='mining_tools':files=dict(files,**{'mining_diary.py':b'optional provider'})
            self.package(name,files)
        self.value=dict(schema=1,kind='modules',platform='windows-x64',version=self.version,sequence=1,minimum_manager=1,
            issued_at=self.now-1,expires_at=self.now+86400,packages=self.items)
    def tearDown(self):self.tmp.cleanup()
    def package(self,name,files):
        inventory=canonical(dict(schema=1,id=name,version=self.version,files={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}))
        content=dict(files,**{'component.json':inventory});buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            for relative,raw in content.items():archive.writestr('SynthScan/'+relative,raw)
        raw=buffer.getvalue();url='https://example.test/'+name+'.zip';self.archives[url]=raw
        self.items[name]=dict(id=name,version=self.version,requires=[] if name=='core' else list(FEATURES[name][1]),url=url,
            size=len(raw),unpacked_size=sum(map(len,content.values())),sha256=hashlib.sha256(raw).hexdigest(),inventory_sha256=hashlib.sha256(inventory).hexdigest())
    def signed(self,**changes):return canonical(envelope(dict(self.value,**changes),self.private,self.public))
    def opener(self,url,trust):
        if url!=self.trust['modules_manifest_url']:return io.BytesIO(self.archives[url])
        payload=canonical(self.value)
        if getattr(self,'published_payload',None)!=payload:self.published_payload=payload;self.published_raw=self.signed()
        return io.BytesIO(self.published_raw)
    def prepare(self,selected):return prepare(self.root,self.profile,selected,self.trust,self.opener,now=self.now)
    def apply(self,current=None,health=lambda path:True,can=lambda:True):
        return activate(self.root,current or self.root,self.profile,health,lambda *args:None,trust=self.trust,can_activate=can)
    def active(self):return self.root/'versions'/active_token(self.root)
    def test_defaults_and_dependency(self):
        self.assertEqual(set(DEFAULTS),set(FEATURES));self.assertEqual(resolve(['mining_recognition']),['mining_recognition','mining_tools'])
        with self.assertRaises(ValueError):resolve(['unknown'])
    def test_core_only_has_no_optional_provider_or_ocr(self):
        self.prepare([]);self.apply();root=self.active()
        self.assertEqual(installed(root),set());self.assertFalse((root/'mining_diary.py').exists())
        self.assertFalse((root/'runtime/Lib/site-packages/onnxruntime').exists())
        self.assertEqual((self.profile/'inventory.json').read_bytes(),b'private record')
    def test_add_recognition_resolves_dependency_and_switches_engine(self):
        self.prepare(['mining_recognition']);self.apply();root=self.active()
        self.assertEqual(installed(root),{'mining_recognition','mining_tools'})
        self.assertEqual((root/'dist/native/SynthScan.exe').read_bytes(),b'full engine')
        self.assertEqual(load(root/'release.json')['edition'],'full')
    def test_removal_builds_a_fresh_screen_free_tree_and_keeps_data(self):
        self.prepare(['mining_recognition']);self.apply();old=self.active()
        prepare(old,self.profile,[],self.trust,self.opener,now=self.now);self.apply(old);root=self.active()
        self.assertEqual(installed(root),set());self.assertEqual((root/'dist/native/SynthScan.exe').read_bytes(),b'standard engine')
        self.assertFalse((root/'mining_diary.py').exists());self.assertFalse((root/'runtime/Lib/site-packages/onnxruntime').exists())
        self.assertEqual((self.profile/'inventory.json').read_bytes(),b'private record')
    def test_signature_tampering_unknown_keys_and_expiry_fail_closed(self):
        raw=json.loads(self.signed());raw['signature']=base64.b64encode(bytes(64)).decode()
        for candidate in (canonical(raw),self.signed(expires_at=self.now-1),self.signed(platform='linux')):
            with self.assertRaises(ValueError):catalog(candidate,self.trust,self.now)
        with self.assertRaises(ValueError):catalog(self.signed(),dict(keys={}),self.now)
    def test_conflicting_module_files_rejected_before_activation(self):
        self.package('acceptance',{'dist/native/SynthScan.exe':b'bad override'})
        self.prepare(['acceptance'])
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.apply()
        self.assertIsNone(active_token(self.root))
    def test_partial_download_retains_working_install_and_no_pending_plan(self):
        def broken(url,trust):return io.BytesIO(self.signed() if url==self.trust['modules_manifest_url'] else b'partial')
        with self.assertRaises(ValueError):prepare(self.root,self.profile,['missions'],self.trust,broken,now=self.now)
        self.assertIsNone(active_token(self.root));self.assertFalse((self.profile/'updates/pending.json').exists())
    def test_archive_changed_after_download_is_rejected(self):
        self.prepare(['missions']);path=next((self.profile/'updates/modules-cache').glob('*.zip'));path.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.apply()
        self.assertIsNone(active_token(self.root))
    def test_health_failure_rolls_back_and_preserves_profile(self):
        self.prepare(['missions'])
        with self.assertRaises(RuntimeError):self.apply(health=lambda path:False)
        self.assertIsNone(active_token(self.root));self.assertEqual((self.profile/'inventory.json').read_bytes(),b'private record')
    def test_activity_resume_defers_switch(self):
        self.prepare(['missions'])
        from app_updates import UpdateDeferred
        with self.assertRaises(UpdateDeferred):self.apply(can=lambda:False)
        self.assertIsNone(active_token(self.root));self.assertTrue((self.profile/'updates/pending.json').exists())
    def test_catalog_sequence_rollback_rejected(self):
        self.prepare([]);self.value['sequence']=0
        with self.assertRaises(ValueError):self.prepare([])
        self.value['sequence']=1;self.value['expires_at']-=1
        with self.assertRaisesRegex(ValueError,'reuse'):self.prepare([])
    def test_automatic_updates_preserve_selection(self):
        self.prepare(['acceptance']);self.apply();root=self.active()
        result=stage(root,self.profile,self.trust,self.opener,self.now)
        self.assertEqual(result['status'],'current');self.assertEqual(installed(root),{'acceptance'})

    def test_pending_selection_from_before_notes_removal_can_activate(self):
        self.prepare(['people'])
        path=self.profile/'updates/pending.json';pending=load(path)
        pending['modules']=['notes','people']
        pending['sha256']=hashlib.sha256(canonical(dict(schema=1,catalog=pending['catalog'],modules=['notes','people']))).hexdigest()
        write(path,pending);self.apply()
        self.assertEqual(installed(self.active()),{'people'})
        self.assertEqual(load(self.active()/'release.json')['modules'],['people'])
        self.assertEqual((self.profile/'inventory.json').read_bytes(),b'private record')
    def test_windows_path_alias_and_traversal_rejected(self):
        for relative in ('../escape','a//b','CON.txt','a\\b'):
            self.package('acceptance',{relative:b'bad'});item=self.items['acceptance'];path=self.base/'unsafe.zip';path.write_bytes(self.archives[item['url']])
            with self.assertRaises(ValueError):inspect_package(path,item)

    def legacy_inventory(self):
        (self.root/'legacy_reader.py').write_bytes(b'obsolete reader code')
        inventory={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        write(self.root/'release_integrity.json',dict(version=self.version,files=inventory))
        return inventory
    def test_recovery_refresh_removes_legacy_reader_from_base_install(self):
        from module_setup import refresh_recovery_core
        self.legacy_inventory();self.prepare([]);self.apply()
        refresh_recovery_core(self.root,self.profile,self.active())
        self.assertFalse((self.root/'legacy_reader.py').exists())
        self.assertEqual(load(self.root/'release.json')['module_schema'],1)
        self.assertEqual((self.profile/'inventory.json').read_bytes(),b'private record')
    def test_recovery_refresh_preserves_external_app_edits(self):
        from module_setup import refresh_recovery_core
        self.legacy_inventory();(self.root/'legacy_reader.py').write_bytes(b'user edit')
        self.prepare([]);self.apply()
        with self.assertRaisesRegex(ValueError,'Externally changed'):refresh_recovery_core(self.root,self.profile,self.active())
        self.assertEqual((self.root/'legacy_reader.py').read_bytes(),b'user edit')
    def test_recovery_copy_failure_restores_previous_files(self):
        from module_setup import refresh_recovery_core
        import app_updates
        self.legacy_inventory();before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.prepare([]);self.apply();original=app_updates.replace_file;calls=0
        def fail_once(source,target):
            nonlocal calls
            calls+=1
            if calls==2:raise PermissionError('simulated locked file')
            return original(source,target)
        with patch('app_updates.replace_file',side_effect=fail_once),self.assertRaises(PermissionError):refresh_recovery_core(self.root,self.profile,self.active())
        for relative,raw in before.items():self.assertEqual((self.root/relative).read_bytes(),raw,relative)


if __name__=='__main__':unittest.main()
