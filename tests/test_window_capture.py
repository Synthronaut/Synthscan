"""Native boundary tests; no windows or game process are opened."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from window_telemetry_capture import WindowTelemetryCapture


class FakeCapture:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.handlers = {}
        self.stopped = False

    def event(self, callback):
        self.handlers[callback.__name__] = callback
        return callback

    def start_free_threaded(self):
        return self

    def is_finished(self):
        return self.stopped

    def stop(self):
        self.stopped = True

    def emit(self, pixels):
        self.handlers["on_frame_arrived"](SimpleNamespace(frame_buffer=pixels,
                                          width=pixels.shape[1], height=pixels.shape[0]), self)


class WindowCaptureTests(unittest.TestCase):
    def setUp(self):
        self.token = "join-1"
        self.source = WindowTelemetryCapture(lambda: self.token, factory=FakeCapture)
        self.source.start(123)
        self.native = self.source.capture
        self.pixels = np.full((500, 1600, 4), 42, dtype=np.uint8)

    def tearDown(self):
        self.source.stop()

    def test_held_frame_keeps_capture_time_and_session(self):
        with patch("window_telemetry_capture.time.time", return_value=100):
            self.native.emit(self.pixels)
        self.token = "join-2"
        image, at, token = self.source.take_latest()
        self.assertEqual((at, token), (100, "join-1"))
        self.assertIsNone(self.source.take_latest())

    def test_native_buffer_is_copied_and_only_corner_is_retained(self):
        self.native.emit(self.pixels)
        self.pixels[:] = 0
        image, _, _ = self.source.take_latest()
        self.assertEqual(image.shape, (420, 1400, 3))
        self.assertTrue(np.all(image == 42))

    def test_old_callbacks_cannot_replace_or_clear_new_capture(self):
        self.source.start(456)
        new = self.source.capture
        new.emit(self.pixels)
        self.native.emit(np.zeros_like(self.pixels))
        self.native.handlers["on_closed"]()
        self.assertIsNotNone(self.source.take_latest())
        self.assertTrue(self.native.stopped)

    def test_close_invalidates_pending_frame(self):
        self.native.emit(self.pixels)
        self.native.handlers["on_closed"]()
        self.assertIsNone(self.source.take_latest())

    def test_callback_throttle_does_not_retimestamp_old_pixels(self):
        with patch("window_telemetry_capture.time.monotonic", side_effect=[100, 100.1]):
            self.native.emit(self.pixels)
            self.token = "join-2"
            self.native.emit(self.pixels)
        self.assertEqual(self.source.take_latest()[2], "join-1")


if __name__ == "__main__":
    unittest.main()
