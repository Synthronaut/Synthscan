import unittest

from tools.audit_blueprint_reward_order import associate, completions, grants


class BlueprintRewardOrderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.reward = dict(at='2026-11-08T01:00:00.500', name='S71 Rifle')
        self.complete = dict(at='2026-11-08T01:00:00.000', mission_id='m1', contract='Generator/Mission_0')
        self.pool = dict(id='pool1', name='Pool', members=[dict(id='bp1', name='S71 Rifle', record_position=3)])
        self.contracts = {('generator', 'mission'): [self.pool]}

    def test_grant_queue_dump_and_fade_are_not_second_grants(self):
        line = '<2026-11-08T01:00:00.500Z> [Notice] <SHUDEvent_OnNotification> Added notification "Received Blueprint: S71 Rifle: " [10]'
        text = '\n'.join([line, line, '<2026-11-08T01:00:01Z> "Received Blueprint: S71 Rifle: " [10]',
                          '<2026-11-08T01:00:02Z> <UpdateNotificationItem> Notification "Received Blueprint: S71 Rifle: "'])
        self.assertEqual(grants(text), [self.reward])

    def test_patches_and_acceptances_do_not_mix(self):
        text = '\n'.join(['completed\t2026-11-08T01:00:00\tm1\tGenerator/Mission_0\t41002',
                          'completed\t2026-11-08T01:00:01\tm2\tGenerator/Mission_0\t41001',
                          'accepted\t2026-11-08T01:00:02\tm3\tGenerator/Mission_0\t41002'])
        self.assertEqual([c['mission_id'] for c in completions(text, 41002)], ['m1'])

    def test_matching_grant_keeps_record_position_separate(self):
        rows, unresolved = associate([self.reward], [self.complete], self.contracts)
        self.assertEqual(unresolved, [])
        self.assertEqual(rows[0]['stored_position'], 3)
        self.assertEqual(rows[0]['blueprint_id'], 'bp1')
        self.assertNotIn('completion_number', rows[0])

    def test_nearest_of_two_completions_is_not_selected(self):
        second = dict(self.complete, mission_id='m2', at='2026-11-08T01:00:00.400')
        rows, unresolved = associate([self.reward], [self.complete, second], self.contracts)
        self.assertEqual(rows, [])
        self.assertIn('unique nearby', unresolved[0]['reason'])

    def test_same_name_in_two_pools_is_ambiguous(self):
        other = dict(self.pool, id='pool2')
        rows, unresolved = associate([self.reward], [self.complete], {('generator', 'mission'): [self.pool, other]})
        self.assertEqual(rows, [])
        self.assertIn('unique matching', unresolved[0]['reason'])

    def test_late_notification_is_not_attached(self):
        rows, unresolved = associate([dict(self.reward, at='2026-11-08T01:00:10')], [self.complete], self.contracts)
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)


if __name__ == '__main__':
    unittest.main()
