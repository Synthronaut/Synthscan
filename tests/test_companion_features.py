from concurrent.futures import Future
import json
from pathlib import Path
from threading import Event
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from companion_features import CompanionService,CompanionStore,PresenceChanges,tag_labels,is_org,MARKET_INTERVAL
from companion_toasts import NoticeGate
from player_services import PlayerClient,PLAYER_PREFIX,PlayerLeftShard
from party_invites import PartyInviteQueue

ITEM=dict(id=5011,name='Carinite (Pure)',identity='fixture')
CONTEXT=dict(session_token='join',full_shard_id='pub_use1b_100_020',joined_at=100)
PERSON=dict(id=PLAYER_PREFIX+'2',handle='DemoZebra')


def offer(identifier,quality=1000,price=50,unit='unit'):
    return dict(id=identifier,quality=quality,price=price,unit=unit,url='https://uexcorp.space/marketplace/item/info/demo/',renewed=1000)


class ImmediatePool:
    def submit(self,function,*args,**kwargs):
        future=Future()
        try:future.set_result(function(*args,**kwargs))
        except Exception as error:future.set_exception(error)
        return future
    def shutdown(self,**kwargs):pass


class BuyerWatchTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name);self.store=CompanionStore(self.directory)
    def tearDown(self):self.temp.cleanup()
    def test_initial_load_is_quiet_and_only_new_exact_quality_alerts(self):
        self.store.watch(ITEM,1000)
        self.store.market_result(5011,[offer(1),offer(2,880)],1000)
        self.assertEqual(self.store.data['notifications'],[])
        self.store.market_result(5011,[offer(1),offer(3),offer(4,880),offer(5,None)],2800)
        self.assertEqual(len(self.store.data['notifications']),1)
        self.assertIn('Q1000',self.store.data['notifications'][0]['detail'])
    def test_seen_ads_survive_restart_and_edited_ads_do_not_repeat(self):
        self.store.watch(ITEM,1000);self.store.market_result(5011,[offer(1)],1000)
        self.store=CompanionStore(self.directory)
        self.store.market_result(5011,[offer(1,price=500),offer(2)],2800)
        self.store.market_result(5011,[offer(1,price=600),offer(2)],4600)
        self.assertEqual(len(self.store.data['notifications']),1)
    def test_price_requires_comparable_unit_and_pause_stops_ingest(self):
        watch=self.store.watch(ITEM,1000,100,'SCU');self.store.market_result(5011,[],1000)
        self.store.market_result(5011,[offer(1,price=500),offer(2,price=50,unit='SCU'),offer(3,price=150,unit='SCU')],2800)
        self.assertEqual(len(self.store.data['notifications']),1)
        watch['enabled']=False;self.store.market_result(5011,[offer(4,price=200,unit='SCU')],4600)
        self.assertEqual(len(self.store.data['notifications']),1)
    def test_thirty_minute_cadence_and_invalid_inputs(self):
        watch=self.store.watch(ITEM,1000);self.store.market_result(5011,[],1000)
        self.assertEqual(watch['due_at'],1000+1800);self.assertEqual(MARKET_INTERVAL,1800)
        for quality in (True,1001,-1,1000.5):
            with self.assertRaises(ValueError):self.store.watch(ITEM,quality)
        with self.assertRaises(ValueError):self.store.watch(ITEM,1000,100,'')
    def test_overlapping_watches_alert_once_per_ad_and_reject_exact_duplicates(self):
        self.store.watch(ITEM,1000);self.store.watch(ITEM,0)
        with self.assertRaises(ValueError):self.store.watch(ITEM,1000)
        self.store.market_result(5011,[],1000)
        self.store.market_result(5011,[offer(1)],2800)
        self.assertEqual(len(self.store.data['notifications']),1)
    def test_corrupt_private_file_is_preserved(self):
        self.store.path.write_text('{bad')
        bad=CompanionStore(self.directory);self.assertTrue(bad.read_only)
        with self.assertRaises(ValueError):bad.save()
        self.assertEqual(bad.path.read_text(),'{bad')


