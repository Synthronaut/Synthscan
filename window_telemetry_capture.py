"""Window-surface capture for diagnostics. Requires rendered DisplayInfo text.

No game input, memory inspection, file changes, or graphics hooks. Latest-only
frames retain their capture timestamp and session token; polling never makes a
held frame fresh. The native callback never calls Tk or performs recognition.
"""
import ctypes
from ctypes import wintypes
import threading
import time


def game_window_handle():
    user = ctypes.windll.user32
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.IsIconic.argtypes = [wintypes.HWND]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    hwnd = user.FindWindowW("CryENGINE", None)
    if not hwnd or user.IsIconic(hwnd) or not user.IsWindowVisible(hwnd):
        return None
    title = ctypes.create_unicode_buffer(256)
    user.GetWindowTextW(hwnd, title, len(title))
    return int(hwnd) if title.value.strip().lower() == "star citizen" else None


class WindowTelemetryCapture:
    def __init__(self, get_session_token, interval=.75, factory=None):
        self.get_session_token = get_session_token
        self.interval = max(.5, float(interval))
        self.factory = factory
        self.hwnd = None
        self.controller = None
        self.capture = None
        self._lock = threading.Lock()
        self._latest = None
        self._last_frame = 0
        self._generation = 0

    def start(self, hwnd):
        self.stop()
        if self.factory is None:
            from windows_capture import WindowsCapture
            self.factory = WindowsCapture
        generation = self._generation
        self._last_frame = 0
        self.capture = self.factory(window_hwnd=hwnd, cursor_capture=False, draw_border=False,
                                    minimum_update_interval=int(self.interval*1000))

        @self.capture.event
        def on_frame_arrived(frame, control):
            now = time.monotonic()
            if generation != self._generation or now-self._last_frame < self.interval:
                return
            at, token = time.time(), self.get_session_token()
            self._last_frame = now
            crop = frame.frame_buffer[:min(420, frame.height), max(0, frame.width-1400):, :3].copy()
            with self._lock:
                if generation == self._generation:
                    self._latest = (crop, at, token)

        @self.capture.event
        def on_closed():
            with self._lock:
                if generation == self._generation:
                    self._latest = None

        self.controller = self.capture.start_free_threaded()
        self.hwnd = hwnd

    def take_latest(self):
        with self._lock:
            latest, self._latest = self._latest, None
        return latest

    @property
    def finished(self):
        return self.controller is not None and self.controller.is_finished()

    def stop(self):
        # Invalidate callbacks before stopping; an old close event cannot clear
        # the next session's frame, even if the native callback finishes late.
        self._generation += 1
        controller, self.controller = self.controller, None
        self.hwnd = None
        try:
            if controller:
                controller.stop()
        finally:
            self.capture = None
            with self._lock:
                self._latest = None
