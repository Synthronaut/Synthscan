import copy
import json
from pathlib import Path
import tempfile
import unittest

from refinery_orders import RefineryOrderBook
from screen_readers import TextBox, fabricator_candidates, refinery_orders, duration


def box(text, x=20, y=10, width=100, score=.99):
    return TextBox(text, score, x, y, x+width, y+18)


def panel(status='COMPLETED', number=1, offset=0):
    return [box(status, offset+20, 50), box(f'WORK ORDER {number}', offset+300, 50, 140),
            box('MATERIALS YIELDED (CSCU)', offset+20, 90, 190),
            box('QUALITY', offset+220, 90, 60), box('YIELD', offset+300, 90, 60),
            box('IRON', offset+25, 140), box('874', offset+225, 140, 50), box('235', offset+305, 140, 50)]


class ReaderTests(unittest.TestCase):
    def test_blueprint_exact_rows_need_fabricator_context(self):
        self.assertEqual(fabricator_candidates([box('FR-76')]), [])
        found = fabricator_candidates([box('FABRICATOR'), box('FR-76'), box('XL-1')])
        self.assertEqual({b['name'] for b in found}, {'FR-76', 'XL-1'})
        self.assertTrue(all(b['ownership'] == 'review' for b in found))

    def test_partial_variants_and_generic_words_not_imported(self):
        self.assertEqual(fabricator_candidates([box('BLUEPRINT LIBRARY'), box('ADP Arms'), box('Laser Rifle')]), [])

    def test_duplicate_rows_deduplicated(self):
        self.assertEqual(len(fabricator_candidates([box('BLUEPRINTS'), box('FR-76'), box('FR-76')])), 1)

    def test_low_confidence_cannot_create_blueprint(self):
        self.assertEqual(fabricator_candidates([box('FABRICATOR'), box('FR-76', score=.89)]), [])

    def test_refinery_centiscu_and_quality_are_separate(self):
        rows = refinery_orders([box('Levski')] + panel())
        self.assertEqual(rows[0]['parts'], [dict(material='Iron', quality=874, scu=2.35)])
        self.assertEqual(rows[0]['status'], 'completed')

    def test_two_side_by_side_panels_do_not_cross_pair(self):
        rows = refinery_orders([box('Levski')] + panel() + panel(number=2, offset=500))
        self.assertEqual([r['number'] for r in rows], [1, 2])
        self.assertEqual([len(r['parts']) for r in rows], [1, 1])

    def test_setup_is_not_a_placed_order(self):
        self.assertEqual(refinery_orders(panel(status='SETUP'), 'Levski'), [])

    def test_unknown_station_is_not_guessed(self):
        self.assertEqual(refinery_orders(panel()), [])

    def test_explicit_station_and_scu(self):
        boxes = panel()
        boxes[2] = box('MATERIALS YIELDED (SCU)', 20, 90, 190)
        rows = refinery_orders([box('STATION: Checkmate')] + boxes)
        self.assertEqual(rows[0]['parts'][0]['scu'], 235)

    def test_conflicting_station_labels_are_not_assigned_to_hint(self):
        self.assertEqual(refinery_orders([box('Levski'), box('Checkmate')] + panel(), 'Orbituary'), [])

    def test_arbitrary_station_label_is_not_persisted(self):
        self.assertEqual(refinery_orders([box('STATION: Not a station')] + panel()), [])

    def test_quality_not_in_material_bands_is_rejected(self):
        boxes = panel()
        boxes[-2] = box('674', 225, 140, 50)
        self.assertEqual(refinery_orders(boxes, 'Levski'), [])

    def test_missing_column_or_unknown_units_is_rejected(self):
        boxes = panel()
        boxes[2] = box('MATERIALS YIELDED', 20, 90, 190)
        self.assertEqual(refinery_orders(boxes, 'Levski'), [])
        self.assertEqual(refinery_orders([b for b in panel() if b.text != 'QUALITY'], 'Levski'), [])

    def test_time_parser_rejects_ambiguous_bare_number(self):
        self.assertEqual(duration('1h 2m 3s'), 3723)
        self.assertIsNone(duration('45'))


class OrderBookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'orders.json'
        self.book = RefineryOrderBook(self.path)
        self.order = dict(station='Levski', number=1, status='processing', remaining_seconds=10,
                          parts=[dict(material='Iron', quality=874, scu=2.35)])

    def tearDown(self):
        self.temp.cleanup()

    def agree(self, observation=None, start=100):
        obs = observation or self.order
        self.book.observe(obs, now=start)
        return self.book.observe(obs, now=start+6)

    def test_two_reads_required_and_persisted(self):
        self.assertEqual(self.book.observe(self.order, now=100), 'awaiting_confirmation')
        self.assertFalse(self.path.exists())
        self.assertEqual(self.book.observe(self.order, now=106), 'updated')
        self.assertEqual(len(RefineryOrderBook(self.path).snapshot()), 1)

    def test_timer_does_not_confirm_completion(self):
        self.agree()
        row = self.book.snapshot(now=200)[0]
        self.assertEqual(row['status'], 'processing')
        self.assertIn('needs terminal confirmation', row['display_status'])

    def test_repeated_completion_is_not_another_haul(self):
        done = dict(self.order, status='completed', remaining_seconds=None)
        self.assertEqual(self.agree(done), 'completed')
        self.assertEqual(self.book.observe(done, now=113), 'updated')
        self.assertEqual(len(self.book.snapshot()), 1)
        self.assertEqual(self.book.snapshot()[0]['parts'][0]['scu'], 2.35)

    def test_same_ore_different_qualities_remain_separate(self):
        order = copy.deepcopy(self.order)
        order['parts'].append(dict(material='Iron', quality=907, scu=1.5))
        self.agree(order)
        self.assertEqual(len(self.book.snapshot()[0]['parts']), 2)

    def test_partial_scroll_merges_without_doubling(self):
        self.agree()
        other = dict(self.order, parts=[dict(material='Gold', quality=864, scu=1)])
        self.agree(other, start=120)
        self.assertEqual(len(self.book.snapshot()[0]['parts']), 2)

    def test_yield_conflict_requires_review(self):
        self.agree()
        wrong = dict(self.order, parts=[dict(material='Iron', quality=874, scu=9)])
        self.assertEqual(self.agree(wrong, start=120), 'yield_conflict_review_required')
        self.assertEqual(self.book.snapshot()[0]['parts'][0]['scu'], 2.35)

    def test_collected_order_can_be_archived_for_number_reuse(self):
        done = dict(self.order, status='completed')
        self.agree(done)
        key = self.book.snapshot()[0]['id']
        self.book.mark_collected(key, now=120)
        self.assertEqual(self.agree(start=130), 'number_reused_review_required')
        self.book.archive_for_reuse(key)
        self.agree(start=150)
        self.assertEqual(len(self.book.snapshot()), 2)

    def test_incomplete_order_cannot_be_marked_collected(self):
        self.agree()
        with self.assertRaises(ValueError):
            self.book.mark_collected(self.book.snapshot()[0]['id'])

    def test_disagreeing_or_stale_reads_not_confirmed(self):
        self.book.observe(self.order, now=100)
        changed = dict(self.order, status='completed')
        self.assertEqual(self.book.observe(changed, now=106), 'awaiting_confirmation')
        self.assertEqual(self.book.observe(changed, now=200), 'awaiting_confirmation')
        self.assertFalse(self.path.exists())

    def test_station_names_separate_same_order_number(self):
        self.agree()
        self.agree(dict(self.order, station='Checkmate'))
        self.assertEqual(len(self.book.snapshot()), 2)

    def test_corrupt_ledger_preserved(self):
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            RefineryOrderBook(self.path)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_nan_amount_and_unknown_quality_rejected(self):
        for quality, amount in ((874, float('nan')), (None, 1), (1001, 1)):
            bad = dict(self.order, parts=[dict(material='Iron', quality=quality, scu=amount)])
            with self.assertRaises(ValueError):
                self.book.observe(bad)


if __name__ == '__main__':
    unittest.main()
