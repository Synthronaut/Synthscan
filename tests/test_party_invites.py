from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
from threading import Event,Thread
import unittest
from unittest.mock import Mock,patch,call

from companion_features import CompanionService
from party_invites import InviteHistory,PartyInviteQueue,INVITE_INTERVAL_MIN,INVITE_INTERVAL_MAX,MAX_BATCH_REQUESTS
from player_services import PlayerClient,PLAYER_PREFIX,PlayerLeftShard

PEOPLE=[dict(id=PLAYER_PREFIX+str(i),handle='Pilot'+str(i)) for i in (2,3,4)]
CONTEXT=dict(session_token='join',full_shard_id='fixture',joined_at=100)


class QueueTests(unittest.TestCase):
    def test_fifty_recipient_boundary_applies_to_friend_and_party_queues(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i}') for i in range(51)]
        self.assertEqual(MAX_BATCH_REQUESTS,50)
        for operation in ('friend','party'):
            self.assertEqual(PartyInviteQueue(people[:50],operation=operation).snapshot()['total'],50)
            with self.assertRaisesRegex(ValueError,'Nothing was sent'):PartyInviteQueue(people,operation=operation)
    def test_random_gap_is_sampled_per_completion_and_measured_after_it(self):
        clock=[10.];sample=Mock(side_effect=[.09,.99])
        q=PartyInviteQueue(PEOPLE,clock=lambda:clock[0],sample_interval=sample)
        self.assertEqual((INVITE_INTERVAL_MIN,INVITE_INTERVAL_MAX),(.09,.99))
        self.assertTrue(q.before_send(PEOPLE[0]));clock[0]=13.
        q.update(dict(PEOPLE[0],outcome='Sent',detail='Receipt'))
        self.assertAlmostEqual(q.due,13.09)
        def advance(seconds):clock[0]+=seconds
        with patch.object(q.condition,'wait',side_effect=advance):self.assertTrue(q.before_send(PEOPLE[1]))
        self.assertGreaterEqual(clock[0],13.09)
        self.assertEqual(q.snapshot()['sent'],1);self.assertEqual(q.snapshot()['current_handle'],'Pilot3')
        self.assertEqual(sample.call_count,1)
        q.update(dict(PEOPLE[1],outcome='Sent',detail='Receipt'))
        self.assertAlmostEqual(q.due,clock[0]+.99)
        self.assertEqual(sample.call_args_list,[call(.09,.99),call(.09,.99)])
    def test_default_random_gaps_stay_in_requested_range_for_both_operations(self):
        for operation in ('friend','party'):
            q=PartyInviteQueue(PEOPLE,operation=operation)
            for _ in range(100):
                q.inflight=True;q.update(dict(PEOPLE[0],outcome='Sent',detail='Receipt'))
                self.assertGreaterEqual(q.last_interval,.09);self.assertLessEqual(q.last_interval,.99)
    def waiter(self,q,person):
        entered=Event();finished=Event();answer=[];original=q.condition.wait
        def wait(timeout=None):entered.set();return original(timeout)
        q.condition.wait=wait
        def work():answer.append(q.before_send(person));finished.set()
        thread=Thread(target=work,daemon=True);thread.start()
        self.assertTrue(entered.wait(1))
        return thread,finished,answer
    def test_pause_blocks_send_until_explicit_resume(self):
        q=PartyInviteQueue(PEOPLE);q.pause(True)
        thread,finished,answer=self.waiter(q,PEOPLE[0])
        try:
            self.assertFalse(finished.is_set());self.assertEqual(q.snapshot()['state'],'Paused')
            q.pause(False);self.assertTrue(finished.wait(1));self.assertEqual(answer,[True])
        finally:q.cancel();thread.join(1)
    def test_cancel_wakes_paused_queue_without_sending(self):
        q=PartyInviteQueue(PEOPLE);q.pause(True)
        thread,finished,answer=self.waiter(q,PEOPLE[0])
        q.cancel();self.assertTrue(finished.wait(1));thread.join(1);self.assertEqual(answer,[False])
        q.finish();self.assertEqual(q.snapshot()['state'],'Cancelled')
        self.assertTrue(all(row['outcome']=='Not sent' for row in q.snapshot()['results']))
    def test_cancel_wakes_cooldown_and_retains_successful_receipts(self):
        q=PartyInviteQueue(PEOPLE);q.before_send(PEOPLE[0]);q.update(dict(PEOPLE[0],outcome='Sent',detail='Receipt'))
        thread,finished,answer=self.waiter(q,PEOPLE[1]);q.cancel()
        self.assertTrue(finished.wait(1));thread.join(1);self.assertEqual(answer,[False])
        q.finish();s=q.snapshot();self.assertEqual(s['sent'],1);self.assertEqual(s['results'][0]['detail'],'Receipt')
    def test_skipped_recipient_does_not_restart_cooldown(self):
        clock=[1.];sample=Mock(return_value=.99);q=PartyInviteQueue(PEOPLE,clock=lambda:clock[0],sample_interval=sample)
        q.before_send(PEOPLE[0]);q.update(dict(PEOPLE[0],outcome='Sent',detail='Receipt'))
        clock[0]=1.5;q.update(dict(PEOPLE[1],outcome='Skipped',detail='Already in party'))
        self.assertAlmostEqual(q.due,1.99);self.assertEqual(q.snapshot()['next_in_seconds'],1)
        sample.assert_called_once_with(.09,.99)


