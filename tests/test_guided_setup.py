import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from setup_status import reputation_view,error_message
from reputation_notice import NoticeGate

class GuidedSetupTests(unittest.TestCase):
    def test_game_watcher_waits_for_first_run_instead_of_reopening_the_wizard(self):
        from native_control import setup_busy,RecoveryPolicy
        with patch('native_control.instance_running',return_value=True),patch('setup_status.ready',return_value=False):
            self.assertTrue(setup_busy())
            policy=RecoveryPolicy();self.assertFalse(policy.update({1},setup_busy(),False,now=100))
        with patch('native_control.instance_running',return_value=True),patch('setup_status.ready',return_value=True):
            self.assertFalse(setup_busy())

    def test_installer_startup_choice_starts_watcher_without_waiting_for_a_reboot(self):
        from community_startup import ensure_watcher
        with patch('community_startup.owns_shortcut',return_value=True),patch('app_lifecycle.instance_running',return_value=False),patch('community_startup.subprocess.Popen') as spawn:
            ensure_watcher();self.assertIn('--watch',spawn.call_args.args[0])
        with patch('community_startup.owns_shortcut',return_value=False),patch('community_startup.subprocess.Popen') as spawn:
            ensure_watcher();spawn.assert_not_called()

    def test_uninstall_restores_only_owned_names_and_keeps_player_records(self):
        import community_uninstall as uninstall
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);profile=root/'profile';profile.mkdir()
            ini=root/'game/Data/Localization/english/global.ini';ini.parent.mkdir(parents=True)
            ini.write_text('Adagio=Adagio (249 / 800)\nMission=Keep my marks\n')
            (profile/'diary.json').write_text('personal record fixture')
            (profile/'reputation_localization_state.json').write_text(json.dumps(dict(entries={'adagio':dict(original='Adagio',written='Adagio (249 / 800)')})))
            with patch.object(uninstall,'PROFILE',profile),patch.object(uninstall,'game_directory',return_value=root/'game'),patch.object(uninstall,'send_signal'),patch('community_startup.owns_shortcut',return_value=False):
                uninstall.cleanup()
            self.assertEqual(ini.read_text(),'Adagio=Adagio\nMission=Keep my marks\n')
            self.assertEqual((profile/'diary.json').read_text(),'personal record fixture')

    def test_new_player_gets_login_guidance_without_a_profile(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(reputation_view(Path(d),100)['state'],'waiting')

    def test_restart_prompt_follows_the_actual_game_process(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def session(pids):
                (root/'session_state.json').write_text(json.dumps(dict(game_pids=pids,written_at=100)))
            (root/'reputation_labels_status.json').write_text(json.dumps(dict(ok=True,at=100,names=14,written_game_pids=[123],labels_written_at=95)))
            session([123]);self.assertEqual(reputation_view(root,101)['state'],'restart')
            session([124]);self.assertEqual(reputation_view(root,101)['state'],'ready')
            self.assertEqual(reputation_view(root,300)['state'],'waiting')

    def test_zero_unknown_balances_do_not_claim_success(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'session_state.json').write_text(json.dumps(dict(game_pids=[1],written_at=100)))
            (root/'reputation_labels_status.json').write_text(json.dumps(dict(ok=True,at=100,names=0)))
            self.assertEqual(reputation_view(root,101)['state'],'checking')

    def test_notice_does_not_repeat_for_each_rep_update(self):
        gate=NoticeGate()
        self.assertTrue(gate.consume(dict(state='restart'),[1]))
        self.assertFalse(gate.consume(dict(state='restart',written_at=200),[1]))
        self.assertFalse(gate.consume(dict(state='ready'),[2]))
        self.assertTrue(gate.consume(dict(state='restart'),[2]))

    def test_permission_error_has_an_in_app_recovery_action(self):
        self.assertIn('Allow game-text access',error_message(PermissionError()))

    def test_native_text_rewrite_is_automatically_reannotated_without_another_rpc(self):
        from questing import Questing
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ini=root/'Data/Localization/english/global.ini';ini.parent.mkdir(parents=True);ini.write_text('base')
            (root/'reputation_snapshot.json').write_text('{}')
            q=Questing(root,root/'Game.log')
            def sync(_):
                ini.write_text('annotated')
                return dict(changed=True,names=1,requires_game_text_reload=True)
            try:
                with patch('installation.RELEASE',True),patch('installation.reference_paths',return_value={'game':root}),patch('tools.sync_reputation_names.sync',side_effect=sync) as write,patch('app_lifecycle.game_process_ids',return_value={1}):
                    q.sync_names(100);q.sync_names(104);self.assertEqual(write.call_count,1)
                    ini.write_text('native blueprint update')
                    stamp=ini.stat().st_mtime_ns;os.utime(ini,ns=(stamp+1000000,stamp+1000000))
                    q.sync_names(108);self.assertEqual(write.call_count,2)
                    self.assertEqual(ini.read_text(),'annotated')
                    self.assertFalse(q.future)
            finally:q.close()