class TagAndJoinTests(unittest.TestCase):
    def test_category_and_custom_tags_can_coexist_and_deduplicate(self):
        self.assertEqual(tag_labels('friendly, Trader, friendly, Org Affiliate, Mining crew'),['Friendly','Trader','Org Affiliate','Mining crew'])
        self.assertEqual(tag_labels(''),[])
        with self.assertRaises(ValueError):tag_labels(','.join('tag'+str(i) for i in range(9)))
    def test_baseline_gaps_and_restart_are_quiet(self):
        gate=PresenceChanges()
        self.assertEqual(gate.observe([PERSON],1000),set())
        self.assertEqual(gate.observe([PERSON,dict(id='other')],1030),{'other'})
        self.assertEqual(gate.observe([dict(id='new')],1300),set())
        gate.reset();self.assertEqual(gate.observe([dict(id='new')],1330),set())
    def test_one_missing_snapshot_does_not_cause_false_rejoin(self):
        gate=PresenceChanges();gate.observe([PERSON],1000)
        gate.observe([],1030);self.assertEqual(gate.observe([PERSON],1060),set())
        gate.observe([],1090);gate.observe([],1120)
        self.assertEqual(gate.observe([PERSON],1150),{PERSON['id']})


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.social=Mock(return_value=dict(rows=[PERSON],observed_at=1000))
        self.market=Mock(return_value=([offer(1)],False))
        self.service=CompanionService(self.directory,42,social=self.social,market=self.market,pool=ImmediatePool())
        self.service.tick(CONTEXT,False,1000)
    def tearDown(self):self.service.close();self.temp.cleanup()
    def command(self,action,now=1001,**fields):
        return dict(id=action+str(now),action=action,at=now,owner_pid=42,session_token='join',**fields)
    def test_no_roster_poll_when_page_closed_and_no_tags(self):
        self.service.tick(CONTEXT,False,1010);self.social.assert_not_called()
        self.service.tick(CONTEXT,True,1011);self.assertEqual(self.social.call_args.args[0],'roster')
    def test_saved_tags_monitor_with_page_closed_and_only_new_arrivals_alert(self):
        self.service.store.data['tags'][PERSON['id']]=dict(handle='DemoZebra',label='Trader',alert=True)
        self.service.tick(CONTEXT,False,1001);self.service.tick(CONTEXT,False,1002)
        self.assertEqual(self.service.store.data['notifications'],[])
        self.social.return_value=dict(rows=[],observed_at=1032)
        self.service.tick(CONTEXT,False,1032);self.service.tick(CONTEXT,False,1033)
        self.service.tick(CONTEXT,False,1062);self.service.tick(CONTEXT,False,1063)
        self.social.return_value=dict(rows=[PERSON],observed_at=1092)
        self.service.tick(CONTEXT,False,1092);self.service.tick(CONTEXT,False,1093)
        self.assertEqual(len(self.service.store.data['notifications']),1)
        self.assertEqual(self.service.store.data['notifications'][0]['session_token'],'join')
    def test_wrong_owner_stale_and_wrong_session_never_send(self):
        self.service.roster=[PERSON]
        for extra in (dict(owner_pid=99),dict(at=900),dict(session_token='old')):
            command=self.command('friend',player_id=PERSON['id'],confirmed=True);command.update(extra)
            try:self.service.command(command,1001)
            except ValueError:pass
        self.social.assert_not_called()
        with self.assertRaises(ValueError):self.service.command(self.command('friend',player_id=PERSON['id']),1001)
    def test_confirmed_send_is_persisted_before_submission_and_not_replayed(self):
        self.service.roster=[PERSON];self.social.return_value='Friend request sent.'
        command=self.command('friend',player_id=PERSON['id'],confirmed=True)
        self.service.command(command,1001);self.service.command(command,1001)
        self.assertEqual(self.social.call_count,1)
        self.assertIn(command['id'],json.loads(self.service.store.path.read_text())['commands'])
    def test_market_calls_only_when_due_and_shared_by_watches(self):
        self.service.store.watch(ITEM,1000);self.service.store.watch(ITEM,880)
        self.service.tick(CONTEXT,False,1001);self.service.tick(CONTEXT,False,1002)
        self.assertEqual(self.market.call_count,1)
        self.service.tick(CONTEXT,False,2700);self.assertEqual(self.market.call_count,1)
        self.service.tick(CONTEXT,False,2802);self.assertEqual(self.market.call_count,2)
    def test_failed_roster_and_new_session_reset_arrival_baseline(self):
        self.service.tick(CONTEXT,True,1001);self.service.tick(CONTEXT,True,1002)
        self.social.side_effect=ValueError('Unavailable')
        self.service.tick(CONTEXT,True,1032);self.service.tick(CONTEXT,True,1033)
        self.assertIsNone(self.service.gate.members)
        self.service.tick(dict(CONTEXT,session_token='other'),False,1034)
        self.assertEqual(self.service.roster,[])


class BulkPeopleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.social=Mock()
        self.service=CompanionService(self.temp.name,42,social=self.social,pool=ImmediatePool())
        self.service.tick(CONTEXT,False,1000)
        self.other=dict(id=PLAYER_PREFIX+'3',handle='OtherPilot')
        self.service.roster=[PERSON,self.other,dict(id=PLAYER_PREFIX+'1',handle='Me',is_self=True)]
    def tearDown(self):self.service.close();self.temp.cleanup()
    def command(self,action,**fields):
        return dict(id=action,action=action,at=1001,owner_pid=42,session_token='join',player_ids=[PERSON['id'],self.other['id']],**fields)
    def test_mark_org_preserves_existing_tags_and_individual_alert_settings(self):
        self.service.store.data['tags'][PERSON['id']]=dict(handle=PERSON['handle'],label='Trader',alert=True)
        self.service.command(self.command('mark_org'),1001)
        tags=self.service.store.data['tags']
        self.assertEqual(tags[PERSON['id']]['label'],'Trader, Org');self.assertTrue(tags[PERSON['id']]['alert'])
        self.assertEqual(tags[self.other['id']]['label'],'Org');self.assertFalse(tags[self.other['id']]['alert'])
        self.assertTrue(is_org(dict(label='Org Affiliate')));self.assertFalse(is_org(dict(label='Org enemy')))
        self.service.publish(1001)
        rows=json.loads((Path(self.temp.name)/'companion_state.json').read_text())['rows']
        self.assertEqual([p['is_org'] for p in rows],[True,True,False])
    def test_bulk_add_and_explicit_clear_without_empty_save_erasing_tags(self):
        self.service.command(self.command('mark_org'),1001)
        self.service.command(self.command('tag_many',label='Friendly'),1001)
        self.assertEqual(self.service.store.data['tags'][PERSON['id']]['label'],'Org, Friendly')
        empty=self.command('tag_many',label='');empty['id']='empty'
        with self.assertRaises(ValueError):self.service.command(empty,1001)
        self.assertIn(PERSON['id'],self.service.store.data['tags'])
        empty.update(id='clear',clear_tags=True);self.service.command(empty,1001)
        self.assertEqual(self.service.store.data['tags'],{})
    def test_unknown_or_self_in_selection_prevents_all_tag_changes(self):
        command=self.command('mark_org');command['player_ids'].append(PLAYER_PREFIX+'1')
        with self.assertRaises(ValueError):self.service.command(command,1001)
        self.assertEqual(self.service.store.data['tags'],{})
        command['player_ids'][-1]='unknown'
        with self.assertRaises(ValueError):self.service.command(command,1001)
        self.assertEqual(self.service.store.data['tags'],{})
    def test_bulk_limit_error_does_not_partially_apply_tags(self):
        self.service.store.data['tags'][self.other['id']]=dict(handle=self.other['handle'],label=', '.join('tag'+str(i) for i in range(8)),alert=False)
        with self.assertRaises(ValueError):self.service.command(self.command('mark_org'),1001)
        self.assertNotIn(PERSON['id'],self.service.store.data['tags'])
    def test_org_batch_rechecks_local_tag_and_requires_confirmation_and_session(self):
        command=self.command('party_many',confirmed=True,org_only=True)
        with self.assertRaises(ValueError):self.service.command(command,1001)
        self.service.command(self.command('mark_org'),1001)
        command['confirmed']=False
        with self.assertRaises(ValueError):self.service.command(command,1001)
        command.update(confirmed=True,session_token='old')
        with self.assertRaises(ValueError):self.service.command(command,1001)
        self.social.assert_not_called()
    def test_confirmed_batch_is_deduplicated_persisted_and_not_replayed(self):
        self.service.command(self.command('mark_org'),1001)
        command=self.command('party_many',confirmed=True,org_only=True);command['player_ids'].append(PERSON['id'])
        self.service.command(command,1001);self.service.command(command,1001)
        self.social.assert_called_once()
        self.assertEqual(self.social.call_args.args[0],'party_many')
        self.assertEqual(len(self.social.call_args.kwargs['people']),2)
        self.assertIn('party_many',json.loads(self.service.store.path.read_text())['commands'])
    def test_batch_outcomes_are_visible_and_attempts_skipped_until_session_changes(self):
        self.social.return_value=dict(status='Partial batch',results=[dict(PERSON,outcome='Sent',detail='Receipt'),dict(self.other,outcome='Check in game',detail='Timeout')])
        self.service.command(self.command('party_many',confirmed=True),1001)
        another=self.command('party_many',confirmed=True);another['id']='another'
        with self.assertRaises(ValueError):self.service.command(another,1001)
        self.service.tick(CONTEXT,False,1002)
        state=json.loads((Path(self.temp.name)/'companion_state.json').read_text())
        self.assertEqual(len(state['batch_results']),2);self.assertFalse(state['social_busy'])
        self.service.command(another,1003)
        self.assertEqual(set(self.social.call_args.kwargs['previous']),{PERSON['id'],self.other['id']})
        cancellation=self.social.call_args.kwargs['cancel'];self.assertFalse(cancellation.is_set())
        self.service.tick(dict(CONTEXT,session_token='new'),False,1004)
        self.assertTrue(cancellation.is_set())
        self.assertEqual(self.service.invited,set());self.assertEqual(self.service.batch_results,[])
    def test_shutdown_cancels_remaining_batch_work(self):
        self.service.command(self.command('party_many',confirmed=True),1001)
        cancellation=self.social.call_args.kwargs['cancel'];self.assertFalse(cancellation.is_set())
        self.service.close();self.assertTrue(cancellation.is_set())


