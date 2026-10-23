"""Quantity semantics with controlled OCR, without changing the real inventory."""
import unittest
from unittest.mock import patch

import numpy as np
from refinery_db import parse_refinery_image


def text(value, left=100):
    return [[[left, 100], [left + 90, 100], [left + 90, 120], [left, 120]], value, 0.99]


class RefineryUnitTests(unittest.TestCase):
    def parse(self, amount, *extra):
        result = [text("Tungsten", 10), text(amount, 180), *extra]
        with patch("refinery_db.get_ocr", return_value=lambda frame: (result, None)):
            return parse_refinery_image(np.zeros((300, 500, 3), dtype=np.uint8))

    def test_explicit_scu_is_not_divided_by_one_hundred(self):
        self.assertEqual(self.parse("750 SCU")["Tungsten"], 750)

    def test_explicit_centiscu_is_converted(self):
        self.assertEqual(self.parse("850 cSCU")["Tungsten"], 8.5)

    def test_quality_column_does_not_replace_quantity(self):
        parsed = self.parse("750 SCU", text("Quality: 910", 320))
        self.assertEqual(parsed["Tungsten"], 750)
        self.assertEqual(parsed.qualities["Tungsten"], 910)

    def test_percentage_is_not_added_as_an_ore_quantity(self):
        self.assertEqual(self.parse("85%"), {})
