"""No outgoing requests: verified friends, explicit retries and per-person receipts."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace
from companion_features import CompanionService
from party_invites import PartyInviteQueue
from player_services import PlayerClient,PlayerLeftShard,PLAYER_PREFIX
import test_party_invites as fixtures

class PeoplePolishTests(unittest.TestCase):
    setUp=fixtures.QueueServiceTests.setUp
    tearDown=fixtures.QueueServiceTests.tearDown
    command=fixtures.QueueServiceTests.command
    def friend_context(self):
        friend=dict(id=PLAYER_PREFIX+'900',handle='VerifiedElsewhere')
        self.service.relationships=dict(friends_at=1000,friends=[friend['id'],fixtures.PEOPLE[0]['id']],friend_rows=[friend],party_at=1000,party=[])
        return friend
    def test_automatic_friend_and_custom_friendly_are_distinct_and_not_persisted(self):
        self.friend_context();p=fixtures.PEOPLE[0]
        self.service.store.data['tags'][p['id']]=dict(handle=p['handle'],label='Friendly',alert=False)
        self.service.publish(1001)
        view=json.loads((Path(self.temp.name)/'companion_state.json').read_text())
        row=next(r for r in view['rows'] if r['id']==p['id'])
        self.assertEqual(row['tag'],'Friendly, Friend');self.assertEqual(row['manual_tag'],'Friendly')
        self.assertEqual(self.service.store.data['tags'][p['id']]['label'],'Friendly')
        self.service.relationships['friends']=[];self.service.publish(1002)
        row=json.loads((Path(self.temp.name)/'companion_state.json').read_text())['rows'][0]
        self.assertEqual(row['tag'],'Friendly')
    def test_add_friends_stages_verified_friends_on_other_shards_too(self):
        friend=self.friend_context()
        self.service.command(self.command('stage_tag',label='Friend'),1001)
        ids={p['id'] for p in self.service.store.data['actions']}
        self.assertEqual(ids,{friend['id'],fixtures.PEOPLE[0]['id']})
        self.service.command(self.command('party_many',player_ids=list(ids),from_actions=True,confirmed=True,resend=True),1001)
        self.assertTrue(self.pool.calls[-1][1]['allow_friends'])
        self.service.publish(1001)
        self.assertEqual(len(json.loads((Path(self.temp.name)/'companion_state.json').read_text())['action_people']),2)
    def test_stale_or_unverified_friend_cannot_be_staged(self):
        friend=self.friend_context();self.service.relationships['friends_at']=1
        with self.assertRaises(ValueError):self.service.command(self.command('stage_people',player_ids=[friend['id']]),1001)
        self.assertEqual(self.pool.calls,[])
    def test_success_and_warning_are_separate_per_operation_and_survive_restart(self):
        person=fixtures.PEOPLE[0]
        q=PartyInviteQueue([person],'friend-one',operation='friend',interval=0)
        q.update(dict(person,outcome='Sent',detail='Receipt returned'));q.finish();self.service.invite_queue=q;self.service.publish(1001)
        q=PartyInviteQueue([person],'party-one',operation='party',interval=0)
        q.update(dict(person,outcome='Check in game',detail='No invitation receipt returned'));q.finish();self.service.invite_queue=q;self.service.publish(1002)
        status=json.loads((Path(self.temp.name)/'companion_state.json').read_text())['rows'][0]['requests']
        self.assertEqual(status['friend']['outcome'],'Sent');self.assertEqual(status['party']['outcome'],'Check in game')
        self.service.close();self.service=CompanionService(self.temp.name,42,social=Mock(),pool=self.pool)
        self.service.tick({},False,1002.5) # Cold bridge startup must not erase the previous join's receipts.
        self.service.tick(fixtures.CONTEXT,False,1003)
        self.assertEqual(self.service.store.data['request_results'][person['id']]['friend']['outcome'],'Sent')
    def test_queued_request_does_not_receive_success_marker(self):
        person=fixtures.PEOPLE[0];self.service.invite_queue=PartyInviteQueue([person],'pending',operation='party')
        self.service.publish(1001)
        row=json.loads((Path(self.temp.name)/'companion_state.json').read_text())['rows'][0]
        self.assertEqual(row['requests']['party']['outcome'],'Queued')
        self.assertNotIn(person['id'],self.service.store.data['request_results'])
    def test_explicit_retry_bypasses_attempt_history_but_duplicate_command_does_not_resend(self):
        self.service.invite_history.record('join',fixtures.PEOPLE[0])
        command=self.command('party_many',player_ids=[fixtures.PEOPLE[0]['id']],confirmed=True,resend=True)
        self.service.command(command,1001);self.assertEqual(self.pool.calls[-1][1]['previous'],[])
        before=len(self.pool.calls);self.service.command(command,1001);self.assertEqual(len(self.pool.calls),before)

class VerifiedFriendTransportTests(unittest.TestCase):
    def client(self):
        c=object.__new__(PlayerClient);c.account=SimpleNamespace(subject=PLAYER_PREFIX+'1')
        c.scope=Mock();c.server_member_ids=Mock(return_value=set())
        self.person=dict(id=PLAYER_PREFIX+'900',handle='VerifiedElsewhere',account_id='account',player_id='900')
        c.search=Mock(return_value=dict(rows=[self.person]))
        c.relationships=Mock(return_value=dict(friends_at=1000,friends=[self.person['id']]))
        c.message=Mock(return_value=SimpleNamespace);c.call=Mock(return_value=SimpleNamespace(invitation=SimpleNamespace(id='receipt')))
        return c
    def test_party_invite_to_verified_friend_outside_shard_checks_receipt(self):
        c=self.client();text=c.send('party',self.person,fixtures.CONTEXT,True,allow_friend=True)
        self.assertIn('sent',text);c.call.assert_called_once();self.assertTrue(c.call.call_args.kwargs['confirmed'])
    def test_unverified_other_shard_target_is_never_sent(self):
        c=self.client();c.relationships.return_value=dict(friends_at=1000,friends=[])
        with self.assertRaises(PlayerLeftShard):c.send('party',self.person,fixtures.CONTEXT,True,allow_friend=True)
        c.call.assert_not_called()
    def test_missing_receipt_is_not_success(self):
        c=self.client();c.call.return_value.invitation.id=''
        with self.assertRaisesRegex(ValueError,'receipt'):c.send('party',self.person,fixtures.CONTEXT,True,allow_friend=True)
