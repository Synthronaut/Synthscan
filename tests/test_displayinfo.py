from pathlib import Path
import json
import unittest

import cv2
import numpy as np

from validated_displayinfo import ValidatedDisplayInfoReader, numeric_token

FIXTURES = Path(__file__).parent / "fixtures" / "displayinfo"


class NumericTokenTests(unittest.TestCase):
    def test_scalar_punctuation_and_units(self):
        self.assertEqual(numeric_token("26,6 [23", "fps"), 26.6)
        self.assertEqual(numeric_token("8.4m5r", "ping"), 8.4)
        self.assertEqual(numeric_token("478,", "integer"), 478)
        self.assertEqual(numeric_token("03, r", "node"), 3)

    def test_damaged_or_truncated_tokens_are_not_repaired_into_values(self):
        for text, kind in (("8.77", "fps"), ("8A4ms", "ping"), ("831]", "integer"),
                           ("47B", "integer"), ("03", "node"), ("10.", "fps")):
            with self.subTest(text=text):
                self.assertIsNone(numeric_token(text, kind))


@unittest.skipUnless((FIXTURES/'labels.json').exists(),'Private capture fixtures are not distributed')
class CapturedDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = ValidatedDisplayInfoReader()

    def test_manually_checked_live_frames(self):
        labels = json.loads((FIXTURES / "labels.json").read_text())
        for name, expected in labels.items():
            with self.subTest(frame=name):
                result = self.reader.parse_image(cv2.imread(str(FIXTURES / name)))
                # A rejected/obscured field is allowed to remain unavailable.
                # Every published value must agree with the manually read frame.
                for key, value in expected.items():
                    if result.get(key) not in (None, "--"):
                        self.assertEqual(result[key], value, (name, key, self.reader.last_evidence))
                for key in ("server_fps",):
                    self.assertEqual(result[key], expected[key], (name, key))
                if name == "clear.png":
                    for key, value in expected.items():
                        self.assertEqual(result[key], value)

    def test_blank_game_image_has_no_metrics_and_does_not_load_model(self):
        reader = ValidatedDisplayInfoReader()
        result = reader.parse_image(np.zeros((420, 1400, 3), dtype=np.uint8))
        self.assertIsNone(reader._recognizer)
        self.assertIsNone(result["ping_ms"])
        self.assertIsNone(result["shard_pop"])
        self.assertEqual(result["server_name"], "--")

    def test_disagreeing_recognitions_are_rejected(self):
        def recognize(images):
            self.calls += 1
            return [["470" if self.calls == 1 else "472", .99]], None
        self.calls = 0
        reader = ValidatedDisplayInfoReader(recognizer=recognize)
        self.assertIsNone(reader._number(np.zeros((30, 50, 3), dtype=np.uint8),
                                       (1, 3, 25), "integer", "shard_pop"))

    def test_dim_short_pulse_recovers_both_populations_and_server_fps(self):
        for name, shard, local in [("pulse_dim.png", 38, 5), ("pulse_bright.png", 29, 4),
                                   ("pulse_short.png", 29, 4)]:
            with self.subTest(frame=name):
                result = self.reader.parse_image(cv2.imread(str(FIXTURES / name)))
                self.assertEqual(result["server_fps"], 30.0)
                self.assertEqual(result["shard_pop"], shard)
                self.assertEqual(result["srv_pop"], local)

    def test_population_clause_requires_labels_bracket_and_agreement(self):
        frame = np.zeros((120, 1400, 3), dtype=np.uint8)
        for texts, expected in [(["shard 38, 5rv 5]", "shard 38, srv 5]"], (38, 5)),
                                (["shard 38, srv 51", "shard 38, srv 51"], None),
                                (["shard 38, srv 5]", "shard 38, srv 6]"], None),
                                (["shard 38, srv 50]", "shard 38, srv 50]"], None),
                                (["shard 3B, srv 5]", "shard 3B, srv 5]"], None)]:
            results = iter(texts)
            reader = ValidatedDisplayInfoReader(recognizer=lambda images: ([[next(results), .99]], None))
            with self.subTest(texts=texts):
                self.assertEqual(reader._population_clause(frame, (1289, 97, 1321)), expected)


if __name__ == "__main__":
    unittest.main()
