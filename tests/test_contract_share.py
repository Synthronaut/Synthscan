import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timezone
from contract_share import ContractQueue,LogRecords,accept_scan_code,ContractSession,accept_blockers

MID='11111111-2222-3333-4444-555555555555'
END=' [Team_CoreGameplayFeatures][Missions][Comms]\n'
def line(at,text):return '<'+datetime.fromtimestamp(at,timezone.utc).isoformat().replace('+00:00','Z')+'> [Notice] '+text
def push(at=100):return line(at,f'<MissionShared> Received share push message: ownerId[123] - missionId[{MID}]')+'\n'
def added(at=100.2,title='Contract Shared: Test',qid='8'):
    return line(at,f'<SHUDEvent_OnNotification> Added notification "{title}" [{qid}] to queue. New queue size: 8, MissionId: [00000000-0000-0000-0000-000000000000]')+END
def action(at=115.7,title='Contract Shared: Test',qid='8',verb='Next'):
    return line(at,f'<UpdateNotificationItem> Notification "{title}" [{qid}], Action: {verb}')+END

class ContractShareTests(unittest.TestCase):
    def test_movement_mouse_and_ordinary_gameplay_do_not_block_acceptance(self):
        self.assertEqual(accept_blockers([0x57,0x41,0x53,0x44,0x01,0x02],0xdc),())
    def test_modifiers_and_actual_accept_key_block_without_releasing_player_keys(self):
        for key in (0x10,0x11,0x12,0x5b,0x5c,0xa0,0xa5,0xdc):
            self.assertEqual(accept_blockers([0x57,key],0xdc),(key,))
    def test_contract_remains_eligible_after_old_750ms_limit_until_fade(self):
        q=self.queue();q.feed(action())
        self.assertIsNotNone(q.candidate(117));q.feed(action(117.5,verb='StartFade'))
        self.assertIsNone(q.candidate(117.6))
    def test_stale_and_wrong_owner_data_pause_without_changing_session(self):
        c=ContractSession();self.assertEqual(c.update(dict(owner_pid=4,written_at=100,session_token='join'),4,101),(True,True))
        for snap in (dict(owner_pid=4,written_at=90,session_token=None),dict(owner_pid=9,written_at=101,session_token='other')):
            self.assertEqual(c.update(snap,4,101),(False,False));self.assertEqual(c.token,'join')
        self.assertEqual(c.update(dict(owner_pid=4,written_at=102,session_token='join'),4,102),(True,False))
    def test_only_verified_fresh_session_changes_reset_queue(self):
        c=ContractSession();c.update(dict(owner_pid=4,written_at=100,session_token='a'),4,100)
        self.assertEqual(c.update(dict(owner_pid=4,written_at=101,session_token='b'),4,101),(True,True))
        self.assertEqual(c.update(dict(owner_pid=4,written_at=102,session_token=None),4,102),(False,True))
    def queue(self):
        q=ContractQueue();q.feed(push());q.feed(added());return q
    def test_queue_waits_for_exact_notification_even_after_long_backlog(self):
        q=self.queue();self.assertIsNone(q.candidate(101));q.feed(action(700))
        self.assertEqual(q.candidate(700.1)['mission'],MID)
    def test_party_friend_and_ordinary_next_replace_contract(self):
        for title in ('Party Invite Received: Accept Invitation?', 'Friend Request: Add to Friends?', 'Someone joined the party'):
            q=self.queue();q.feed(action());q.feed(action(115.8,title,'9'));self.assertIsNone(q.candidate(115.9))
    def test_queue_addition_does_not_replace_active_slot(self):
        q=self.queue();q.feed(action());q.feed(added(115.8,'Party Invite Received: Accept Invitation?','9'))
        self.assertIsNotNone(q.candidate(115.9))
    def test_fading_or_removed_share_never_qualifies(self):
        for verb in ('StartFade','Remove'):
            q=self.queue();q.feed(action());q.feed(action(115.8,verb=verb));self.assertIsNone(q.candidate(115.9))
    def test_unmatched_id_and_missing_push_fail_closed(self):
        q=self.queue();q.feed(action(qid='9'));self.assertIsNone(q.candidate(115.8))
        q=ContractQueue();q.feed(added());q.feed(action());self.assertIsNone(q.candidate(115.8))
    def test_replay_clock_jump_and_expired_activation_fail_closed(self):
        q=self.queue();q.feed(action())
        for now in (115,145.7,9999):self.assertIsNone(q.candidate(now))
    def test_ignored_accept_retries_same_prompt_and_fresh_reshare(self):
        q=self.queue();q.feed(action());q.attempted_once(q.candidate(115.8),115.8)
        self.assertIsNone(q.candidate(115.9))
        retry=q.candidate(116.6);self.assertIsNotNone(retry);self.assertTrue(q.attempted_once(retry,116.6))
        q.feed(push(120));q.feed(added(120.2,qid='10'));q.feed(action(121,qid='10'))
        self.assertEqual(q.candidate(121.1)['queue_id'],'10');self.assertEqual(q.view(121.1)['attempts'],2)
    def test_menu_closing_after_five_seconds_still_retries_until_prompt_closes(self):
        q=self.queue();q.feed(action());first=q.candidate(115.8);q.attempted_once(first,115.8)
        # The game ignores a key while a menu is up. No confirmation is fed.
        self.assertIsNotNone(q.candidate(122))
        q.attempted_once(q.candidate(122),122)
        self.assertIn('retrying',q.view(122.1)['message'])
        q.feed(action(122.2,verb='StartFade'));self.assertIsNone(q.candidate(123))
    def test_retries_are_rate_limited_bounded_and_cancelled_by_replacement(self):
        q=self.queue();q.feed(action());at=115.8
        for i in range(q.MAX_ATTEMPTS):
            candidate=q.candidate(at);self.assertIsNotNone(candidate);q.attempted_once(candidate,at)
            self.assertIsNone(q.candidate(at+.05));at+=q.RETRY_SECONDS
        self.assertIsNone(q.candidate(at));self.assertEqual(q.view(at)['attempts'],q.MAX_ATTEMPTS)
        for title in ('Party Invite Received: Accept Invitation?','Friend Request: Add to Friends?'):
            q=self.queue();q.feed(action());q.attempted_once(q.candidate(115.8),115.8)
            q.feed(action(116,title=title,qid='9'));self.assertIsNone(q.candidate(117))
    def test_duplicate_next_does_not_restart_timeout_or_retry_clock(self):
        q=self.queue();q.feed(action());q.attempted_once(q.candidate(115.8),115.8)
        q.feed(action(116));self.assertIsNone(q.candidate(116.1))
        q.feed(action(140));self.assertIsNone(q.candidate(146))
    def test_prompt_replaced_during_input_preparation_cancels_old_candidate(self):
        q=self.queue();q.feed(action());candidate=q.candidate(115.8)
        q.feed(action(115.9,title='Party Invite Received: Accept Invitation?',qid='9'))
        self.assertFalse(q.attempted_once(candidate,116));self.assertEqual(q.view(116)['attempts'],0)
    def test_confirmation_stops_retries_even_when_banner_remains_active(self):
        q=self.queue();q.feed(action());q.attempted_once(q.candidate(115.8),115.8)
        q.feed(added(116,'Contract Accepted: Test').replace('00000000-0000-0000-0000-000000000000',MID))
        self.assertIsNone(q.candidate(117));self.assertEqual(q.view(117)['confirmed'],1)
        q.feed(push(120));q.feed(added(120.2,qid='10'));q.feed(action(121,qid='10'))
        self.assertIsNone(q.candidate(122))
    def test_accepted_mission_confirms_attempt(self):
        q=self.queue();q.feed(action());q.attempted_once(q.candidate(115.8),115.8)
        q.feed(added(116,'Contract Accepted: Test').replace('00000000-0000-0000-0000-000000000000',MID))
        self.assertEqual(q.view(130)['confirmed'],1);self.assertIn('confirmed',q.message)
    def test_multiline_titles_and_unknown_update(self):
        q=ContractQueue();q.feed(push());q.feed(added(title='Contract Shared: Test\ncontinued'));q.feed(action(title='Contract Shared: Test\ncontinued'))
        self.assertIsNotNone(q.candidate(115.8))
        q.feed(line(115.9,'<UpdateNotificationItem> unknown format'));self.assertIsNone(q.candidate(116))
    def test_overlapping_shares_and_mismatched_titles_fail_closed(self):
        q=ContractQueue();q.feed(push());q.feed(push(100.1).replace(MID,'22222222-2222-3333-4444-555555555555'))
        q.feed(added());q.feed(action());self.assertIsNone(q.candidate(115.8))
        q=self.queue();q.feed(action(title='Contract Shared: Other'));self.assertIsNone(q.candidate(115.8))
    def test_tail_starts_at_eof_and_assembles_chunked_records(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text(push()+added()+action())
            r=LogRecords(p);self.assertEqual(r.read(),([],True))
            with p.open('a') as f:f.write(push(200)+added(200.2,title='Contract Shared: Test\ncontinued')+action(201)[:-10])
            records,reset=r.read();self.assertFalse(reset);self.assertEqual(len(records),2)
            with p.open('a') as f:f.write(action(201)[-10:])
            records,reset=r.read();self.assertEqual(len(records),1);self.assertIn('Action: Next',records[0])
            p.write_text('new session\n');self.assertEqual(r.read(),([],True))
    def test_accept_binding_is_notifications_not_legacy_invite(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'actionmaps.xml'
            p.write_text('<ActionMaps><actionmap name="ui_notification"><action name="ui_notification_accept"><rebind input="kb1_backslash"/></action></actionmap></ActionMaps>')
            self.assertEqual(accept_scan_code(p),('lbracket',0x1a))
            p.write_text('<ActionMaps><actionmap name="default"><action name="notification_accept"><rebind input="kb1_backslash"/></action></actionmap></ActionMaps>')
            self.assertEqual(accept_scan_code(p),('backslash',0x2b))
            p.write_text(p.read_text().replace('kb1_backslash','kb1_ '))
            with self.assertRaises(ValueError):accept_scan_code(p)



class SocialAcceptanceTests(unittest.TestCase):
    def test_social_requests_are_independently_opt_in(self):
        for kind,title in (('party','Party Invite Received: Accept Invitation?'),('friend','Friend Request: Add to Friends?')):
            for enabled in (False,True):
                q=ContractQueue(dict(contract=False,party=enabled if kind=='party' else False,friend=enabled if kind=='friend' else False))
                q.feed(added(title=title));q.feed(action(title=title))
                self.assertEqual(q.candidate(115.8) is not None,enabled)
                if enabled:
                    c=q.candidate(115.8);self.assertEqual(c['kind'],kind)
                    self.assertTrue(q.attempted_once(c,115.8))
                    self.assertIsNone(q.candidate(116))
                    self.assertIsNotNone(q.candidate(116.6))
                    q.feed(action(117,title=title,verb='StartFade'));self.assertIsNone(q.candidate(118))
    def test_social_requires_matching_added_and_active_prompt(self):
        title='Friend Request: Add to Friends?'
        q=ContractQueue(dict(friend=True));q.feed(action(title=title));self.assertIsNone(q.candidate(115.8))
        q.feed(added(title=title));q.feed(action(title='Friend Request Declined: Test'));self.assertIsNone(q.candidate(115.8))
        q.feed(action(title=title));c=q.candidate(115.8)
        q.feed(action(115.9,title='Party Invite Received: Accept Invitation?',qid='9'))
        self.assertFalse(q.attempted_once(c,116))
    def test_old_preferences_do_not_enable_social_acceptance(self):
        from contract_share import acceptance_settings
        self.assertEqual(acceptance_settings({'enabled':True}),dict(contract=True,party=False,friend=False))
        self.assertEqual(acceptance_settings({'enabled':False,'party_enabled':True}),dict(contract=False,party=True,friend=False))

if __name__=='__main__':unittest.main()
