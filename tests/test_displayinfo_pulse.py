import unittest
from tools.probe_displayinfo_pulse import PulseTrace


class PulseTraceTests(unittest.TestCase):
    def test_single_frame_pulse_has_nonzero_visibility_bracket(self):
        trace = PulseTrace()
        for native, visible in [(0, False), (333333, True), (666666, False)]:
            trace.add(native, native/1e7, visible, .95 if visible else .2)
        summary = trace.summarize()
        burst = summary["bursts"][0]
        self.assertEqual(burst["frames"], 1)
        self.assertEqual(burst["captured_span_ms"], 0)
        self.assertAlmostEqual(burst["first_visible_to_absent_ms"], 33.3333)
        self.assertAlmostEqual(burst["outer_bracket_ms"], 66.6666)
        self.assertTrue(burst["bracketed"])
        self.assertFalse(summary["ended_with_displayinfo_detected"])

    def test_unfinished_pulse_cannot_claim_restore_or_complete_duration(self):
        trace = PulseTrace()
        trace.add(100, 10, True, .95)
        summary = trace.summarize()
        self.assertTrue(summary["ended_with_displayinfo_detected"])
        self.assertFalse(summary["bursts"][0]["bracketed"])
        self.assertIsNone(summary["bursts"][0]["first_visible_to_absent_ms"])


if __name__ == "__main__":
    unittest.main()