class BulkInvitationTests(unittest.TestCase):
    def client(self):
        client=object.__new__(PlayerClient);client.account=SimpleNamespace(subject=PLAYER_PREFIX+'1')
        client.roster=Mock(return_value=dict(rows=[dict(id=PLAYER_PREFIX+str(i)) for i in range(1,7)]))
        client.server_member_ids=Mock(return_value={PLAYER_PREFIX+str(i) for i in range(1,7)})
        client.relationships=Mock(return_value=dict(party_at=1000,party=[PLAYER_PREFIX+'1',PLAYER_PREFIX+'2']))
        client.send=Mock(return_value='Invitation receipt returned.')
        return client
    def people(self,*ids):return [dict(id=PLAYER_PREFIX+str(i),handle='Pilot'+str(i)) for i in ids]
    def test_only_eligible_recipients_sent_once_in_order(self):
        client=self.client();people=self.people(1,2,3,4,5,99)
        result=client.invite_many(people,CONTEXT,True,[PLAYER_PREFIX+'5'],control=PartyInviteQueue(people,interval=0))
        self.assertEqual([r['outcome'] for r in result['results']],['Skipped','Skipped','Sent','Sent','Skipped','Skipped'])
        self.assertEqual([c.args[1]['id'] for c in client.send.call_args_list],[PLAYER_PREFIX+'3',PLAYER_PREFIX+'4'])
        client.server_member_ids.assert_called_once_with(CONTEXT);client.relationships.assert_called_once_with(CONTEXT)
    def test_failure_stops_remaining_recipients_and_keeps_partial_receipts(self):
        client=self.client();client.send.side_effect=['Receipt',OSError('timeout')]
        people=self.people(3,4,5);result=client.invite_many(people,CONTEXT,True,control=PartyInviteQueue(people,interval=0))
        self.assertEqual([r['outcome'] for r in result['results']],['Sent','Check in game','Not sent'])
        self.assertEqual(client.send.call_count,2);self.assertIn('1 sent',result['status'])
    def test_unconfirmed_unknown_party_or_duplicate_batch_never_sends(self):
        client=self.client()
        with self.assertRaises(ValueError):client.invite_many(self.people(3),CONTEXT)
        with self.assertRaises(ValueError):client.invite_many(self.people(3,3),CONTEXT,True)
        client.relationships.return_value=dict(party_at=0,party=[])
        with self.assertRaises(ValueError):client.invite_many(self.people(3),CONTEXT,True)
        client.send.assert_not_called()
    def test_shutdown_or_session_change_stops_before_next_recipient(self):
        client=self.client();cancel=Event()
        def send(*args):cancel.set();return 'Receipt'
        client.send.side_effect=send
        result=client.invite_many(self.people(3,4,5),CONTEXT,True,cancel=cancel)
        self.assertEqual([r['outcome'] for r in result['results']],['Sent','Not sent','Not sent'])
        self.assertEqual(client.send.call_count,1);self.assertIn('2 not sent',result['status'])


