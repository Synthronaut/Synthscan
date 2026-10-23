import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from questing import Questing, mission_event, own_missions
from types import SimpleNamespace as NS

MID='a953281c-f34f-45ad-9793-094de0c9a2fb'
ACCEPT='<SHUDEvent_OnNotification> Added notification "Contract Accepted:  Deliver Things <EM4>[100 Rep]</EM4>: " MissionId: ['+MID+']'
END='<EndMission> Ending mission for player. MissionId['+MID+'] CompletionType[Abandon] Reason[Player left]'

class QuestingTest(unittest.TestCase):
    def test_disabled_reader_never_starts_an_account_query(self):
        from unittest.mock import patch
        with TemporaryDirectory() as d:
            q=Questing(d,Path(d)/'missing.log')
            try:
                with patch.object(q,'query') as query:
                    q.tick(False,True)
                    self.assertIsNone(q.future)
                    query.assert_not_called()
            finally:q.close()

    def test_real_log_shapes_and_nonmatching_presentations(self):
        self.assertEqual(mission_event(ACCEPT),dict(id=MID,title='Deliver Things [100 Rep]',status='Accepted'))
        self.assertEqual(mission_event(END)['status'],'Abandon')
        self.assertIsNone(mission_event(ACCEPT.replace('<SHUDEvent_OnNotification>','<SHUDEvent_OnNotificationQueue>')))

    def test_definition_before_accept_is_retained(self):
        marker='<CLocalMissionPhaseMarker::CreateMarker> missionId ['+MID+'] contractDefinitionId[4f735fe1-caec-4c9d-acba-606d8e096ba6]'
        with TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text(marker+'\n'+ACCEPT+'\n')
            q=Questing(d,p)
            try:
                q.poll_log()
                self.assertEqual(q.journal[MID]['definition_id'],'4f735fe1-caec-4c9d-acba-606d8e096ba6')
                self.assertEqual(q.tick(False)['count'],1)
            finally:q.close()

    def test_terminal_log_event_overrides_delayed_active_service_state(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text(ACCEPT+'\n'+END+'\n');q=Questing(d,p)
            try:
                q.read_at=1000;q.service=[dict(id=MID,state=2,definition_id='definition',participants=1)]
                self.assertEqual(q.tick(False,now=1001)['count'],0)
            finally:q.close()

    def test_duplicate_partial_lines_and_abandon_never_add_balance(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text(ACCEPT+'\n'+ACCEPT+'\n'+END[:40])
            q=Questing(d,p)
            try:
                q.poll_log();self.assertEqual(len(q.journal),1)
                self.assertEqual(q.journal[MID]['status'],'Accepted')
                with p.open('a') as f:f.write(END[40:]+'\n')
                q.poll_log();self.assertEqual(q.journal[MID]['status'],'Abandon')
                self.assertEqual(q.tick(False)['count'],0)
                self.assertFalse((Path(d)/'reputation_snapshot.json').exists())
            finally:q.close()

    def test_contract_reward_split_scenario_and_verified_balance(self):
        with TemporaryDirectory() as d:
            q=Questing(d,Path(d)/'missing.log')
            try:
                q.read_at=1000
                q.service=[dict(id=MID,state=2,definition_id='definition',participants=2)]
                q.catalog={'definition':dict(title='Adagio delivery',payout=12000,rewards=[dict(faction='Adagio',scope='Security',configured_amount=100)])}
                q.balance_names={'123':'Adagio'};q.scopes={'Security':dict(standings=[dict(minimum=800)])}
                p=Path(d)/'reputation_snapshot.json'
                p.write_text(json.dumps(dict(complete=True,own_character_verified=True,read_at=1000,records=[dict(entity='urn:sc:reputations:org:geid:123',scope='Security',score=249)])))
                result=q.tick(False,now=1012)
                self.assertIn('Equal-split scenario: 6,000 aUEC each',result['lines'])
                self.assertIn('Equal-split scenario: +50.0 rep each',result['lines'])
                self.assertIn('Adagio / Security: 249 / 800 verified',result['lines'])
                self.assertEqual(json.loads(p.read_text())['records'][0]['score'],249)
                result=q.tick(False,now=1100)
                self.assertNotIn('verified',' '.join(result['lines']))
            finally:q.close()

    def test_log_rotation_clears_old_accepted_candidates(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'Game.log';p.write_text(ACCEPT+'\n');q=Questing(d,p)
            try:
                q.poll_log();self.assertEqual(q.tick(False)['count'],1)
                p.write_text('new log\n');q.poll_log();self.assertEqual(q.tick(False)['count'],0)
            finally:q.close()

    def test_reject_service_mission_without_own_participation(self):
        class Bodies(list):
            def add(self):
                value=NS();self.append(value);return value
        class Client:
            subject='urn:sc:global:player:geid:123'
            def message(self,name):return NS(queries=Bodies())
            def read(self,domain,service,method,q):
                if method=='QueryActiveMissions':return NS(mission_ids=[NS(mission_id=MID)])
                return NS(missions=[NS(mission_id=MID,participants=[NS(player_urn='another-character')])])
        with self.assertRaisesRegex(ValueError,'own participation'):own_missions(Client())

if __name__=='__main__':unittest.main()
