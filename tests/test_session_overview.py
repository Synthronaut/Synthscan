import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from session_overview import SessionOverview,play_events


def line(text,when='2026-11-08T06:09:38.228Z'):
    return f'<{when}> [Notice] <SHUDEvent_OnNotification> Added notification "{text}: " [576] to queue. MissionId: [abc]'


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.log=self.root/'Game.log'
        self.log.write_text('<2026-11-08T06:00:00.000Z> Session started\n')
        self.book=SessionOverview(self.root,self.log)

    def snapshot(self,score,at=1794118200,character='one'):
        return dict(source='authenticated_reputation_service',own_character_verified=True,complete=True,character_key=character,read_at=at,
                    records=[dict(entity='faction:hh',scope='factionrep',score=score,standing_id='neutral',standing={'name':'Neutral'})])

    def test_notifications_are_not_counted_again_from_queue_dumps(self):
        event=play_events(line('Received Blueprint: <EM4>[BP]</EM4> Rifle'))[0]
        self.book.consume(event);self.book.consume(event)
        self.assertEqual(len(self.book.view()['current']['blueprints']),1)
        self.assertFalse(play_events('<2026-11-08T06:09:39Z> <UpdateNotificationItem> Notification "Received Blueprint: Rifle: " [576]'))

    def test_real_refinery_completion_and_plural_are_persistent_dismissible_reminders(self):
        event=play_events(line('A Refinery Work Order has been Completed at Orbituary'))[0]
        self.book.consume(event);self.book.save()
        restored=SessionOverview(self.root,self.log)
        self.assertIn('Orbituary',restored.view()['refinery_notice'])
        restored.dismiss_refinery();restored.consume(event)
        self.assertEqual(restored.view()['refinery_notice'],'')
        self.assertEqual(play_events(line('3 Refinery Work Orders have been Completed at Levski'))[0]['count'],3)

    def test_reputation_gains_use_verified_balance_changes_not_configured_rewards(self):
        self.book.reputation(self.snapshot(1000));self.book.reputation(self.snapshot(2500,1794118260))
        changes=self.book.view({'hh':'Headhunters'})['current']['reputation']
        self.assertEqual(changes[0]['delta'],1500);self.assertEqual(changes[0]['faction'],'Headhunters')
        self.book.reputation(dict(self.snapshot(9000,1794118320),own_character_verified=False))
        self.assertEqual(self.book.view()['current']['reputation'][0]['delta'],1500)

    def test_character_change_and_new_session_do_not_inherit_old_gains(self):
        self.book.reputation(self.snapshot(1000));self.book.reputation(self.snapshot(2500,1794118260))
        self.book.reputation(self.snapshot(5000,1794118320,'two'))
        self.assertEqual(self.book.view()['current']['reputation'],[])
        self.book.consume(play_events(line('Received Blueprint: Rifle'))[0]);self.book.save()
        self.log.write_text('<2026-11-09T06:00:00.000Z> Session started\n')
        self.book.rotate(True)
        view=self.book.view();self.assertEqual(view['current']['blueprints'],[])
        self.assertEqual(len(view['previous']['blueprints']),1)

    def test_old_balance_is_not_claimed_as_this_sessions_baseline(self):
        self.book.reputation(self.snapshot(100,1));self.book.reputation(self.snapshot(2500))
        self.assertEqual(self.book.view()['current']['reputation'],[])

    def test_contract_completion_deduplicates_mission_identity(self):
        self.book.consume(play_events(line('Contract Complete: Mission [100 Rep] [BP: 5 LEFT]'))[0])
        self.book.consume(play_events(line('Contract Complete: Mission [100 Rep] [BP: 5 LEFT]','2026-11-08T06:10:00Z'))[0])
        self.assertEqual(self.book.view()['current']['contracts_completed'],1)

    def test_corrupt_history_is_never_overwritten(self):
        path=self.root/'session_overview.json';path.write_text('broken')
        restored=SessionOverview(self.root,self.log);restored.save()
        self.assertTrue(restored.view()['history_warning']);self.assertEqual(path.read_text(),'broken')


if __name__=='__main__':unittest.main()
