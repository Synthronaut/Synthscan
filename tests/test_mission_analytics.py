import unittest
from datetime import datetime

from mission_analytics import analyze

DAY1 = datetime(2026, 11, 10, 12).timestamp()
DAY2 = datetime(2026, 11, 11, 12).timestamp()


def wallet(delta, end, category='unclassified', source='Unclassified', **extra):
    return dict(kind='wallets', track='AUEC', delta=delta, end=end, reason='Single completion in window',
                classification=dict(category=category, source=source, **extra), missions=[])


class MissionAnalyticsTests(unittest.TestCase):
    def view(self):
        return dict(
            rows=[dict(status='Complete'), dict(status='Failed')],
            changes=[
                wallet(50000, DAY1, 'mission_reward', 'Mission completion correlation', mission_giver='Hurston Dynamics', mission_title='Delivery'),
                wallet(30000, DAY1, 'mission_reward', 'Mission completion correlation', mission_giver='Hurston Dynamics', mission_title='Cargo'),
                wallet(20000, DAY2, 'mission_reward', 'Mission completion correlation', reward_organizations=['Citizens for Prosperity'], mission_title='Bounty'),
                wallet(9000, DAY2),
                wallet(-12000, DAY2, 'repair'),
                dict(kind='reputation', track='ent1|scope', delta=120, end=DAY2, reason='x', classification={}),
                dict(kind='wallets', track='AUEC', delta=5, end=DAY2, reason='Session boundary', classification={}),
            ],
            sessions=[dict(id='s1', started_at=DAY1, ended_at=DAY2, completed=3, wallet=[dict(currency='AUEC', delta=97000)])])

    def test_faction_money_only_from_correlated_windows(self):
        result = analyze(self.view(), {'ent1': 'Hurston Dynamics'})
        by_name = {f['name']: f for f in result['factions']}
        self.assertEqual(by_name['Hurston Dynamics']['auec'], 80000)
        self.assertEqual(by_name['Hurston Dynamics']['missions'], 2)
        self.assertEqual(by_name['Hurston Dynamics']['avg_per_mission'], 40000)
        self.assertEqual(by_name['Hurston Dynamics']['rep_net'], 120)
        self.assertEqual(by_name['Citizens for Prosperity']['auec'], 20000)
        self.assertEqual(result['factions'][0]['name'], 'Hurston Dynamics')

    def test_totals_categories_daily_and_boundaries_excluded(self):
        result = analyze(self.view())
        totals = result['totals']
        self.assertEqual((totals['gains'], totals['losses'], totals['net']), (109000, 12000, 97000))
        self.assertEqual(totals['attributed'], 100000)
        self.assertEqual(totals['unattributed_gain'], 9000)
        self.assertEqual(totals['missions_completed'], 1)
        cats = {c['key']: c for c in result['categories']}
        self.assertEqual(cats['repair']['loss'], 12000)
        self.assertEqual([d['net'] for d in result['daily']], [80000, 17000])
        self.assertEqual(result['sessions'][0]['net'], 97000)

    def test_empty_view(self):
        result = analyze(dict(rows=[], changes=[], sessions=[]))
        self.assertEqual(result['totals']['net'], 0)
        self.assertEqual(result['factions'], [])

    def test_reputation_standing_progression_and_promotions_in_analytics(self):
        view = self.view()
        view['latest_reputation'] = {
            'ent1|FactionReputation': {'entity': 'ent1', 'scope': 'FactionReputation', 'score': 16543}
        }
        view['changes'].append({
            'kind': 'reputation', 'track': 'ent1|FactionReputation', 'delta': 400, 'end': DAY2,
            'promotion': {'rank': 'Veteran Contractor', 'threshold': 15000, 'scope': 'FactionReputation'}
        })
        result = analyze(view, {'ent1': 'Hurston Dynamics'})
        by_name = {f['name']: f for f in result['factions']}
        hurston = by_name['Hurston Dynamics']
        self.assertEqual(hurston['standing'], 'Veteran Contractor')
        self.assertEqual(hurston['next_standing'], 'Head Contractor')
        self.assertEqual(hurston['points_to_next'], 38000 - 16543)
        self.assertAlmostEqual(hurston['rep_progress_pct'], 6.7, places=1)
        self.assertEqual(len(result['promotions']), 1)
        self.assertEqual(result['promotions'][0]['rank'], 'Veteran Contractor')
        self.assertEqual(result['promotions'][0]['faction'], 'Hurston Dynamics')


if __name__ == '__main__':
    unittest.main()
