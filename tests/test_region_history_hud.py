import unittest
from region_history_hud import recent_visits


class RecentVisitsTests(unittest.TestCase):
    def test_sorted_visits_current_session_and_taipei_times(self):
        old=dict(joined_at='2026-10-21T07:00:00Z',left_at='2026-10-21T09:00:00Z',region_display='EU',full_shard_id='old')
        new=dict(joined_at='2026-10-22T07:00:00Z',active=True,region_display='Asia',full_shard_id='new',server_name='Example')
        rows=recent_visits(dict(sessions=[old,new,dict(joined_at='invalid')],session_token='join',full_shard_id='new'))
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]['current'])
        self.assertEqual(rows[0]['times'],'2026-10-22 15:00:00 → now')
        self.assertEqual(rows[1]['times'],'2026-10-21 15:00:00 → 2026-10-21 17:00:00')

    def test_open_ended_old_visit_is_not_claimed_current(self):
        rows=recent_visits(dict(sessions=[dict(joined_at='2026-10-22T07:00:00Z',active=True,full_shard_id='old')]))
        self.assertFalse(rows[0]['current'])
        self.assertIn('end unrecorded',rows[0]['times'])

    def test_each_server_hop_is_retained_and_history_is_bounded(self):
        sessions=[dict(joined_at=f'2026-10-22T07:{i:02d}:00Z',region_display='Asia') for i in range(12)]
        self.assertEqual(len(recent_visits(dict(sessions=sessions))),8)
        self.assertEqual(sessions[0]['joined_at'],'2026-10-22T07:00:00Z')
