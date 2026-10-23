"""User-started, finite DisplayInfo keyboard experiment.

Opening this window sends no game input. The user must explicitly start one
trial with an empty game console OPEN and leave controls idle. At the end of
the countdown the tester can hand focus from its own window to the game.
Uses ordinary Windows scan-code keyboard events, no game hooks or memory access.
The separate read-only capture probe measures the resulting visible interval.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from telemetry_ipc import read_shared_json
from telemetry_ipc import publish_json
from window_telemetry_capture import game_window_handle

BUILD = "pulse-keyboard-5"
MARKER_CACHE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData"/"Local")))/"SynthScan"/"cache"/"console_marker.json"
PROFILES = {"Baseline": (.060, .012, .012), "Fast": (.040, .003, .003),
            "Shortest": (.020, .001, .002), "Minimum": (.005, .001, .001),
            "Burst": (.040, 0, 0)}


class Cancelled(RuntimeError):
    pass


class ConsoleNotVerified(RuntimeError):
    pass


class ConsoleFrames:
    """Own copied window frames; never desktop pixels or an input hook."""
    def __init__(self, hwnd):
        from windows_capture import WindowsCapture
        self.lock = threading.Lock()
        self.latest = None
        self.capture = WindowsCapture(window_hwnd=hwnd, cursor_capture=False,
                                      draw_border=False, minimum_update_interval=0)

        @self.capture.event
        def on_frame_arrived(frame, control):
            image = frame.frame_buffer[:min(720, frame.height//2), :min(1000, frame.width), :3].copy()
            with self.lock:
                self.latest = (time.time(), image)

        @self.capture.event
        def on_closed():
            with self.lock:
                self.latest = None

        self.controller = self.capture.start_free_threaded()

    def take(self):
        with self.lock:
            item = self.latest
        if item is None or time.time()-item[0] > .5:
            raise RuntimeError("No fresh console-check frame; input stopped")
        return item

    def stop(self):
        self.controller.stop()


class ConsoleGuard:
    """Calibrate a log-prefix template from OCR once, then use fast matching.

    This bounded experiment expects a populated console, as currently observed.
    Ambiguous classifications abort; they never authorize typing into gameplay.
    """
    def __init__(self, frames):
        import cv2
        from rapidocr_onnxruntime import RapidOCR
        self.cv2, self.frames = cv2, frames
        _, image = frames.take()
        try:
            import numpy as np
            cache = read_shared_json(MARKER_CACHE, limit=131072)
            marker = np.asarray(cache["template"], dtype=np.float32)
            if (cache["version"] == 1 and cache["frame_shape"] == list(image.shape[:2])
                    and marker.ndim == 2 and 7 <= marker.shape[0] <= 40
                    and 24 <= marker.shape[1] <= 100 and np.isfinite(marker).all()
                    and marker.std() > 1):
                self.template = marker
                if self.classify(image) is True:
                    return
                raise ConsoleNotVerified("Cached console marker is absent; no command typed")
        except ConsoleNotVerified:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            pass
        engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1,
                          use_text_det=True, use_text_rec=True, use_angle_cls=False)
        results, _ = engine(cv2.resize(image, None, fx=2, fy=2))
        candidates = []
        for box, text, confidence in results or []:
            if float(confidence) < .65 or not re.match(r"^\s*\[\s*(Notice|Error|Warning|Info)\s*\]", text, re.I):
                continue
            x = max(0, int(min(p[0] for p in box)/2))
            y = max(0, int(min(p[1] for p in box)/2)-1)
            bottom = min(image.shape[0], int(max(p[1] for p in box)/2)+2)
            if x < 50 and bottom-y >= 7:
                candidates.append(image[y:bottom, x:x+48])
        if len(candidates) < 3:
            raise ConsoleNotVerified("Cannot verify an open, populated game console; no command typed")
        self.template = cv2.cvtColor(candidates[0], cv2.COLOR_BGR2GRAY).astype("float32")
        if self.classify(image) is not True:
            raise ConsoleNotVerified("Console marker calibration was ambiguous; no command typed")
        publish_json(MARKER_CACHE, {"version": 1, "frame_shape": list(image.shape[:2]),
                                    "template": self.template.tolist()})

    def classify(self, image):
        cv2 = self.cv2
        gray = cv2.cvtColor(image[:, :150], cv2.COLOR_BGR2GRAY).astype("float32")
        scores = cv2.matchTemplate(gray, self.template, cv2.TM_CCOEFF_NORMED)
        maximum = cv2.minMaxLoc(scores)[1]
        if maximum < .70:
            return False
        matches = 0
        for _ in range(3):
            _, score, _, (_, y) = cv2.minMaxLoc(scores)
            if score < .82:
                break
            matches += 1
            scores[max(0, y-self.template.shape[0]):y+self.template.shape[0]+1] = -1
        return True if matches >= 2 else None

    def wait(self, opened, keyboard, after=0, timeout=1.5):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            keyboard.check()
            at, image = self.frames.take()
            if at >= after and self.classify(image) is opened:
                return at
            time.sleep(.01)
        raise RuntimeError(f"Cannot verify console {'open' if opened else 'closed'}; input stopped")


class Keyboard:
    """Foreground-only scan codes with explicit key hold/release durations."""
    def __init__(self, hwnd, hold=.060, char_hold=.012, gap=.012):
        self.hwnd, self.hold, self.char_hold = hwnd, hold, char_hold
        self.gap = gap
        self.burst = False
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user.SetForegroundWindow.restype = wintypes.BOOL
        self.user.GetKeyboardLayout.argtypes = [wintypes.DWORD]
        self.user.GetKeyboardLayout.restype = wintypes.HANDLE
        self.user.VkKeyScanExW.argtypes = [wintypes.WCHAR, wintypes.HANDLE]
        self.user.VkKeyScanExW.restype = ctypes.c_short
        self.user.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HANDLE]
        self.user.MapVirtualKeyExW.restype = wintypes.UINT
        thread = self.user.GetWindowThreadProcessId(hwnd, None)
        self.layout = self.user.GetKeyboardLayout(thread)

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class Payload(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("data",)
            _fields_ = [("type", wintypes.DWORD), ("data", Payload)]

        self.Input, self.KeyInput = INPUT, KEYBDINPUT
        self.user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.user.SendInput.restype = wintypes.UINT

    def check(self):
        if self.user.GetForegroundWindow() != self.hwnd:
            raise Cancelled("Game lost focus. Input stopped.")
        if self.user.GetAsyncKeyState(0x1B) & 0x8000:
            raise Cancelled("Escape pressed. Input stopped.")

    def foreground_details(self):
        foreground = self.user.GetForegroundWindow()
        process = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(foreground, ctypes.byref(process))
        return {"hwnd": foreground, "pid": process.value,
                "is_game": foreground == self.hwnd}

    def handoff_from_tester(self):
        """Only a focused tester may initiate the user-requested activation."""
        before = self.foreground_details()
        if not before["is_game"]:
            if before["pid"] != os.getpid():
                raise Cancelled("Another app has focus. Keep the tester focused after clicking Start.")
            self.user.SetForegroundWindow(self.hwnd)
            deadline = time.monotonic()+1
            while self.user.GetForegroundWindow() != self.hwnd and time.monotonic() < deadline:
                time.sleep(.02)
        self.check()
        return {"before": before, "after": self.foreground_details()}

    def event(self, scan, up=False):
        entry = self.Input(type=1, ki=self.KeyInput(0, scan, 0x0008 | (0x0002 if up else 0), 0, 0))
        if self.user.SendInput(1, ctypes.byref(entry), ctypes.sizeof(entry)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    def text_burst(self, value):
        """Queue ordinary scan-code text in one Windows input call.

        The subsequent Enter still uses a measured hold. No Unicode injection,
        clipboard, game-process calls, or direct console execution is involved.
        """
        self.check()
        entries = []
        scans = set()

        def add(scan, up=False):
            entries.append(self.Input(type=1, ki=self.KeyInput(0, scan, 0x0008 | (0x0002 if up else 0), 0, 0)))
            scans.add(scan)

        for char in value:
            mapping = self.user.VkKeyScanExW(char, self.layout)
            if mapping == -1 or (mapping >> 8) & ~1:
                raise RuntimeError("The active keyboard layout cannot type this command safely")
            scan = self.user.MapVirtualKeyExW(mapping & 255, 0, self.layout)
            if not scan:
                raise RuntimeError("Missing command scan code")
            shift = bool((mapping >> 8) & 1)
            if shift:
                add(0x2A)
            add(scan)
            add(scan, True)
            if shift:
                add(0x2A, True)
        array = (self.Input*len(entries))(*entries)
        if self.user.SendInput(len(entries), array, ctypes.sizeof(self.Input)) != len(entries):
            for scan in scans:
                self.event(scan, up=True)
            raise RuntimeError("Windows did not accept the complete text sequence")
        self.check()

    def key(self, vk, hold=None):
        self.check()
        scan = self.user.MapVirtualKeyExW(vk, 0, self.layout)
        if not scan:
            raise RuntimeError(f"No scan code for key {vk}")
        self.event(scan)
        try:
            time.sleep(self.hold if hold is None else hold)
        finally:
            self.event(scan, up=True)
        time.sleep(self.gap)
        self.check()

    def text(self, value):
        for char in value:
            mapping = self.user.VkKeyScanExW(char, self.layout)
            if mapping == -1 or (mapping >> 8) & ~1:
                raise RuntimeError("The active keyboard layout cannot type this command safely")
            shift = bool((mapping >> 8) & 1)
            if shift:
                self.check()
                self.event(0x2A)
                time.sleep(self.gap)
            try:
                self.key(mapping & 255, self.char_hold)
            finally:
                if shift:
                    self.event(0x2A, up=True)

    def command(self, enabled):
        text = f"r_displayinfo {1 if enabled else 0}"
        self.text_burst(text) if self.burst else self.text(text)
        self.key(0x0D)

    def clear_own_console_input(self):
        # Recovery may follow an ignored Enter, leaving our <=15-character
        # command in the input line. Console visibility must be verified first.
        for _ in range(32):
            self.key(0x08, hold=.060)


def read_status(output):
    try:
        value = read_shared_json(output.with_suffix(".status.json"))
        frame = value["frame"]
        if time.time()-frame["at"] > .5:
            return None
        return frame
    except (OSError, ValueError, KeyError, TypeError):
        return None


def wait_visibility(output, visible, seconds, keyboard, after=0, stable_for=0):
    deadline = time.monotonic()+seconds
    first_at = None
    count = 0
    last_at = None
    while time.monotonic() < deadline:
        keyboard.check()
        frame = read_status(output)
        if frame and frame["at"] >= after and frame["at"] != last_at:
            last_at = frame["at"]
            if frame["visible"] == visible:
                first_at = frame["at"] if first_at is None else first_at
                count += 1
                if not stable_for or count >= 3 and frame["at"]-first_at >= stable_for:
                    return frame
            else:
                first_at, count = None, 0
        time.sleep(.01)
    raise RuntimeError(f"Capture did not confirm DisplayInfo {'on' if visible else 'off'}")


class Tester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"SynthScan — one DisplayInfo pulse test [{BUILD}]")
        self.root.geometry("660x440")
        self.running = False
        self.message = tk.StringVar(value=f"{BUILD}: ready. No game input has been sent.")
        ttk.Label(self.root, text="ONE PULSE TEST", font=("Segoe UI", 16, "bold")).pack(pady=(18, 10))
        instructions = ("1. Park safely. If the game console is open, clear its input line.\n"
                        "2. Choose a timing below. The game will come forward in 8 seconds.\n"
                        "3. Leave controls alone until the result. First calibration can take 30 sec.\n\n"
                        "The test uses normal keyboard commands. Both the console and the\n"
                        "DisplayInfo panel will flash. This first trial does not promise invisibility.\n"
                        "Escape or switching away from the game stops input.\n"
                        "If interrupted, restore r_DisplayInfo 0 yourself and close the console.")
        ttk.Label(self.root, text=instructions, justify="left", wraplength=620).pack(padx=20)
        row = ttk.Frame(self.root)
        row.pack(pady=18)
        self.buttons = []
        for profile, timing in PROFILES.items():
            button = ttk.Button(row, text=f"{profile} {int(timing[0]*1000)} ms",
                                command=lambda name=profile: self.start(name))
            button.pack(side="left", padx=5)
            self.buttons.append(button)
        ttk.Label(self.root, textvariable=self.message, wraplength=620, justify="left").pack(padx=20)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def show(self, message):
        self.root.after(0, self.message.set, message)

    def close(self):
        if self.running:
            self.show("Test is running. Switch away from the game to stop input; restore r_DisplayInfo 0 manually if needed.")
        else:
            self.root.destroy()

    def start(self, profile):
        if self.running:
            return
        self.running = True
        for button in self.buttons:
            button.configure(state="disabled")
        threading.Thread(target=self.run, args=(profile,), daemon=True).start()

    def run(self, profile):
        report = {"build": BUILD, "profile": profile, "key_timing_seconds": PROFILES[profile],
                  "text_method": "scan_code_burst" if profile == "Burst" else "per_key",
                  "started_at": time.time(), "outcome": "failed", "events": [],
                  "initial_state_required": "parked safely; console input empty; DisplayInfo off"}
        output = ROOT/"research"/f"pulse_keyboard_{time.time_ns()}"
        process = None
        keyboard = None
        console_frames = None
        guard = None
        console_open = None
        may_be_enabled = False
        completed = False
        stage = "prepare_capture"
        try:
            hwnd = game_window_handle()
            if not hwnd:
                raise RuntimeError("Star Citizen must be open and not minimized")
            keyboard = Keyboard(hwnd)
            console_frames = ConsoleFrames(hwnd)
            process = subprocess.Popen([sys.executable, "-B", str(ROOT/"tools"/"probe_displayinfo_pulse.py"),
                                        "--seconds", "60", "--publish-status", "--output", str(output)],
                                       cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            stage = "countdown"
            for remaining in range(8, 0, -1):
                self.show(f"Starts in {remaining} seconds. Keep this tester focused; the game will come forward automatically.")
                time.sleep(1)
            stage = "focus_handoff"
            report["focus_handoff"] = keyboard.handoff_from_tester()
            frame = read_status(output)
            if not frame:
                raise RuntimeError("Fast capture is not ready; no input sent")
            if frame["visible"]:
                raise RuntimeError("DisplayInfo is already detected; turn it off before retrying")
            for vk in (0x10, 0x11, 0x12):
                if keyboard.user.GetAsyncKeyState(vk) & 0x8000:
                    raise Cancelled("Release Shift/Ctrl/Alt before starting")
            self.show("Checking the game console. Leave controls alone.")
            stage = "console_preflight"
            try:
                guard = ConsoleGuard(console_frames)
            except ConsoleNotVerified:
                keyboard.key(0xC0)
                report["events"].append({"event": "console_key_attempt", "at": time.time()})
                time.sleep(.1)
                guard = ConsoleGuard(console_frames)
            guard.wait(True, keyboard)
            console_open = True
            report["events"].append({"event": "initial_console_confirmed_open", "at": time.time()})
            self.show("Running one pulse. Leave the game focused.")
            keyboard.hold, keyboard.char_hold, keyboard.gap = PROFILES[profile]
            keyboard.burst = profile == "Burst"
            stage = "enable_panel"
            may_be_enabled = True
            keyboard.command(True)
            report["events"].append({"event": "on_enter_released", "at": time.time()})
            keyboard.key(0xC0)
            console_open = False
            stage = "confirm_console_closed"
            guard.wait(False, keyboard, after=time.time())
            report["events"].append({"event": "console_closed_with_panel", "at": time.time()})
            on_frame = wait_visibility(output, True, 2, keyboard)
            report["events"].append({"event": "captured_panel", "at": on_frame["at"]})
            # Recognition runs later. Restore as soon as the capture confirms a frame.
            stage = "disable_panel"
            keyboard.key(0xC0)
            console_open = True
            guard.wait(True, keyboard, after=time.time())
            report["events"].append({"event": "console_reopened", "at": time.time()})
            keyboard.command(False)
            off_at = time.time()
            report["events"].append({"event": "off_enter_released", "at": off_at})
            keyboard.key(0xC0)
            console_open = False
            guard.wait(False, keyboard, after=time.time())
            closed_at = time.time()
            report["events"].append({"event": "final_console_closed", "at": closed_at})
            wait_visibility(output, False, 2, keyboard, after=closed_at, stable_for=.15)
            may_be_enabled = False
            completed = True
            report["outcome"] = "panel_on_and_off_confirmed"
        except Exception as exc:
            report["error"] = str(exc)
            report["failed_stage"] = stage
            if keyboard:
                report["foreground_at_failure"] = keyboard.foreground_details()
            # Never redirect input back into the game after focus loss/cancellation.
            if keyboard and may_be_enabled and not isinstance(exc, Cancelled):
                try:
                    keyboard.hold, keyboard.char_hold, keyboard.gap = (.080, .012, .012)
                    keyboard.burst = False
                    keyboard.check()
                    # Observe actual console state before any recovery keystroke.
                    _, console_image = console_frames.take()
                    console_open = guard.classify(console_image) if guard else None
                    if console_open is None:
                        raise RuntimeError("Console state unknown; restore manually")
                    if console_open is False:
                        keyboard.key(0xC0)
                        console_open = True
                        guard.wait(True, keyboard, after=time.time())
                    keyboard.clear_own_console_input()
                    keyboard.command(False)
                    off_at = time.time()
                    keyboard.key(0xC0)
                    console_open = False
                    guard.wait(False, keyboard, after=time.time())
                    wait_visibility(output, False, 2, keyboard, after=time.time(), stable_for=.15)
                    may_be_enabled = False
                    report["cleanup"] = "off confirmed"
                except Exception as cleanup_exc:
                    report["cleanup_error"] = str(cleanup_exc)
        finally:
            if console_frames:
                console_frames.stop()
            output.with_suffix(".stop").touch()
            if process:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    # This is only our read-only capture child, never the game.
                    process.terminate()
                    report["capture_error"] = "Capture child did not finish in time"
            report["ended_at"] = time.time()
            report["manual_restore_may_be_needed"] = may_be_enabled
            report["console_expected_open"] = console_open
            event_times = {event["event"]: event["at"] for event in report["events"]}
            if "off_enter_released" in event_times and "on_enter_released" in event_times:
                report["on_to_off_command_interval_ms"] = 1000*(event_times["off_enter_released"]-event_times["on_enter_released"])
            if "initial_console_confirmed_open" in event_times and "final_console_closed" in event_times:
                report["initial_open_to_final_close_ms"] = 1000*(event_times["final_console_closed"]-event_times["initial_console_confirmed_open"])
            try:
                capture_report = json.loads(output.with_suffix(".json").read_text())
                report["capture"] = {k: v for k, v in capture_report.items() if k != "timeline"}
            except (OSError, ValueError):
                report["capture_error"] = "No completed capture report"
            readable = [sample["values"] for burst in report.get("capture", {}).get("bursts", [])
                        for sample in burst.get("samples", [])
                        if all(sample["values"].get(k) is not None for k in ("server_fps", "srv_pop", "shard_pop"))]
            report["readable_snapshot_count"] = len(readable)
            if completed:
                report["outcome"] = "snapshot_captured_and_off_confirmed" if readable else "pulse_completed_no_usable_reading"
            path = output.with_suffix(".macro.json")
            path.write_text(json.dumps(report, indent=2))
            if completed:
                if readable:
                    v = readable[0]
                    self.show(f"{profile}: captured server FPS {v['server_fps']}, server pop {v['srv_pop']}, "
                              f"shard pop {v['shard_pop']}. DisplayInfo off confirmed. Results: {path.name}")
                else:
                    self.show(f"{profile}: panel switched off, but no complete readable snapshot. Results: {path.name}")
            else:
                self.show(f"Test stopped: {report.get('error', 'unknown error')}. "
                          f"{'Restore r_DisplayInfo 0 manually and close the console. ' if may_be_enabled else ''}"
                          f"Results: {path.name}")
            self.running = False
            self.root.after(0, lambda: [button.configure(state="normal") for button in self.buttons])


if __name__ == "__main__":
    Tester().root.mainloop()