class HistoryTests(unittest.TestCase):
    def test_history_survives_restart_and_is_scoped_to_game_session(self):
        with tempfile.TemporaryDirectory() as directory:
            history=InviteHistory(directory);history.record('join',PEOPLE[0])
            restored=InviteHistory(directory)
            self.assertEqual(restored.ids('join'),{PEOPLE[0]['id']});self.assertEqual(restored.ids('other'),set())
            restored.record('other',PEOPLE[1]);self.assertEqual(restored.ids('join'),set())
    def test_corrupt_history_is_preserved_and_sending_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'party_invite_attempts.json';path.write_text('broken')
            history=InviteHistory(directory)
            with self.assertRaises(ValueError):history.record('join',PEOPLE[0])
            self.assertEqual(path.read_text(),'broken')
    def test_failed_history_write_keeps_previous_record(self):
        with tempfile.TemporaryDirectory() as directory:
            history=InviteHistory(directory);history.record('join',PEOPLE[0])
            with patch('party_invites.publish_json',return_value=False):
                with self.assertRaises(ValueError):history.record('join',PEOPLE[1])
            self.assertEqual(history.ids('join'),{PEOPLE[0]['id']})


class ManualPool:
    def __init__(self):self.calls=[]
    def submit(self,*args,**kwargs):self.calls.append((args,kwargs));return Future()
    def shutdown(self,**kwargs):pass


class QueueServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.pool=ManualPool();self.service=CompanionService(self.temp.name,42,social=Mock(),pool=self.pool)
        self.service.tick(CONTEXT,False,1000);self.service.roster=PEOPLE
    def tearDown(self):self.service.close();self.temp.cleanup()
    def command(self,action,**extra):return dict(id=action,action=action,owner_pid=42,session_token='join',at=1001,**extra)
    def start(self,**extra):self.service.command(self.command('party_many',player_ids=[p['id'] for p in PEOPLE],confirmed=True,**extra),1001)
    def test_oversized_batch_is_rejected_before_persisting_or_submitting(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i}') for i in range(51)]
        self.service.roster=people
        for operation in ('friend_many','party_many'):
            with self.assertRaisesRegex(ValueError,'Nothing was sent'):
                self.service.command(self.command(operation,player_ids=[p['id'] for p in people],confirmed=True),1001)
            self.assertFalse(self.pool.calls);self.assertIsNone(self.service.invite_queue)
            self.assertNotIn(operation,self.service.store.data['commands'])
        self.service.command(self.command('tag_many',player_ids=[p['id'] for p in people],label='Org'),1001)
        self.assertEqual(len(self.service.store.data['tags']),51)
        self.service.command(self.command('party_many',player_ids=[p['id'] for p in people[:50]],confirmed=True),1001)
        self.assertEqual(self.service.invite_queue.snapshot()['total'],50)
    def test_queue_controls_require_matching_queue_and_session(self):
        self.start();q=self.service.invite_queue
        bad=self.command('pause_invites',queue_id='old')
        with self.assertRaises(ValueError):self.service.command(bad,1001)
        self.service.command(self.command('pause_invites',queue_id=q.identifier),1001);self.assertTrue(q.paused)
        bad=self.command('resume_invites',queue_id=q.identifier);bad['session_token']='old'
        with self.assertRaises(ValueError):self.service.command(bad,1001)
        self.assertTrue(q.paused)
        self.service.command(self.command('resume_invites',queue_id=q.identifier),1001);self.assertFalse(q.paused)
        self.service.command(self.command('cancel_invites',queue_id=q.identifier),1001);self.assertTrue(q.cancel_event.is_set())
    def test_progress_is_published_while_job_is_running(self):
        self.start();q=self.service.invite_queue;q.before_send(PEOPLE[0]);q.update(dict(PEOPLE[0],outcome='Sent',detail='Receipt'))
        self.service.publish(1002);state=json.loads((Path(self.temp.name)/'companion_state.json').read_text())
        self.assertTrue(state['invite_queue']['active']);self.assertEqual(state['invite_queue']['sent'],1)
        self.assertEqual(state['invite_queue']['remaining'],2);self.assertEqual(state['batch_results'][0]['outcome'],'Sent')
    def test_previous_attempts_are_skipped_unless_explicit_resend(self):
        self.service.invite_history.record('join',PEOPLE[0]);self.start()
        self.assertIn(PEOPLE[0]['id'],self.service.invited)
        self.assertIn(PEOPLE[0]['id'],self.pool.calls[-1][1]['previous'])
        self.service.jobs.clear();command=self.command('party_many',player_ids=[p['id'] for p in PEOPLE],confirmed=True,resend=True);command['id']='explicit-resend'
        self.service.command(command,1001)
        self.assertEqual(self.pool.calls[-1][1]['previous'],[])
        self.assertEqual(self.service.invite_history.ids('join'),{PEOPLE[0]['id']})
    def test_old_single_party_command_also_uses_queue_and_history(self):
        self.service.command(self.command('party',player_id=PEOPLE[0]['id'],confirmed=True),1001)
        self.assertIsNotNone(self.service.invite_queue);self.assertEqual(self.service.invite_queue.snapshot()['total'],1)
    def test_history_file_is_excluded_from_public_packages(self):
        from tools.package_community import is_private
        self.assertTrue(is_private('party_invite_attempts.json'));self.assertTrue(is_private('party_invite_attempts.json.tmp'))
        self.assertTrue(is_private('friend_request_attempts.json'))


