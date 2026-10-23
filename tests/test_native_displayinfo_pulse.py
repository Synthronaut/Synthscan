from types import SimpleNamespace
import unittest

from tools.test_native_displayinfo import native_pulse


class NativePulseTests(unittest.TestCase):
    def test_only_native_on_and_off_keys_with_post_off_verification(self):
        events = []
        keyboard = SimpleNamespace(key=lambda vk: events.append(("key", vk)),
                                   check=lambda: events.append(("check",)))
        native_pulse(keyboard, lambda visible, after, stable: events.append(("observe", visible, stable)))
        self.assertEqual(events, [("key", 0x7D), ("observe", True, 0), ("check",),
                                  ("key", 0x7E), ("observe", False, .150)])

    def test_failed_on_observation_still_requests_off(self):
        events = []
        keyboard = SimpleNamespace(key=lambda vk: events.append(vk), check=lambda: None)
        def fail(*args):
            raise RuntimeError("On not observed")
        with self.assertRaisesRegex(RuntimeError, "On not observed"):
            native_pulse(keyboard, fail)
        self.assertEqual(events, [0x7D, 0x7E])

    def test_focus_loss_cannot_trigger_input_into_another_app(self):
        events = []
        def lost():
            raise RuntimeError("Focus lost")
        keyboard = SimpleNamespace(key=lambda vk: events.append(vk), check=lost)
        with self.assertRaisesRegex(RuntimeError, "Focus lost"):
            native_pulse(keyboard, lambda *args: None)
        self.assertEqual(events, [0x7D])


if __name__ == "__main__":
    unittest.main()
