import unittest
from reputation_ranks import (
    load_scopes,
    standing_progression,
    detect_promotion,
    primary_record_for_faction,
)


class ReputationRanksTests(unittest.TestCase):
    def test_load_scopes_succeeds(self):
        scopes = load_scopes()
        self.assertIn('FactionReputation', scopes)
        self.assertIn('Hauling', scopes)
        self.assertIn('BountyHunter', scopes)
        self.assertGreaterEqual(len(scopes['FactionReputation']['standings']), 6)

    def test_standing_progression_faction_reputation(self):
        # Neutral: 0, Jr. Contractor: 800, Contractor: 2200, Sr. Contractor: 5800,
        # Veteran Contractor: 15000, Head Contractor: 38000, Elite Contractor: 95250
        prog = standing_progression('FactionReputation', 16543)
        self.assertIsNotNone(prog)
        self.assertEqual(prog['current_rank'], 'Veteran Contractor')
        self.assertEqual(prog['next_rank'], 'Head Contractor')
        self.assertEqual(prog['points_needed'], 38000 - 16543)
        self.assertEqual(prog['is_max'], False)
        self.assertAlmostEqual(prog['progress_pct'], 6.7, places=1)

    def test_standing_progression_max_tier(self):
        prog = standing_progression('FactionReputation', 100000)
        self.assertIsNotNone(prog)
        self.assertEqual(prog['current_rank'], 'Elite Contractor')
        self.assertIsNone(prog['next_rank'])
        self.assertEqual(prog['points_needed'], 0)
        self.assertEqual(prog['progress_pct'], 100.0)
        self.assertTrue(prog['is_max'])

    def test_standing_progression_hauling_low(self):
        prog = standing_progression('Hauling', 100)
        self.assertIsNotNone(prog)
        self.assertEqual(prog['current_rank'], 'Rookie')
        self.assertEqual(prog['next_rank'], 'Junior')
        self.assertEqual(prog['points_needed'], 150)
        self.assertEqual(prog['progress_pct'], 25.0)

    def test_detect_promotion_single_tier(self):
        promo = detect_promotion('FactionReputation', 14800, 15200)
        self.assertIsNotNone(promo)
        self.assertEqual(promo['rank'], 'Veteran Contractor')
        self.assertEqual(promo['threshold'], 15000)
        self.assertEqual(promo['previous_rank'], 'Sr. Contractor')

    def test_detect_promotion_exact_threshold(self):
        promo = detect_promotion('FactionReputation', 799, 800)
        self.assertIsNotNone(promo)
        self.assertEqual(promo['rank'], 'Jr. Contractor')
        self.assertEqual(promo['threshold'], 800)

    def test_detect_promotion_none_when_no_threshold_crossed(self):
        promo = detect_promotion('FactionReputation', 15200, 16000)
        self.assertIsNone(promo)

    def test_detect_promotion_none_when_decrease(self):
        promo = detect_promotion('FactionReputation', 15200, 14000)
        self.assertIsNone(promo)

    def test_primary_record_for_faction(self):
        recs = [
            {'entity': 'org1', 'scope': 'Affinity', 'score': 50},
            {'entity': 'org1', 'scope': 'FactionReputation', 'score': 1500},
            {'entity': 'org1', 'scope': 'NPC_Reliability', 'score': 10},
        ]
        chosen = primary_record_for_faction(recs)
        self.assertEqual(chosen['scope'], 'FactionReputation')

    def test_primary_record_prefers_hauling_over_internal(self):
        recs = [
            {'entity': 'org2', 'scope': 'Affinity', 'score': 50},
            {'entity': 'org2', 'scope': 'Hauling', 'score': 100},
        ]
        chosen = primary_record_for_faction(recs)
        self.assertEqual(chosen['scope'], 'Hauling')


if __name__ == '__main__':
    unittest.main()
