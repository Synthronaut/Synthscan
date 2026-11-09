import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from companion_features import CompanionRunner
from player_session import SessionVerifier
from telemetry_core import IncrementalGameLog,utc_iso


SHARD='pub_use1b_100_020'


def join(at=100,shard=SHARD):
    return f'<{utc_iso(at)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[{shard}]\n'


class PlayerSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.log=self.directory/'Game.log';self.log.write_text(join())
        self.pids=[7];self.factory=Mock(wraps=IncrementalGameLog)
        self.verifier=SessionVerifier(lambda:self.pids,lambda:self.log,self.factory)
        self.context=dict(owner_pid=42,written_at=900,session_token='bridge-join',full_shard_id=SHARD,joined_at=100,game_pids=[7])

    def append(self,line):
        with self.log.open('a') as f:f.write(line)

    def test_reuses_reader_but_immediately_observes_disconnect(self):
        self.assertTrue(self.verifier.matches(self.context));self.assertTrue(self.verifier.matches(self.context))
        self.assertEqual(self.factory.call_count,1)
        self.append(f'<{utc_iso(101)}> Connection closed\n')
        self.assertFalse(self.verifier.matches(self.context))

    def test_loading_and_new_join_invalidate_previous_scope(self):
        self.assertTrue(self.verifier.matches(self.context))
        self.append(f'<{utc_iso(101)}> OpenLoadingScreen\n')
        self.assertFalse(self.verifier.matches(self.context))
        self.append(f'<{utc_iso(102)}> StopLoadingScreen Finished\n')
        self.assertTrue(self.verifier.matches(self.context))
        self.append(join(103,'pub_use1b_100_021'))
        self.assertFalse(self.verifier.matches(self.context))
        self.assertTrue(self.verifier.matches(dict(self.context,joined_at=103,full_shard_id='pub_use1b_100_021',session_token='new-bridge-join')))
        self.assertEqual(self.factory.call_count,1)

    def test_process_exit_or_changed_processes_rejects_old_snapshot(self):
        self.assertTrue(self.verifier.matches(self.context));self.pids=[8]
        self.assertFalse(self.verifier.matches(self.context));self.pids=[]
        self.assertFalse(self.verifier.matches(self.context))

    def test_log_replacement_rejects_old_identity_without_replaying_cached_state(self):
        self.assertTrue(self.verifier.matches(self.context))
        self.log.write_text(join(200,'pub_euw1b_100_040'))
        self.assertFalse(self.verifier.matches(self.context))

    def runner(self):
        service=Mock()
        with patch('companion_features.CompanionService',return_value=service):runner=CompanionRunner(self.directory,42)
        (self.directory/'home_status.json').write_text(json.dumps(dict(owner_pid=42,visible=True,active_page='people')))
        return runner,service

    def write_snapshot(self,**changes):
        (self.directory/'session_ribbon.json').write_text(json.dumps(dict(self.context,**changes)))

    def tick(self,runner,now):
        with patch('player_session._verifier',self.verifier),patch('companion_features.time.time',return_value=now):runner.tick()

    def test_slow_bridge_does_not_repeatedly_clear_confirmed_people_session(self):
        runner,service=self.runner();self.write_snapshot()
        for now in (1000,1006,1015,1030):
            self.tick(runner,now)
            context,visible,at=service.tick.call_args.args
            self.assertEqual(context['session_token'],'bridge-join');self.assertTrue(visible)
        self.assertEqual(self.factory.call_count,1)

    def test_stale_bridge_cannot_keep_old_session_during_loading_or_after_disconnect(self):
        runner,service=self.runner();self.write_snapshot();self.tick(runner,1000)
        self.append(f'<{utc_iso(101)}> OpenLoadingScreen\n');self.tick(runner,1002)
        self.assertEqual(service.tick.call_args.args[0],{})
        self.append(f'<{utc_iso(102)}> Connection closed\n');self.tick(runner,1004)
        self.assertEqual(service.tick.call_args.args[0],{})

    def test_temporary_missing_snapshot_uses_only_still_verified_context(self):
        runner,service=self.runner();self.write_snapshot();self.tick(runner,1000)
        (self.directory/'session_ribbon.json').unlink();self.tick(runner,1002)
        self.assertEqual(service.tick.call_args.args[0]['session_token'],'bridge-join')
        self.append(f'<{utc_iso(101)}> Connection closed\n');self.tick(runner,1004)
        self.assertEqual(service.tick.call_args.args[0],{})

    def test_wrong_owner_future_snapshot_and_explicit_leave_are_never_retained(self):
        for changes in (dict(owner_pid=43),dict(written_at=2000),dict(session_token=None)):
            runner,service=self.runner();self.write_snapshot();self.tick(runner,1000)
            self.write_snapshot(**changes);self.tick(runner,1002)
            self.assertEqual(service.tick.call_args.args[0],{})