class ActionListTests(unittest.TestCase):
    setUp=QueueServiceTests.setUp
    tearDown=QueueServiceTests.tearDown
    command=QueueServiceTests.command
    def stage(self,ids,identifier='stage'):
        command=self.command('stage_people',player_ids=ids);command['id']=identifier;self.service.command(command,1001)
    def test_action_list_stops_at_fifty_and_removal_makes_room(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i:02}') for i in range(51)]
        self.service.roster=people
        self.stage([p['id'] for p in people])
        self.assertEqual(len(self.service.store.data['actions']),50)
        self.assertIn('1 not added',self.service.action_status)
        self.assertFalse(self.pool.calls)
        self.stage([people[0]['id'],people[50]['id']],'full-list')
        self.assertEqual(len(self.service.store.data['actions']),50)
        self.service.command(self.command('unstage_people',player_ids=[people[0]['id']]),1001)
        self.stage([people[50]['id']],'fill-space')
        self.assertEqual(len(self.service.store.data['actions']),50)
        self.assertIn(people[50]['id'],{p['id'] for p in self.service.store.data['actions']})
        self.service.publish(1002)
        self.assertEqual(json.loads((Path(self.temp.name)/'companion_state.json').read_text())['action_limit'],50)
    def test_add_by_tag_and_add_friends_share_action_list_capacity(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i:02}') for i in range(60)]
        self.service.roster=people
        for p in people:self.service.store.data['tags'][p['id']]=dict(handle=p['handle'],label='Org',alert=False)
        self.service.command(self.command('stage_tag',label='Org'),1001)
        self.assertEqual(len(self.service.store.data['actions']),50);self.assertIn('10 not added',self.service.action_status)
        self.service.relationships=dict(friends=[p['id'] for p in people],friends_at=1001,friend_rows=people)
        self.service.command(dict(self.command('stage_tag',label='Friend'),id='stage-friends'),1001)
        self.assertEqual(len(self.service.store.data['actions']),50);self.assertFalse(self.pool.calls)
    def test_saved_oversized_action_list_is_reduced_on_restart(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i:02}') for i in range(51)]
        self.service.store.data.update(actions=people,actions_session='join');self.service.store.save();self.service.close()
        self.service=CompanionService(self.temp.name,42,social=Mock(),pool=self.pool)
        self.assertEqual(self.service.store.data['actions'],people[:50]);self.assertIn('first 50 saved players',self.service.action_status)
    def test_staging_is_incremental_deduplicated_and_survives_roster_filtering(self):
        self.stage([PEOPLE[0]['id']]);self.stage([PEOPLE[0]['id'],PEOPLE[1]['id']],'stage-again')
        self.assertEqual([p['id'] for p in self.service.store.data['actions']],[PEOPLE[0]['id'],PEOPLE[1]['id']])
        self.service.search=[];self.service.publish(1001)
        state=json.loads((Path(self.temp.name)/'companion_state.json').read_text())
        self.assertEqual(len(state['action_people']),2)
    def test_add_org_matches_org_and_affiliate_only_on_current_shard(self):
        tags=self.service.store.data['tags']
        for person,label in zip(PEOPLE,['Org','Org Affiliate','Org enemy']):tags[person['id']]=dict(handle=person['handle'],label=label,alert=False)
        tags[PLAYER_PREFIX+'99']=dict(handle='OffShard',label='Org',alert=False)
        self.service.command(self.command('stage_tag',label='Org',include_org_affiliate=True,scope='shard'),1001)
        self.assertEqual([p['id'] for p in self.service.store.data['actions']],[p['id'] for p in PEOPLE[:2]])
        self.assertEqual(self.pool.calls,[])
    def test_add_custom_tag_matches_whole_tag_case_insensitively(self):
        for person,label in zip(PEOPLE,['Friendly, Trading Partners','Trading Partners Plus','trading partners']):self.service.store.data['tags'][person['id']]=dict(handle=person['handle'],label=label,alert=False)
        self.service.command(self.command('stage_tag',label='Trading Partners'),1001)
        self.assertEqual([p['id'] for p in self.service.store.data['actions']],[PEOPLE[0]['id'],PEOPLE[2]['id']])
    def test_remove_exclusions_then_bulk_action_targets_only_remaining_people(self):
        self.stage([p['id'] for p in PEOPLE])
        self.service.command(self.command('unstage_people',player_ids=[PEOPLE[1]['id']]),1001)
        ids=[PEOPLE[0]['id'],PEOPLE[2]['id']]
        self.service.command(self.command('party_many',player_ids=ids,from_actions=True,confirmed=True),1001)
        self.assertEqual([p['id'] for p in self.pool.calls[-1][1]['people']],ids)
        self.assertEqual(self.service.invite_queue.snapshot()['interval_min_seconds'],.09)
        self.assertEqual(self.service.invite_queue.snapshot()['interval_max_seconds'],.99)
    def test_off_shard_search_result_cannot_be_staged_or_used_for_any_action(self):
        other=dict(id=PLAYER_PREFIX+'99',handle='OffShard');self.service.search=[other]
        with self.assertRaises(ValueError):self.stage([other['id']])
        for action in ('friend_many','party_many','tag_many','mark_org'):
            with self.assertRaises(ValueError):self.service.command(self.command(action,player_ids=[other['id']],confirmed=True,label='Org'),1001)
        with self.assertRaises(ValueError):self.service.command(self.command('stage_tag',label='Org',scope='saved'),1001)
        self.assertEqual(self.pool.calls,[])
    def test_membership_refresh_removes_departed_players_from_action_list(self):
        self.stage([p['id'] for p in PEOPLE])
        job=Future();job.set_result(dict(rows=[PEOPLE[0],PEOPLE[2]],observed_at=1002));self.service.jobs['roster']=(job,CONTEXT)
        self.service.tick(CONTEXT,False,1002)
        self.assertEqual([p['id'] for p in self.service.store.data['actions']],[PEOPLE[0]['id'],PEOPLE[2]['id']])
    def test_action_list_survives_app_restart_within_same_join_but_resets_on_new_join(self):
        self.stage([PEOPLE[0]['id']]);self.service.close()
        self.service=CompanionService(self.temp.name,42,social=Mock(),pool=self.pool);self.service.tick(CONTEXT,False,1002)
        self.assertEqual(len(self.service.store.data['actions']),1)
        self.service.tick(dict(CONTEXT,session_token='new-join'),False,1003);self.assertEqual(self.service.store.data['actions'],[])
    def test_confirmation_cannot_send_people_removed_from_action_list(self):
        self.stage([PEOPLE[0]['id']])
        with self.assertRaises(ValueError):self.service.command(self.command('party_many',player_ids=[p['id'] for p in PEOPLE],confirmed=True,from_actions=True),1001)
        self.assertEqual(self.pool.calls,[])
    def test_friend_and_party_attempt_histories_are_independent(self):
        self.stage([p['id'] for p in PEOPLE]);self.service.friend_history.record('join',PEOPLE[0]);self.service.invite_history.record('join',PEOPLE[1])
        self.service.command(self.command('friend_many',player_ids=[p['id'] for p in PEOPLE],confirmed=True,from_actions=True),1001)
        self.assertEqual(self.pool.calls[-1][0][1],'friend_many');self.assertEqual(self.pool.calls[-1][1]['previous'],[PEOPLE[0]['id']]);self.assertTrue(self.pool.calls[-1][1]['require_shard'])
        self.service.invite_queue.cancel();self.service.jobs.clear()
        self.service.command(self.command('party_many',player_ids=[p['id'] for p in PEOPLE],confirmed=True,from_actions=True),1001)
        self.assertEqual(self.pool.calls[-1][1]['previous'],[PEOPLE[1]['id']])
    def test_clear_only_changes_local_action_list_and_does_not_send_requests(self):
        self.stage([p['id'] for p in PEOPLE]);self.service.command(self.command('clear_actions'),1001)
        self.assertEqual(self.service.store.data['actions'],[]);self.assertEqual(self.pool.calls,[])


