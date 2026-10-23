import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from detector import SignatureDetector, read_signature_candidates
from radar_db import MINERAL_SIGNATURES, SPECIAL_SIGNATURES, parse_signature, signature_candidates, match_summary


class MiningSignatureTests(unittest.TestCase):
    def test_known_mineral_examples(self):
        for value, name, count in [(6370, "Stileron", 2), (8600, "Ice", 2), (15420, "Titanium", 4),
                                   (21350, "Iron", 5), (3170, "Quantainium", 1)]:
            with self.subTest(value=value):
                match = parse_signature(value)
                self.assertIsNotNone(match)
                self.assertIn((name, count), [(row["name"], row["count"]) for row in match["candidates"]])

    def test_every_source_cluster_resolves_and_caps_are_respected(self):
        self.assertEqual(len(MINERAL_SIGNATURES), 26)
        self.assertEqual(len(SPECIAL_SIGNATURES), 3)
        for ore in MINERAL_SIGNATURES:
            for count in range(1, ore["max_count"] + 1):
                rows = signature_candidates(ore["base_rs"] * count)
                self.assertIn((ore["name"], count), [(r["name"], r["count"]) for r in rows])
            over = signature_candidates(ore["base_rs"] * (ore["max_count"] + 1))
            self.assertNotIn(ore["name"], [r["name"] for r in over])

    def test_ambiguous_ground_fields_are_not_presented_as_one_resource(self):
        match = parse_signature(12000)
        self.assertTrue(match["ambiguous"])
        self.assertIsNone(match["base_rs"])
        self.assertIsNone(match["count"])
        self.assertEqual({r["category"] for r in match["candidates"]}, {"roc", "hand", "salvage"})
        self.assertNotIn("100%", match_summary(match))
        self.assertEqual(len(signature_candidates(12000, environment="space")), 1)
        self.assertIn("ore unknown", next(x for x in __import__('radar_db').reference_groups()[-1][1] if x[2] == 4000)[0])

    def test_system_filter_is_explicit_not_inferred_from_server_region(self):
        self.assertTrue(signature_candidates(6370, system="PYRO"))
        self.assertFalse(signature_candidates(6370, system="STANTON"))
        with self.assertRaises(ValueError):
            signature_candidates(6370, system="ASIA")

    def test_obsolete_and_nearby_numbers_are_not_repaired(self):
        for value in [1700, 5100, 620, 1240, 7700, 6369, 270000, True, 3170.0, "3170"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_signature(value, tolerance=100))
        self.assertTrue(parse_signature(123000))  # Hand-mining field x41.


class MiningOCRGuardTests(unittest.TestCase):
    def read(self, text, score=.96):
        return read_signature_candidates([([[0, 0], [80, 0], [80, 20], [0, 20]], text, score)])

    def test_whole_row_and_literal_separators_only(self):
        for text in ["6370", "6,370", "RS: 6,370", "123,000"]:
            self.assertTrue(self.read(text), text)
        for text in ["RANGE 6370", "6370m", "6.370", "6,37,0", "FPS 3170", "317O", "3170 SCU", "6370"]:
            score = .4 if text == "6370" else .96
            self.assertFalse(self.read(text, score), text)

    def test_two_consecutive_frames_required_and_multiple_numbers_rejected(self):
        detector = SignatureDetector.__new__(SignatureDetector)
        detector.require_game_focus = False
        detector.monitor_rect = {}
        detector._pending_sig = None
        detector._pending_count = 0
        detector._pending_at = 0
        import threading
        detector._ocr_lock = threading.Lock()
        detector._grab_rect_pil = lambda rect: Image.new("RGB", (100, 100), "black")
        rows = [[None, "6370", .96]]
        detector._get_ocr = lambda: lambda *args, **kwargs: (rows, None)
        with patch.object(cv2, "countNonZero", return_value=500):
            self.assertIsNone(detector.scan_screen()[0])
            match, number, _ = detector.scan_screen()
            self.assertEqual(number, 6370)
            self.assertEqual(match["ocr_confidence"], .96)
            rows.append([None, "8600", .99])
            self.assertIsNone(detector.scan_screen()[0])
            rows.pop()
            self.assertIsNone(detector.scan_screen()[0])


if __name__ == "__main__":
    unittest.main()