class OutgoingActionTests(unittest.TestCase):
    def test_handle_search_marks_own_identity_for_selection_and_color(self):
        client=object.__new__(PlayerClient);client.scope=Mock();client.account=SimpleNamespace(subject=PLAYER_PREFIX+'1')
        client.message=Mock(return_value=lambda:SimpleNamespace(pagination=SimpleNamespace(first=0)))
        client.call=Mock(return_value=SimpleNamespace(accounts=[SimpleNamespace(nickname='Pilot'+str(i),player_id=i,account_id=i+10,display_name='Pilot') for i in (1,2)],page_info=SimpleNamespace(has_next_page=False)))
        rows=client.search('Pilot',CONTEXT)['rows']
        self.assertTrue(rows[0]['is_self']);self.assertFalse(rows[1]['is_self'])
    def client(self):
        client=object.__new__(PlayerClient);client.scope=Mock();client.account=SimpleNamespace(subject=PLAYER_PREFIX+'1')
        client.server_member_ids=Mock(return_value={PERSON['id']})
        client.search=Mock(return_value=dict(rows=[dict(PERSON,account_id=20,player_id='2')]))
        client.message=Mock(return_value=lambda:SimpleNamespace())
        client.call=Mock(return_value=SimpleNamespace(request_id='receipt',invitation=SimpleNamespace(id='invite')))
        return client
    def test_sending_requires_confirmed_action_and_exact_identity(self):
        client=self.client()
        with self.assertRaises(ValueError):client.send('friend',PERSON,CONTEXT)
        client.search.return_value=dict(rows=[dict(PERSON,id=PLAYER_PREFIX+'3',account_id=30,player_id='3')])
        with self.assertRaises(ValueError):client.send('friend',PERSON,CONTEXT,True)
        client.call.assert_not_called()
    def test_friend_and_party_use_separate_verified_recipients(self):
        client=self.client();self.assertIn('Friend request sent',client.send('friend',PERSON,CONTEXT,True))
        request=client.call.call_args.args[3];self.assertEqual((request.account_id,request.player_id),(20,2))
        self.assertIn('Party invitation sent',client.send('party',PERSON,CONTEXT,True))
        request=client.call.call_args.args[3];self.assertEqual(request.member_urn,PERSON['id'])
        self.assertEqual(client.call.call_args.args[2],'InviteToParty')
    def test_mutating_rpc_cannot_be_called_as_read(self):
        client=object.__new__(PlayerClient)
        with self.assertRaises(ValueError):client.call('contacts','ContactsService','SendFriendRequest',None)
    def test_shard_membership_is_rechecked_before_either_write(self):
        for action in ('friend','party'):
            client=self.client();client.server_member_ids.return_value=set()
            with self.assertRaises(PlayerLeftShard):client.send(action,PERSON,CONTEXT,True)
            client.call.assert_not_called()


