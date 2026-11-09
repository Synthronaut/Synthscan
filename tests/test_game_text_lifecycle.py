import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import game_text_lifecycle as lifecycle
from game_text_lifecycle import Manager,INI,CFG,read_dacl,write_dacl


class GameTextLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.game=self.root/'LIVE';self.game.mkdir()
        self.profile=self.root/'profile';self.manager=Manager(self.game,self.profile)
    def put(self,name,raw):
        path=self.game/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return path
    def test_fresh_install_removes_only_owned_files_and_empty_directories(self):
        self.manager.write(INI,b'Name=SynthScan\n');self.manager.write(CFG,b'g_language = english\r\n')
        keep=self.put('screenshots/keep.png',b'private fixture')
        result=self.manager.restore()
        self.assertFalse(result['conflicts']);self.assertFalse((self.game/INI).exists());self.assertFalse((self.game/CFG).exists())
        self.assertFalse((self.game/'Data').exists());self.assertEqual(keep.read_bytes(),b'private fixture')
        self.assertTrue(list(self.profile.rglob('*-original.bin'))==[])
        self.assertTrue(list(self.profile.rglob('*-written.bin')))
    def test_original_files_restore_byte_exact_and_backups_stay_outside_game(self):
        original=b'\xef\xbb\xbfName=Original\r\n';self.put(INI,original);self.put(CFG,b'clouds=0\r\n')
        self.manager.write(INI,b'Name=Changed\n');self.manager.write(CFG,b'clouds=0\r\ng_language = english\r\n')
        self.assertEqual(sorted(p.relative_to(self.game).as_posix() for p in self.game.rglob('*') if p.is_file()),[INI,CFG])
        self.assertFalse(self.manager.restore()['conflicts']);self.assertEqual((self.game/INI).read_bytes(),original)
        self.assertEqual((self.game/CFG).read_bytes(),b'clouds=0\r\n')
    def test_disable_blocks_future_writes_and_can_reenable_after_restore(self):
        self.manager.write(INI,b'one');self.manager.restore()
        with self.assertRaisesRegex(ValueError,'disabled'):self.manager.write(INI,b'two')
        self.manager.set_enabled(True);self.manager.write(INI,b'two');self.manager.restore()
        self.assertFalse((self.game/INI).exists())
    def test_external_cfg_edits_keep_all_settings_except_our_language_line(self):
        self.put(CFG,b'clouds=0\n');self.manager.write(CFG,b'clouds=0\ng_language = english\n')
        self.put(CFG,b'clouds=0\ng_language = english\nmy_setting=42\n')
        self.assertFalse(self.manager.restore()['conflicts'])
        self.assertEqual((self.game/CFG).read_bytes(),b'clouds=0\nmy_setting=42\n')
    def test_preexisting_language_is_kept(self):
        self.put(CFG,b'g_language = english\nclouds=0\n');self.manager.write(CFG,b'g_language = english\nclouds=1\n')
        self.manager.restore();self.assertEqual((self.game/CFG).read_bytes(),b'g_language = english\nclouds=0\n')
    def test_external_language_change_is_kept(self):
        self.manager.write(CFG,b'g_language = english\n');self.put(CFG,b'g_language = german\n')
        self.manager.restore();self.assertEqual((self.game/CFG).read_bytes(),b'g_language = german\n')
    def test_existing_localization_three_way_restore_preserves_other_edits(self):
        self.put(INI,b'Name=Base\nOther=Old\n');self.manager.write(INI,b'Name=Rep\nOther=Old\nAdded=Owned\n')
        self.put(INI,b'Name=Rep\nOther=Custom\nAdded=Owned\nNew=User\n')
        result=self.manager.restore();self.assertFalse(result['conflicts'])
        self.assertEqual((self.game/INI).read_bytes(),b'Name=Base\nOther=Custom\nNew=User\n')
    def test_same_key_conflict_preserves_user_value(self):
        self.put(INI,b'Name=Base\n');self.manager.write(INI,b'Name=Rep\n');self.put(INI,b'Name=User\n')
        self.assertIn(INI,self.manager.restore()['conflicts']);self.assertEqual((self.game/INI).read_bytes(),b'Name=User\n')
    def test_new_file_external_edit_is_never_deleted(self):
        self.manager.write(INI,b'Name=Rep\n');self.put(INI,b'Name=User\n')
        self.assertIn(INI,self.manager.restore()['conflicts']);self.assertTrue((self.game/INI).exists())
    def test_changed_game_text_is_not_overwritten_on_next_update(self):
        self.manager.write(INI,b'Name=Rep\n');self.put(INI,b'Name=User\n')
        with self.assertRaisesRegex(ValueError,'outside'):self.manager.write(INI,b'Name=New\n')
    def test_interrupted_replace_keeps_original_and_retry_works(self):
        self.put(INI,b'original');replace=os.replace
        def fail(source,destination):
            if Path(destination)==self.game/INI:raise PermissionError('locked fixture')
            return replace(source,destination)
        with patch('game_text_lifecycle.os.replace',side_effect=fail):
            with self.assertRaises(PermissionError):self.manager.write(INI,b'new')
        self.assertEqual((self.game/INI).read_bytes(),b'original');self.assertFalse(list(self.game.rglob('*.tmp')))
        self.manager.write(INI,b'new');self.manager.restore();self.assertEqual((self.game/INI).read_bytes(),b'original')
    def test_crash_after_replace_recovers_durable_pending_record(self):
        original_store=self.manager.store
        def crash(state):
            if state['files'].get(INI,{}).get('touched'):raise OSError('simulated power loss')
            original_store(state)
        with patch.object(self.manager,'store',side_effect=crash):
            with self.assertRaises(OSError):self.manager.write(INI,b'written before crash')
        self.assertFalse(Manager(self.game,self.profile).restore()['conflicts']);self.assertFalse((self.game/INI).exists())
    def test_legacy_requires_explicit_archival_and_generic_backups_are_untouched(self):
        raw=b'bedrock_game_texts=1\nName=Legacy\n';self.put(INI,raw);backup=self.put(INI+'.bak',b'unknown backup')
        self.assertIn(INI,self.manager.restore()['legacy']);self.assertEqual((self.game/INI).read_bytes(),raw)
        self.manager.restore(archive_legacy=True);self.assertFalse((self.game/INI).exists());self.assertEqual(backup.read_bytes(),b'unknown backup')
        self.assertEqual(next(self.profile.rglob('*legacy-archive.bin')).read_bytes(),raw)
    def test_hardlinks_rejected_without_touching_other_file(self):
        other=self.put('other.txt',b'private');(self.game/'Data/Localization/english').mkdir(parents=True)
        os.link(other,self.game/INI)
        with self.assertRaisesRegex(ValueError,'Linked'):self.manager.write(INI,b'changed')
        self.assertEqual(other.read_bytes(),b'private')
    def test_unmanaged_targets_rejected(self):
        for name in ['Data.p4k','../outside','Bin64/StarCitizen.exe']:
            with self.assertRaises(ValueError):self.manager.write(name,b'bad')
    def test_tampered_original_is_not_restored(self):
        self.put(INI,b'original');self.manager.write(INI,b'new');entry=self.manager.read()['files'][INI]
        (self.manager.folder/entry['original']).write_bytes(b'corrupt')
        self.assertIn(INI,self.manager.restore()['conflicts']);self.assertEqual((self.game/INI).read_bytes(),b'new')
    @unittest.skipUnless(os.name=='nt','Windows ACL test')
    def test_acl_roundtrip_on_private_temporary_fixture(self):
        path=self.put(CFG,b'fixture');sddl=read_dacl(path);write_dacl(path,sddl);self.assertEqual(read_dacl(path),sddl)
    def test_permission_restore_preserves_external_acl_changes(self):
        self.put(CFG,b'fixture');state=self.manager.state();state['permissions']={CFG:dict(original='before',applied='ours')};self.manager.store(state)
        with patch('game_text_lifecycle.read_dacl',return_value='external'),patch('game_text_lifecycle.write_dacl') as write:
            self.assertEqual(self.manager.restore()['permissions_pending'],[CFG]);write.assert_not_called()
    def test_legacy_artifacts_archived_without_deleting_generic_backups(self):
        own=self.put(INI+'.synthscan-blueprints.bak',b'old owned backup');foreign=self.put(INI+'.bak',b'unknown')
        archived=lifecycle.archive_legacy_artifacts(self.game,self.profile)
        self.assertFalse(own.exists());self.assertEqual(foreign.read_bytes(),b'unknown')
        self.assertEqual((self.manager.folder/archived[0]['archive']).read_bytes(),b'old owned backup')
    def test_repeated_updates_do_not_accumulate_full_written_copies(self):
        self.put(INI,b'base')
        for number in range(5):self.manager.write(INI,str(number).encode())
        self.assertEqual(len(list(self.manager.folder.glob('*-written.bin'))),1)
        self.manager.restore();self.assertEqual((self.game/INI).read_bytes(),b'base')
    def test_incomplete_cleanup_cannot_be_silently_reenabled(self):
        self.manager.write(INI,b'ours');self.put(INI,b'external');self.manager.restore()
        with self.assertRaisesRegex(ValueError,'conflicts'):self.manager.set_enabled(True)
        self.assertFalse(lifecycle.enabled(self.game,self.profile))
    def test_interrupted_update_removes_only_its_journaled_temporary_file(self):
        self.put(INI,b'base');state=self.manager.state();entry=self.manager.capture(state,INI)
        temporary=self.put('Data/Localization/english/.synthscan-test.tmp',b'partial bytes')
        unknown=self.put('Data/Localization/english/.synthscan-unknown.tmp',b'leave alone')
        entry.update(pending_sha256=lifecycle.digest(b'new'),pending_temp=dict(name=temporary.name,file_id=temporary.stat().st_ino))
        self.manager.store(state);self.manager.restore()
        self.assertFalse(temporary.exists());self.assertEqual(unknown.read_bytes(),b'leave alone')


if __name__=='__main__':unittest.main()
