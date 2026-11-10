"""Dedicated real-time memory gauge and protected rapid session recovery.

Manages process commit tracking, two-stage recovery confirmation,
and non-activating click hit-testing for the integrated Server HUD ribbon.
"""
import ctypes
from ctypes import wintypes as w
import logging
import os
from pathlib import Path
import re
import time

from session_recovery import read_game_memory, execute_recovery_async

LOG = logging.getLogger(__name__)

GAUGE_WIDTH_NORMAL = 86
GAUGE_WIDTH_CONFIRM = 138

def memory_button_position(bar, bounds, width=GAUGE_WIDTH_NORMAL):
    """Calculate docked position (retained for test compatibility)."""
    x, y, w, h = bar
    left = x - width - 3
    if left < bounds['left']:
        left = bounds['left']
    top = max(bounds['top'], min(y, bounds['top'] + bounds['height'] - h))
    return int(left), int(top), int(width), int(h)


class MemoryRecoveryButton:
    def __init__(self, root, directory, owner):
        import tkinter as tk
        self.root = root
        self.directory = directory
        self.owner = owner
        self.ribbon = None
        self.visible = False
        self.geometry = None
        self.height = 24
        self.width = GAUGE_WIDTH_NORMAL
        
        # Recovery state
        self.confirm_until = 0.0
        self.status_text = None
        self.pressed = False
        self._countdown_job = None
        self._last_mem_read = 0.0
        self._cached_mem = None

        # Transparent click target window hovering over the RAM pill on the ribbon
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.title('Star Citizen Memory & Recovery')
        self.window.attributes('-topmost', True)

        self.canvas = tk.Canvas(
            self.window, width=self.width, height=self.height,
            bg='#070a0f', highlightthickness=0, bd=0, cursor='hand2'
        )
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<ButtonRelease-1>', self.release)

        self.window.update_idletasks()
        self._native_input()

    def _native_input(self):
        """Set WS_EX_NOACTIVATE and hook mouse messages so clicking never steals focus from the game."""
        api = ctypes.windll.user32
        api.GetParent.argtypes = [w.HWND]
        api.GetParent.restype = w.HWND
        api.GetWindowLongW.argtypes = [w.HWND, ctypes.c_int]
        api.SetWindowLongW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_long]

        self.hwnd = api.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        # WS_EX_TOOLWINDOW (0x80) | WS_EX_NOACTIVATE (0x08000000) | WS_EX_LAYERED (0x80000) & ~WS_EX_TRANSPARENT (0x20)
        style = (api.GetWindowLongW(self.hwnd, -20) | 0x80000 | 0x80 | 0x08000000) & ~0x20
        api.SetWindowLongW(self.hwnd, -20, style)

        api.SetLayeredWindowAttributes.argtypes = [w.HWND, w.DWORD, w.BYTE, w.DWORD]
        api.SetLayeredWindowAttributes(self.hwnd, 0, 255, 2)

        proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        api.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
        api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        api.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]
        api.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        api.CallWindowProcW.argtypes = [ctypes.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        api.CallWindowProcW.restype = ctypes.c_ssize_t
        original = api.GetWindowLongPtrW(self.hwnd, -4)

        @proc_type
        def mouse_proc(handle, message, wp, lp):
            if message == 0x21:  # WM_MOUSEACTIVATE -> MA_NOACTIVATE
                return 3
            return api.CallWindowProcW(original, handle, message, wp, lp)

        self._mouse_proc = mouse_proc
        api.SetWindowLongPtrW(self.hwnd, -4, ctypes.cast(mouse_proc, ctypes.c_void_p).value)

    def get_memory_info(self):
        """Read process memory with 1s cache throttle."""
        now = time.time()
        if now - self._last_mem_read >= 1.0 or self._cached_mem is None:
            self._cached_mem = read_game_memory()
            self._last_mem_read = now
        return self._cached_mem

    def cache_state(self):
        now = time.time()
        mem = self.get_memory_info()
        commit_round = round(mem['commit_gb'], 1) if mem else None
        confirm_rem = max(0, int(self.confirm_until - now)) if self.confirm_until > now else 0
        return (commit_round, confirm_rem, self.status_text)

    def press(self, event):
        self.pressed = True

    def release(self, event):
        if self.pressed:
            self.pressed = False
            self.click(event)

    def click(self, event=None):
        now = time.time()
        if self.status_text:
            return  # Recovery already in progress

        if self.confirm_until > now:
            # 2nd Click confirmed! Execute recovery
            self.confirm_until = 0.0
            self.status_text = "CLEANING EAC..."
            if self._countdown_job:
                self.window.after_cancel(self._countdown_job)
                self._countdown_job = None
            self._notify_ribbon()

            def on_status(msg):
                self.status_text = msg
                if not msg:
                    self.confirm_until = 0.0
                if self.window and self.window.winfo_exists():
                    self.window.after(0, self._notify_ribbon)

            execute_recovery_async(callback=on_status)
        else:
            # 1st Click: Arm 4-second confirmation
            self.confirm_until = now + 4.0
            self.width = GAUGE_WIDTH_CONFIRM
            self._notify_ribbon()
            self._schedule_countdown()

    def _schedule_countdown(self):
        if self._countdown_job:
            self.window.after_cancel(self._countdown_job)
        def tick():
            self._countdown_job = None
            if self.confirm_until > time.time():
                self._notify_ribbon()
                self._schedule_countdown()
            else:
                self.confirm_until = 0.0
                self.width = GAUGE_WIDTH_NORMAL
                self._notify_ribbon()
        self._countdown_job = self.window.after(250, tick)

    def _notify_ribbon(self):
        if self.ribbon:
            self.ribbon._last_rendered_key = None
            self.ribbon.render_bar()

    def paint(self):
        # Native ribbon canvas owns the visual painting via hud_appearance.render_original_bar.
        self._notify_ribbon()

    def follow(self, ribbon, bounds):
        """Position transparent click window exactly over the ribbon's RAM pill."""
        self.ribbon = ribbon
        hit = getattr(ribbon, 'memory_hit', None)
        visible = bool(getattr(ribbon, '_visible', False) and getattr(ribbon, 'enabled', True) and hit)
        self.height = ribbon.BAR_HEIGHT

        if visible:
            match = re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', getattr(ribbon, '_last_geometry', '') or '')
            bar_x = int(match[3]) if match else ribbon.bar_win.winfo_x()
            bar_y = int(match[4]) if match else ribbon.bar_win.winfo_y()

            pill_w = hit['right'] - hit['left']
            pill_h = ribbon.BAR_HEIGHT
            left = bar_x + hit['left']
            top = bar_y
            geometry = (left, top, pill_w, pill_h)
            showing = not self.visible

            if showing:
                self.window.deiconify()

            if geometry != self.geometry or showing:
                x, y, width, height = geometry
                if self.geometry is None or self.geometry[2:] != geometry[2:]:
                    self.window.geometry(f'{width}x{height}')
                    self.canvas.configure(width=width, height=height)
                api = ctypes.windll.user32
                api.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
                api.SetWindowPos(self.hwnd, None, x, y, width, height, 0x14)
                self.geometry = geometry

            if getattr(self, 'opacity', None) != 0.01:
                self.window.attributes('-alpha', 0.01)
                self.opacity = 0.01
        elif self.visible:
            self.window.withdraw()

        self.visible = visible

    def sync(self, ribbon, bounds):
        self.follow(ribbon, bounds)

    def close(self):
        if self._countdown_job:
            self.window.after_cancel(self._countdown_job)
            self._countdown_job = None
        self.window.destroy()