class WorkerTests(unittest.TestCase):
    def test_direct_worker_cannot_bypass_fifty_recipient_limit(self):
        people=[dict(id=PLAYER_PREFIX+str(i+2),handle=f'Pilot{i}') for i in range(51)]
        for operation in ('friend','party'):
            c=self.client()
            with self.assertRaisesRegex(ValueError,'Nothing was sent'):c.invite_many(people,CONTEXT,True,operation=operation)
            c.server_member_ids.assert_not_called();c.relationships.assert_not_called();c.send.assert_not_called()
    def client(self):
        c=object.__new__(PlayerClient);c.account=Mock(subject=PLAYER_PREFIX+'1')
        c.roster=Mock(return_value=dict(rows=PEOPLE));c.relationships=Mock(return_value=dict(party_at=1000,party=[]));c.send=Mock(return_value='Receipt')
        c.server_member_ids=Mock(return_value={p['id'] for p in PEOPLE})
        return c
    def test_history_is_saved_before_request_and_timeout_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            history=InviteHistory(directory);q=PartyInviteQueue(PEOPLE,history=history,session='join',interval=0);c=self.client()
            def send(*args):
                self.assertIn(PEOPLE[0]['id'],InviteHistory(directory).ids('join'))
                raise TimeoutError()
            c.send.side_effect=send;result=c.invite_many(PEOPLE,CONTEXT,True,control=q)
            self.assertEqual(c.send.call_count,1);self.assertEqual([p['outcome'] for p in result['results']],['Check in game','Not sent','Not sent'])
            self.assertEqual(q.snapshot()['state'],'Stopped')
    def test_history_failure_prevents_network_send_and_stops_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            q=PartyInviteQueue(PEOPLE,history=InviteHistory(directory),session='join',interval=0);c=self.client()
            with patch('party_invites.publish_json',return_value=False):c.invite_many(PEOPLE,CONTEXT,True,control=q)
            c.send.assert_not_called();self.assertEqual(q.snapshot()['state'],'Stopped')
    def test_service_limit_stops_after_first_attempt_without_retry(self):
        c=self.client();c.send.side_effect=ValueError('The game service is busy or a social limit was reached.')
        q=PartyInviteQueue(PEOPLE,interval=0);c.invite_many(PEOPLE,CONTEXT,True,control=q)
        self.assertEqual(c.send.call_count,1);self.assertFalse(q.snapshot()['active'])
    def test_off_shard_override_is_not_permitted(self):
        c=self.client();q=PartyInviteQueue(PEOPLE[:1],interval=0)
        with self.assertRaises(ValueError):c.invite_many(PEOPLE[:1],CONTEXT,True,control=q,require_shard=False)
        c.send.assert_not_called()
    def test_pause_during_request_blocks_the_next_recipient(self):
        c=self.client();q=PartyInviteQueue(PEOPLE,interval=0);entered=Event();release=Event();paused=Event();original=q.condition.wait
        def wait(timeout=None):paused.set();return original(timeout)
        q.condition.wait=wait
        def send(*args):
            if c.send.call_count==1:entered.set();release.wait(2)
            return 'Receipt'
        c.send.side_effect=send
        thread=Thread(target=lambda:c.invite_many(PEOPLE,CONTEXT,True,control=q),daemon=True);thread.start()
        try:
            self.assertTrue(entered.wait(1));q.pause(True);self.assertEqual(q.snapshot()['state'],'Pausing');release.set()
            self.assertTrue(paused.wait(1));self.assertEqual(c.send.call_count,1)
            q.pause(False);thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(c.send.call_count,3)
            self.assertEqual(c.relationships.call_count,2)
        finally:q.cancel();release.set();thread.join(2)
    def test_resume_refresh_skips_someone_who_has_joined_party(self):
        c=self.client();q=PartyInviteQueue(PEOPLE,interval=0);entered=Event();release=Event();paused=Event();original=q.condition.wait
        def wait(timeout=None):paused.set();return original(timeout)
        q.condition.wait=wait
        def send(*args):
            if c.send.call_count==1:entered.set();release.wait(2)
            return 'Receipt'
        c.send.side_effect=send;results=[]
        thread=Thread(target=lambda:results.append(c.invite_many(PEOPLE,CONTEXT,True,control=q)),daemon=True);thread.start()
        try:
            self.assertTrue(entered.wait(1));q.pause(True);release.set();self.assertTrue(paused.wait(1))
            c.relationships.return_value=dict(party_at=1001,party=[PEOPLE[1]['id']]);q.pause(False);thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual(c.send.call_count,2)
            self.assertEqual(results[0]['results'][1]['outcome'],'Skipped')
        finally:q.cancel();release.set();thread.join(2)
    def test_recipient_rejection_continues_but_connection_failure_stops(self):
        class RpcFailure(Exception):
            def __init__(self,name):self.name=name
            def code(self):
                from types import SimpleNamespace
                return SimpleNamespace(name=self.name)
        for code in ('ALREADY_EXISTS','NOT_FOUND','INVALID_ARGUMENT','UNAVAILABLE','UNAUTHENTICATED','RESOURCE_EXHAUSTED'):
            c=self.client();c.send.side_effect=[RpcFailure(code),'Receipt','Receipt']
            q=PartyInviteQueue(PEOPLE,interval=0);result=c.invite_many(PEOPLE,CONTEXT,True,control=q)
            continuing=code in ('ALREADY_EXISTS','NOT_FOUND','INVALID_ARGUMENT')
            self.assertEqual(c.send.call_count,3 if continuing else 1,code)
            self.assertEqual(result['results'][0]['outcome'],'Skipped' if continuing else 'Check in game',code)
    def test_leaving_shard_is_skipped_without_stopping_other_requests(self):
        c=self.client();c.send.side_effect=['Receipt',PlayerLeftShard('Left the shard'),'Receipt'];q=PartyInviteQueue(PEOPLE,interval=0)
        result=c.invite_many(PEOPLE,CONTEXT,True,control=q)
        self.assertEqual([p['outcome'] for p in result['results']],['Sent','Skipped','Sent'])
    def test_friend_queue_skips_accepted_friends_and_uses_friend_action(self):
        c=self.client();c.relationships.return_value=dict(friends_at=1000,friends=[PEOPLE[0]['id']],party_at=1000,party=[])
        q=PartyInviteQueue(PEOPLE,interval=0,operation='friend');result=c.invite_many(PEOPLE,CONTEXT,True,control=q,operation='friend')
        self.assertEqual(result['results'][0]['outcome'],'Skipped');self.assertEqual(c.send.call_count,2)
        self.assertTrue(all(call.args[0]=='friend' for call in c.send.call_args_list))


if __name__=='__main__':unittest.main()