class RelationshipTests(unittest.TestCase):
    def client(self,fail_friends=False):
        client=object.__new__(PlayerClient);client.scope=Mock();client.account=SimpleNamespace(subject=PLAYER_PREFIX+'1')
        def request(domain,name):
            return lambda:SimpleNamespace(relationship_types=[],filters=SimpleNamespace(types=[]),pagination=SimpleNamespace(first=0,after=''))
        client.message=request
        def call(domain,service,method,query):
            if method=='ListContacts':
                self.assertEqual(query.relationship_types,[1])
                if fail_friends:raise OSError('Unavailable')
                def contact(identifier,types):return SimpleNamespace(account=SimpleNamespace(player_id=identifier),relationships=[SimpleNamespace(type=t) for t in types])
                return SimpleNamespace(contacts=[contact(2,[1]),contact(3,[4]),contact(4,[1,2]),contact(5,[])],page_info=SimpleNamespace(has_next_page=False))
            self.assertEqual(query.filters.types,[4])
            def group(kind,ids):return SimpleNamespace(type=kind,members=[SimpleNamespace(urn=PLAYER_PREFIX+str(i)) for i in ids])
            return SimpleNamespace(groups=[group(2,[1,99]),group(4,[1,2])],page_info=SimpleNamespace(has_next_page=False))
        client.call=call;return client
    def test_confirmed_friends_only_and_own_party_not_server_group(self):
        result=self.client().relationships(CONTEXT)
        self.assertEqual(result['friends'],[PLAYER_PREFIX+'2'])
        self.assertEqual(result['party'],[PLAYER_PREFIX+'1',PLAYER_PREFIX+'2'])
        self.assertTrue(result['friends_at']);self.assertTrue(result['party_at'])
    def test_friend_failure_does_not_erase_verified_party_status(self):
        result=self.client(True).relationships(CONTEXT)
        self.assertEqual(result['friends_at'],0);self.assertTrue(result['friends_error'])
        self.assertTrue(result['party_at']);self.assertIn(PLAYER_PREFIX+'2',result['party'])
    def test_own_row_is_you_even_when_in_party_or_relationships_expire(self):
        with tempfile.TemporaryDirectory() as directory:
            service=CompanionService(directory,42,social=Mock(),pool=ImmediatePool())
            try:
                service.roster=[dict(PERSON,is_self=True)]
                service.relationships=dict(friends=[PERSON['id']],party=[PERSON['id']],friends_at=1000,party_at=1000)
                for now in (1001,1120):
                    service.publish(now)
                    row=json.loads((Path(directory)/'companion_state.json').read_text())['rows'][0]
                    self.assertTrue(row['is_self']);self.assertEqual(row['relationship'],'You')
            finally:service.close()
    def test_manual_friendly_tag_is_not_a_friend_and_stale_flags_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            service=CompanionService(directory,42,social=Mock(),pool=ImmediatePool())
            try:
                service.roster=[PERSON];service.store.data['tags'][PERSON['id']]=dict(handle=PERSON['handle'],label='Friendly',alert=False)
                service.publish(1001)
                read=lambda:json.loads((Path(directory)/'companion_state.json').read_text())['rows'][0]
                self.assertFalse(read()['is_friend']);self.assertFalse(read()['in_party'])
                service.relationships=dict(friends=[PERSON['id']],party=[PERSON['id']],friends_at=1000,party_at=1000)
                service.publish(1001);self.assertTrue(read()['is_friend']);self.assertTrue(read()['in_party']);self.assertEqual(read()['relationship'],'Party + Friend')
                service.publish(1120);self.assertFalse(read()['is_friend']);self.assertFalse(read()['in_party']);self.assertEqual(read()['relationship'],'Unknown')
            finally:service.close()


class ToastGateTests(unittest.TestCase):
    def test_old_wrong_session_hidden_and_repeated_events_are_silent(self):
        gate=NoticeGate(100);event=dict(id='a',kind='player_join',at=101,session_token='join')
        snapshot=dict(owner_pid=42,written_at=101,events=[event])
        self.assertEqual(gate.consume(snapshot,42,'other',True,102),[])
        self.assertEqual(gate.consume(snapshot,42,'join',True,102),[])
        event=dict(event,id='b');snapshot['events']=[event]
        self.assertEqual(gate.consume(snapshot,42,'join',False,102),[])
        self.assertEqual(gate.consume(snapshot,42,'join',True,102),[])
        snapshot['events']=[dict(event,id='c',at=99)]
        self.assertEqual(gate.consume(snapshot,42,'join',True,102),[])
    def test_buyer_alert_is_session_independent_and_one_shot(self):
        gate=NoticeGate(100);event=dict(id='a',kind='buyer_match',at=101)
        snapshot=dict(owner_pid=42,written_at=101,events=[event])
        self.assertEqual(gate.consume(snapshot,42,None,True,102),[event])
        self.assertEqual(gate.consume(snapshot,42,None,True,102),[])


if __name__=='__main__':unittest.main()
