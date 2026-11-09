"""Patch simulations use disposable game folders, never an installed game."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import tempfile
import threading
import time
import unittest
import zlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import synthstrings_guard as guard
import game_text_lifecycle as lifecycle
from game_text_lifecycle import Manager, INI, CFG, save, load


BASE = ('\ufeff' + ''.join(f'key_{i}=CIG text {i} ~mission(Value)\\nNext\n' for i in range(1001))).encode('utf-8')
PACK = BASE + b'bedrock_game_texts=Written by SynthScan\n'


class PatchFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve();self.game = self.root / 'LIVE'
        (self.game / 'Bin64').mkdir(parents=True)
        (self.game / 'Bin64/StarCitizen.exe').write_bytes(b'not executable')
        self.manifest = self.game / 'build_manifest.id'
        self.manifest.write_text(json.dumps({'Data': {'BuildId': 'build-a', 'Version': '4.test'}}))
        self.archive = self.game / 'Data.p4k';self.archive.write_bytes(b'fake archive-a')
        self.now = time.time();os.utime(self.archive, (self.now - 500, self.now - 500))
        self.profile = self.root / 'profile';self.manager = Manager(self.game, self.profile)
        self.ini = self.game / INI

    def install(self, raw=PACK):
        self.manager.write(INI, raw, source=guard.snapshot(self.game))

    def patch_game(self):
        self.manifest.write_text(json.dumps({'Data': {'BuildId': 'build-b', 'Version': '4.test.1'}}))

    def fake_renderer(self, command, **kwargs):
        output = Path(command[3]);output.write_bytes(PACK)
        Path(str(output) + '.base').write_bytes(BASE)
        return subprocess.CompletedProcess(command, 0)

    def apply(self, renderer=None, pids=()):
        with patch('synthstrings_guard.current_pids', return_value=list(pids)), patch('game_text_lifecycle.subprocess.run', side_effect=renderer or self.fake_renderer):
            return lifecycle.apply_native(self.game, '-', self.profile)


class PatchGuardTests(PatchFixture, unittest.TestCase):

    def test_fingerprint_detects_manifest_only_patch_with_identical_archive_size_and_time(self):
        first = guard.snapshot(self.game)
        self.patch_game()
        self.assertNotEqual(first['fingerprint'], guard.snapshot(self.game)['fingerprint'])

    def test_fingerprint_isolated_between_same_named_channels(self):
        other = self.root / 'other/LIVE';other.mkdir(parents=True)
        (other / 'build_manifest.id').write_bytes(self.manifest.read_bytes())
        (other / 'Data.p4k').write_bytes(self.archive.read_bytes())
        self.assertNotEqual(guard.snapshot(self.game)['fingerprint'], guard.snapshot(other)['fingerprint'])

    def test_quarantines_before_waiting_even_with_no_game_running(self):
        self.install();self.patch_game()
        self.assertIsNone(guard.inspect_channel(self.game, self.profile, self.now, []))
        self.assertFalse(self.ini.exists());self.assertTrue(self.manager.read()['enabled'])
        self.assertEqual(guard.view(self.profile)['state'], 'fallback')
        self.assertEqual(next(self.manager.folder.glob('*patch-quarantine.bin')).read_bytes(), PACK)
        self.assertIsNotNone(guard.inspect_channel(self.game, self.profile, self.now + 121, []))

    def test_all_channels_quarantined_before_any_rebuild(self):
        self.install();self.patch_game()
        other = self.root / 'PTU';(other / 'Bin64').mkdir(parents=True)
        for name in ('build_manifest.id', 'Data.p4k', 'Bin64/StarCitizen.exe'):
            (other / name).write_bytes((self.game / name).read_bytes())
        Manager(other, self.profile).write(INI, PACK)
        guard.preflight(self.profile, [self.game, other], [], self.now)
        self.assertFalse(self.ini.exists());self.assertFalse((other / INI).exists())

    def test_unrelated_language_pack_is_never_touched_or_opted_in(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(BASE)
        self.assertIsNone(guard.inspect_channel(self.game, self.profile, self.now, []))
        self.assertEqual(self.ini.read_bytes(), BASE);self.assertFalse(self.manager.journal.exists())

    def test_external_changes_require_attention_and_are_preserved(self):
        self.install();self.ini.write_bytes(PACK + b'external=keep\n');self.patch_game()
        guard.inspect_channel(self.game, self.profile, self.now, [])
        self.assertTrue(self.ini.exists());self.assertEqual(guard.view(self.profile)['state'], 'attention')

    def test_resolving_external_change_clears_stale_attention(self):
        self.install();self.ini.write_bytes(PACK + b'external=keep\n')
        guard.inspect_channel(self.game, self.profile, self.now, [])
        self.assertEqual(guard.view(self.profile)['state'], 'attention')
        self.ini.write_bytes(PACK)
        guard.inspect_channel(self.game, self.profile, self.now + 1, [])
        self.assertEqual(guard.view(self.profile)['state'], 'ready')

    def test_disabled_preference_prevents_rebuild(self):
        self.install();self.manager.set_enabled(False);self.patch_game()
        self.assertIsNone(guard.inspect_channel(self.game, self.profile, self.now, []))
        self.assertEqual(guard.view(self.profile)['state'], 'disabled')

    def test_incomplete_manifest_still_quarantines_old_owned_file(self):
        self.install();self.manifest.write_text('{')
        guard.inspect_channel(self.game, self.profile, self.now, [12])
        self.assertFalse(self.ini.exists());self.assertTrue(guard.view(self.profile, [12])['restart_required'])

    def test_legacy_generated_file_is_archived_then_can_be_removed_without_old_restore(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(PACK)
        guard.inspect_channel(self.game, self.profile, self.now, [])
        self.assertFalse(self.ini.exists())
        self.assertFalse(self.manager.restore()['conflicts']);self.assertFalse(self.ini.exists())

    def test_suspended_annotation_writer_cannot_recreate_old_pack(self):
        self.install();self.manager.suspend()
        with self.assertRaisesRegex(ValueError, 'paused'):
            self.manager.write(INI, PACK)
        self.assertFalse(self.ini.exists())

    def test_build_change_blocks_annotation_writer_before_guard_next_poll(self):
        self.install();self.patch_game()
        with self.assertRaisesRegex(ValueError, 'build changed'):
            self.manager.write(INI, PACK)

    def test_successful_adaptation_records_restart_only_for_affected_game_process(self):
        self.install();self.patch_game()
        result = self.apply(pids=[21])
        self.assertTrue(result['written']);self.assertTrue(self.ini.exists())
        self.assertEqual(guard.view(self.profile, [21])['state'], 'adapted')
        self.assertTrue(guard.view(self.profile, [21])['restart_required'])
        self.assertFalse(guard.view(self.profile, [22])['restart_required'])
        self.assertFalse(guard.view(self.profile, [])['restart_required'])
        self.assertEqual(self.manager.read()['files'][INI]['source']['build'], 'build-b')

    def test_success_before_game_start_does_not_request_restart(self):
        self.install();self.patch_game();self.apply()
        self.assertFalse(guard.view(self.profile, [24])['restart_required'])

    def test_game_start_during_extraction_is_included_in_restart_notice(self):
        with patch('synthstrings_guard.current_pids', side_effect=[[], [30]]), patch('game_text_lifecycle.subprocess.run', side_effect=self.fake_renderer):
            self.assertTrue(lifecycle.apply_native(self.game, '-', self.profile)['written'])
        self.assertTrue(guard.view(self.profile, [30])['restart_required'])

    def test_failed_extraction_keeps_defaults_and_preference_for_automatic_retry(self):
        self.install();self.patch_game()
        result = self.apply(lambda *a, **kw: (_ for _ in ()).throw(subprocess.CalledProcessError(2, 'fixture')))
        self.assertTrue(result['fallback']);self.assertFalse(self.ini.exists())
        self.assertTrue(self.manager.read()['enabled'])
        self.assertEqual(guard.view(self.profile)['state'], 'fallback')

    def test_old_renderer_without_baseline_cannot_activate_unvalidated_text(self):
        def old_renderer(command, **kwargs):
            Path(command[3]).write_bytes(PACK)
        result = self.apply(old_renderer)
        self.assertTrue(result['fallback']);self.assertFalse(self.ini.exists())

    def test_patch_during_render_cannot_commit_output(self):
        self.install()
        def changing_renderer(command, **kwargs):
            self.fake_renderer(command, **kwargs);self.patch_game()
        result = self.apply(changing_renderer, [31])
        self.assertTrue(result['fallback']);self.assertFalse(self.ini.exists())
        self.assertTrue(guard.view(self.profile, [31])['restart_required'])

    def test_file_locked_during_quarantine_does_not_claim_defaults(self):
        self.install();self.patch_game();unlink = Path.unlink
        def locked(path, *args, **kwargs):
            if path == self.ini:
                raise PermissionError('fixture file locked')
            return unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', locked):
            guard.preflight(self.profile, [self.game], [], self.now)
        self.assertTrue(self.ini.exists());self.assertEqual(guard.view(self.profile)['state'], 'attention')

    def test_interrupted_quarantine_is_reconciled_and_never_restores_stale_pack(self):
        self.install();store = self.manager.store
        def crash(state):
            if state['files'][INI].get('suspended'):
                raise OSError('simulated power loss after unlink')
            store(state)
        with patch.object(self.manager, 'store', side_effect=crash):
            with self.assertRaises(OSError):
                self.manager.suspend()
        recovered = Manager(self.game, self.profile)
        self.assertFalse(recovered.restore()['conflicts']);self.assertFalse(self.ini.exists())

    def test_failure_retries_only_when_another_check_is_requested(self):
        self.install();self.patch_game()
        guard.inspect_channel(self.game, self.profile, self.now - 121, [])
        with patch('synthstrings_guard.channels', return_value=[self.game]), patch('synthstrings_guard.current_pids', return_value=[]), patch('synthstrings_guard.rebuild', return_value={'error': True}) as rebuild:
            guard.poll(self.profile);guard.poll(self.profile)
            self.assertEqual(rebuild.call_count, 2)
        self.apply()
        self.assertNotIn('retry_at', load(self.manager.folder / 'guard_status.json'))

    def test_new_patch_does_not_inherit_old_patch_retry_delay(self):
        self.install();self.manager.suspend()
        old = guard.snapshot(self.game)
        guard.record(self.manager, 'fallback', 'Waiting', 'Retry', old)
        value = load(self.manager.folder / 'guard_status.json');value['retry_at'] = self.now + 9999
        save(self.manager.folder / 'guard_status.json', value);self.patch_game()
        guard.inspect_channel(self.game, self.profile, self.now, [])
        self.assertIsNotNone(guard.inspect_channel(self.game, self.profile, self.now + 121, []))

    def test_restart_debt_survives_later_success_and_history_is_bounded(self):
        source = guard.snapshot(self.game)
        guard.record(self.manager, 'fallback', 'Defaults', 'Waiting', source, [40])
        for i in range(30):
            guard.record(self.manager, 'adapted', 'Adapted', f'Result {i}', source)
        self.assertTrue(guard.view(self.profile, [40])['restart_required'])
        self.assertEqual(len(guard.view(self.profile)['history']), 20)

    def test_config_changes_during_extraction_are_preserved(self):
        def renderer(command, **kwargs):
            self.fake_renderer(command, **kwargs)
            (self.game / CFG).write_bytes(b'clouds = 0\n')
        self.assertTrue(self.apply(renderer)['written'])
        self.assertEqual((self.game / CFG).read_bytes(), b'clouds = 0\ng_language = english\n')

    def test_disabling_during_extraction_prevents_late_reactivation(self):
        def renderer(command, **kwargs):
            self.fake_renderer(command, **kwargs);self.manager.set_enabled(False)
        self.assertFalse(self.apply(renderer)['written']);self.assertFalse(self.ini.exists())

    def test_patch_guard_can_quarantine_while_renderer_is_busy(self):
        self.install();started = threading.Event();release = threading.Event()
        def renderer(command, **kwargs):
            started.set()
            if not release.wait(5):
                raise TimeoutError('fixture renderer was not released')
            return self.fake_renderer(command, **kwargs)
        with patch('synthstrings_guard.current_pids', return_value=[60]), patch('game_text_lifecycle.subprocess.run', side_effect=renderer), ThreadPoolExecutor(1) as pool:
            future = pool.submit(lifecycle.apply_native, self.game, '-', self.profile)
            try:
                self.assertTrue(started.wait(2));self.patch_game()
                guard.inspect_channel(self.game, self.profile, self.now, [60])
                self.assertFalse(self.ini.exists())
            finally:
                release.set()
            self.assertTrue(future.result(timeout=3)['fallback'])

    def test_guard_service_never_scans_without_a_request_and_deduplicates_restarts(self):
        with patch('app_lifecycle.SingleInstance') as singleton,patch('synthstrings_guard.check_once') as check,patch('app_lifecycle.launcher_process_ids',return_value={1}),patch('synthstrings_guard.current_pids',return_value=[]):
            singleton.return_value.acquired=True
            service=guard.GuardService(self.profile)
            try:
                for _ in range(5):service.tick()
                check.assert_not_called()
                guard.request_check(self.profile,'launcher_open','session-a');service.tick()
                for future in list(service.futures.values()):future.result(timeout=2)
                service.tick();self.assertEqual(check.call_count,1)
            finally:service.close()
            again=guard.GuardService(self.profile)
            try:
                guard.request_check(self.profile,'launcher_open','session-a');again.tick()
                self.assertEqual(check.call_count,1)
                guard.request_check(self.profile,'manual');again.tick()
                for future in list(again.futures.values()):future.result(timeout=2)
                self.assertEqual(check.call_count,2)
            finally:again.close()

    def test_unchanged_managed_existing_pack_is_informational_not_a_recovery_failure(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(BASE)
        annotated=BASE.replace(b'CIG text 0 ',b'Annotated text 0 ',1)
        self.manager.write(INI,annotated)
        guard.inspect_channel(self.game,self.profile,self.now,[])
        result=guard.view(self.profile)
        self.assertEqual(result['state'],'external');self.assertFalse(result['warning'])
        self.assertEqual(result['reason'],'existing_pack');self.assertNotIn('tray',result['summary'])
        self.assertEqual(self.ini.read_bytes(),annotated)
        guard.inspect_channel(self.game,self.profile,self.now+1,[])
        self.assertEqual(len(guard.view(self.profile)['history']),1)
        self.patch_game();guard.inspect_channel(self.game,self.profile,self.now+2,[])
        self.assertEqual(guard.view(self.profile)['reason'],'pack_build_changed')
        self.assertEqual(self.ini.read_bytes(),annotated)

    def test_history_contains_explanations_and_hides_old_reasonless_alerts(self):
        guard.save(self.manager.folder/'guard_status.json',dict(schema=1,state='attention',game=str(self.game),
                   title='SynthStrings needs attention',detail='An externally owned or edited localization file was preserved. Open Setup before using it with this patch.',
                   history=[dict(title='SynthStrings needs attention',at=self.now)]))
        result=guard.view(self.profile)
        self.assertEqual(result['state'],'external');self.assertFalse(result['warning'])
        self.assertEqual(result['history'],[]);self.assertIn('Text settings',result['detail'])

    def test_explicit_switch_archives_existing_pack_and_never_restores_it_over_a_patch(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(BASE)
        self.manager.write(INI,BASE+b'foreign_extra=keep\n')
        old=self.ini.read_bytes()
        self.manager.suspend(replace_sha256=guard.digest(old))
        self.assertFalse(self.ini.exists())
        self.assertEqual(next(self.manager.folder.glob('*patch-quarantine.bin')).read_bytes(),old)
        self.apply();self.assertFalse(self.manager.restore()['conflicts'])
        self.assertFalse(self.ini.exists())

    def test_explicit_switch_cannot_remove_a_pack_changed_after_selection(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(BASE)
        expected=guard.digest(BASE);self.ini.write_bytes(BASE+b'changed=keep\n')
        with self.assertRaisesRegex(ValueError,'changed after'):
            self.manager.suspend(replace_sha256=expected)
        self.assertTrue(self.ini.exists())

    def test_failed_explicit_quarantine_does_not_change_normal_restoration(self):
        self.ini.parent.mkdir(parents=True);self.ini.write_bytes(BASE)
        edited=BASE+b'annotation=ours\n';self.manager.write(INI,edited)
        unlink=Path.unlink
        def locked(path,*args,**kwargs):
            if path==self.ini:raise PermissionError('locked fixture')
            return unlink(path,*args,**kwargs)
        with patch.object(Path,'unlink',locked),self.assertRaises(PermissionError):
            self.manager.suspend(replace_sha256=guard.digest(edited))
        self.assertFalse(self.manager.restore()['conflicts']);self.assertEqual(self.ini.read_bytes(),BASE)

    def test_deleted_generated_pack_can_be_rebuilt_without_external_edit_failure(self):
        self.install();self.ini.unlink()
        result=self.apply()
        self.assertTrue(result['written'],result);self.assertTrue(self.ini.exists())

    def test_automatic_requests_wait_for_game_exit_but_manual_request_is_allowed(self):
        with patch('app_lifecycle.SingleInstance') as singleton,patch('synthstrings_guard.check_once') as check,patch('app_lifecycle.launcher_process_ids',return_value={1}),patch('synthstrings_guard.current_pids',return_value=[50]) as pids:
            singleton.return_value.acquired=True;service=guard.GuardService(self.profile)
            try:
                guard.request_check(self.profile,'launcher_open','session-game')
                service.tick();check.assert_not_called()
                guard.request_check(self.profile,'manual');service.tick()
                for future in list(service.futures.values()):future.result(timeout=2)
                service.tick();self.assertEqual(check.call_count,1)
                pids.return_value=[];service.tick()
                for future in list(service.futures.values()):future.result(timeout=2)
                self.assertEqual(check.call_count,2)
            finally:service.close()

    def test_corrupt_journal_reports_attention_without_changing_game_text(self):
        self.install();self.manager.journal.write_text('{')
        guard.preflight(self.profile, [self.game], [], self.now)
        self.assertEqual(self.ini.read_bytes(), PACK)
        self.assertEqual(guard.view(self.profile)['state'], 'attention')

    def test_interrupted_quarantine_retains_restart_advice(self):
        self.install();store = self.manager.store
        def crash(state):
            if state['files'][INI].get('suspended'):raise OSError('simulated crash')
            store(state)
        with patch.object(self.manager, 'store', side_effect=crash):
            with self.assertRaises(OSError):self.manager.suspend([71])
        guard.inspect_channel(self.game, self.profile, self.now, [71])
        self.assertTrue(guard.view(self.profile, [71])['restart_required'])

    def test_watcher_stop_terminates_only_its_owned_renderer(self):
        from unittest.mock import Mock
        cancel = Mock();cancel.is_set.side_effect = [False, True]
        with patch('game_text_lifecycle.subprocess.Popen') as popen:
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [subprocess.TimeoutExpired('fixture', .25), 0]
            with self.assertRaisesRegex(ValueError, 'stopped'):
                lifecycle._run_text_renderer(['fixture-renderer'], {}, cancel)
            process.terminate.assert_called_once();process.kill.assert_not_called()


@unittest.skipUnless(os.environ.get('SYNTHSCAN_TEST_NATIVE_TEXT_RENDERER'), 'Opt-in headless native renderer fixture')
class NativeRendererTests(PatchFixture, unittest.TestCase):
    def test_direct_text_settings_switch_backs_up_pack_and_builds_current_text(self):
        from strings_settings import replace_pack
        self.zip64(BASE + b'TheCollector_Recipes_Title_VGLflightsuit=A synthetic contract\n')
        self.ini.parent.mkdir(parents=True);old=BASE+b'custom=old pack\n';self.ini.write_bytes(old)
        self.profile.mkdir(parents=True)
        (self.profile/'region_config.txt').write_text('gametexts=0\nother_setting=keep\n')
        with patch('strings_settings.current_pids',return_value=[]),patch('synthstrings_guard.current_pids',return_value=[]):
            result=replace_pack(self.game,self.profile,Path(os.environ['SYNTHSCAN_TEST_NATIVE_TEXT_RENDERER']),guard.digest(old))
        self.assertTrue(result['written'],result)
        self.assertEqual(next(self.manager.folder.glob('*patch-quarantine.bin')).read_bytes(),old)
        self.assertEqual((self.profile/'region_config.txt').read_text(),'other_setting=keep\ngametexts=1\n')
        self.assertIn(b'A synthetic contract <EM4>[BP]</EM4>',self.ini.read_bytes())

    def zip64(self, text):
        name = b'Data\\Localization\\english\\global.ini';crc = zlib.crc32(text)
        local = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0, 0, 0, 0, crc, len(text), len(text), len(name), 0) + name + text
        central = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 45, 20, 0, 0, 0, 0, crc, len(text), len(text), len(name), 0, 0, 0, 0, 0, 0) + name
        end = struct.pack('<IQHHIIQQQQ', 0x06064b50, 44, 45, 45, 0, 0, 1, 1, len(central), len(local))
        locator = struct.pack('<IIQI', 0x07064b50, 0, len(local) + len(central), 1)
        footer = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, 65535, 65535, 0xffffffff, 0xffffffff, 0)
        self.archive.write_bytes(local + central + end + locator + footer)
        os.utime(self.archive, (self.now - 500, self.now - 500))

    def test_native_render_preserves_actual_fresh_archive_baseline_and_ignores_poisoned_cache(self):
        base = BASE + b'TheCollector_Recipes_Title_VGLflightsuit=A synthetic contract\n'
        self.zip64(base)
        with patch('synthstrings_guard.current_pids', return_value=[]):
            result = lifecycle.apply_native(self.game, '-', self.profile, Path(os.environ['SYNTHSCAN_TEST_NATIVE_TEXT_RENDERER']))
            self.assertTrue(result.get('written'), result)
            self.assertIn(b'A synthetic contract <EM4>[BP]</EM4>', self.ini.read_bytes())
            cache = self.profile / 'game_text_LIVE.ini';self.assertTrue(cache.exists());cache.write_bytes(b'poisoned cache')
            again = lifecycle.apply_native(self.game, '-', self.profile, Path(os.environ['SYNTHSCAN_TEST_NATIVE_TEXT_RENDERER']))
            self.assertTrue(again.get('written'), again)
            self.assertEqual(self.manager.read()['files'][INI]['source']['source_sha256'], guard.digest(base))

    def test_native_ptu_render_does_not_reuse_live_ownership(self):
        source = (Path(__file__).resolve().parents[1] / 'native/synthscan/include/CraftingData.h').read_text(encoding='utf-8')
        source = source[source.index('inline const CraftBlueprint CRAFT_BLUEPRINTS[] = {'):]
        names = re.findall(r'^\s*\{"((?:[^"\\]|\\.)*)",', source[:source.index('\n};')], re.M)
        self.profile.mkdir(parents=True)
        (self.profile / 'owned_blueprints.txt').write_text(''.join('owned\tfixture\t' + re.sub(r'\\(.)', r'\1', name) + '\thand\n' for name in names), encoding='utf-8')
        self.zip64(BASE + b'TheCollector_Recipes_Title_VGLflightsuit=A synthetic contract\n')
        ptu = self.root / 'PTU';(ptu / 'Bin64').mkdir(parents=True)
        for name in ('Data.p4k', 'build_manifest.id', 'Bin64/StarCitizen.exe'):
            shutil.copy2(self.game / name, ptu / name)
        native = Path(os.environ['SYNTHSCAN_TEST_NATIVE_TEXT_RENDERER'])
        with patch('synthstrings_guard.current_pids', return_value=[]):
            live_result = lifecycle.apply_native(self.game, '-', self.profile, native)
            ptu_result = lifecycle.apply_native(ptu, '-', self.profile, native)
        self.assertTrue(live_result.get('written'), live_result);self.assertTrue(ptu_result.get('written'), ptu_result)
        self.assertIn(b'A synthetic contract [BP]', self.ini.read_bytes())
        self.assertIn(b'A synthetic contract <EM4>[BP]</EM4>', (ptu / INI).read_bytes())


class RenderValidationTests(unittest.TestCase):
    def test_original_physical_continuations_and_blank_rows_are_preserved(self):
        base = BASE + b'opaque continuation row\\nMore text\n\n'
        self.assertEqual(guard.validate_render(base, base + b'bedrock_game_texts=1')['keys'], 1001)
        with self.assertRaisesRegex(ValueError, 'row'):
            guard.validate_render(base, base.replace(b'opaque continuation', b'changed') + b'bedrock_game_texts=1')

    def test_complete_baseline_with_appended_annotations_is_accepted(self):
        candidate = PACK.replace(b'key_9=CIG text 9 ~mission(Value)\\nNext', b'key_9=CIG text 9 ~mission(Value)\\nNext <EM4>[BP]</EM4>')
        result = guard.validate_render(BASE, candidate)
        self.assertEqual(result['keys'], 1001);self.assertEqual(result['annotated'], 1)

    def test_bad_candidates_are_rejected(self):
        bad = [PACK.replace(b'key_9=', b'key_gone='), PACK.replace(b'~mission(Value)', b'bad', 1),
               PACK + b'key_9=duplicate\n', PACK + b'key_9,P=duplicate alias\n', PACK[:100],
               PACK.replace(b'CIG text 1', b'\xff', 1), PACK + b'bad=\0\n', BASE]
        for candidate in bad:
            with self.subTest(candidate=candidate[:50]), self.assertRaises(ValueError):
                guard.validate_render(BASE, candidate)


if __name__ == '__main__':
    unittest.main()
