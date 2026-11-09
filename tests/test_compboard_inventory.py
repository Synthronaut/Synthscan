import json
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from compboard_inventory import CompboardInventory, read_inventory, valid_counts, FILENAME, StaleInventoryError
from executive_hangar_hud import hangar_svg


class CompboardInventoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.repository = CompboardInventory(self.directory)
        self.addCleanup(self.repository.close)

    def seed(self, counts):
        return self.repository.set_counts(counts, self.repository.view()['revision'])

    def test_claim_consumes_exactly_one_of_all_seven_and_keeps_duplicates(self):
        state = self.seed([2, 3, 1, 5, 2, 1, 4])
        used = self.repository.use_set(state['revision'])
        self.assertEqual(used['counts'], [1, 2, 0, 4, 1, 0, 3])
        self.assertEqual(used['total'], state['total']-7)
        self.assertEqual(used['complete_sets'], 0)
        self.assertEqual(read_inventory(self.directory)['counts'], used['counts'])

    def test_incomplete_set_never_partially_consumes_boards(self):
        for missing in range(7):
            counts = [3]*7;counts[missing] = 0;before = self.seed(counts)
            with self.assertRaises(ValueError):self.repository.use_set(before['revision'])
            self.assertEqual(self.repository.view(), before)

    def test_ready_sets_are_the_smallest_board_quantity(self):
        state = self.seed([4, 2, 3, 8, 7, 6, 5])
        self.assertEqual(state['complete_sets'], 2)
        first = self.repository.use_set(state['revision'])
        second = self.repository.use_set(first['revision'])
        self.assertEqual(second['complete_sets'], 0)
        self.assertEqual(second['counts'], [2, 0, 1, 6, 5, 4, 3])

    def test_counts_and_undo_survive_reopening(self):
        state = self.seed([2]*7);self.repository.use_set(state['revision'])
        other = CompboardInventory(self.directory)
        try:
            state = other.view();self.assertEqual(state['counts'], [1]*7)
            restored = other.undo_set(state['revision']);self.assertEqual(restored['counts'], [2]*7)
            self.assertFalse(restored['can_undo'])
            with self.assertRaises(ValueError):other.undo_set(restored['revision'])
        finally:other.close()

    def test_edits_clear_undo_while_noop_save_preserves_it(self):
        state = self.seed([2]*7);used = self.repository.use_set(state['revision'])
        saved = self.repository.set_counts(used['counts'], used['revision'])
        self.assertTrue(saved['can_undo']);self.assertEqual(saved['revision'], used['revision'])
        edited = self.repository.set_counts([4]*7, saved['revision'])
        self.assertFalse(edited['can_undo'])
        with self.assertRaises(ValueError):self.repository.undo_set(edited['revision'])

    def test_stale_windows_cannot_overwrite_or_consume_newer_counts(self):
        old = self.repository.view();state = self.seed([2]*7)
        for operation in [lambda: self.repository.set_counts([5]*7, old['revision']), lambda: self.repository.use_set(old['revision'])]:
            with self.assertRaises(StaleInventoryError):operation()
        self.assertEqual(self.repository.view(), state)

    def test_invalid_counts_do_not_change_saved_inventory(self):
        original = self.seed([2]*7)
        for counts in [[0]*6, [0]*8, [True]*7, [-1]*7, [10000]*7, [1.5]*7, ['3']*7]:
            with self.subTest(counts=counts),self.assertRaises(ValueError):self.repository.set_counts(counts, original['revision'])
        self.assertEqual(self.repository.view(), original)

    def test_readonly_hud_does_not_create_a_profile_database(self):
        other = self.directory/'other'
        self.assertEqual(read_inventory(other)['counts'], [0]*7)
        self.assertFalse(other.exists())

    def test_separate_profiles_have_independent_counts(self):
        self.seed([9]*7)
        with tempfile.TemporaryDirectory() as directory:
            other = CompboardInventory(directory)
            try:self.assertEqual(other.view()['counts'], [0]*7)
            finally:other.close()

    def test_corruption_is_reported_instead_of_replaced_by_zeroes(self):
        self.repository.db.execute('UPDATE board_inventory SET counts=?', ('[1,2]',))
        with self.assertRaises(ValueError):read_inventory(self.directory)
        with self.assertRaises(ValueError):CompboardInventory(self.directory)
        self.assertEqual(self.repository.db.execute('SELECT counts FROM board_inventory').fetchone()[0], '[1,2]')

    def test_failed_write_rolls_back_every_count(self):
        before = self.seed([2]*7)
        self.repository.db.execute('PRAGMA query_only=ON')
        try:
            with self.assertRaises(sqlite3.Error):self.repository.use_set(before['revision'])
        finally:self.repository.db.execute('PRAGMA query_only=OFF')
        self.assertEqual(self.repository.view(), before)

    def test_hud_shows_counts_sets_and_retains_exactly_five_lights(self):
        svg = hangar_svg(None, dict(counts=[2, 1, 5, 3, 4, 9, 7]))
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall('{http://www.w3.org/2000/svg}circle')), 5)
        for value in ['1:2', '2:1', '7:7', '1 set']:self.assertIn(value, svg)
        bad = hangar_svg(None, dict(unavailable=True))
        self.assertIn('Board counts unavailable', bad);self.assertNotIn('1:0', bad)
