"""User-started test of native F14/F15 bindings; never opens or types in console."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from native_displayinfo_bindings import sha256_file
from test_displayinfo_keyboard import Keyboard, wait_visibility
from window_telemetry_capture import game_window_handle

GAME = Path(r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE")


def native_pulse(keyboard, wait):
    """Only F14 then F15, with the Off request attempted after any On request."""
    attempted = False
    try:
        attempted = True
        on_at = time.time()
        keyboard.key(0x7D)  # F14. No text, Enter or console hotkey.
        wait(True, on_at, 0)
    finally:
        if attempted:
            keyboard.check()  # Never redirect keys after Escape or focus loss.
            off_at = time.time()
            keyboard.key(0x7E)  # F15.
    wait(False, off_at, .150)


class Tester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SynthScan — native DisplayInfo binding test")
        self.root.geometry("600x280")
        self.status = tk.StringVar(value=(
            "Experimental: install the native test profile with Star Citizen closed, then relaunch.\n\n"
            "Test sends F14 (On) and F15 (Off). It never opens the console or types commands.\n"
            "Each click runs once. Automatic sampling is disabled."))
        ttk.Label(self.root, textvariable=self.status, wraplength=560).pack(padx=18, pady=20)
        self.test_button = ttk.Button(self.root, text="Test one native pulse", command=lambda: self.start(False))
        self.test_button.pack(pady=5)
        self.off_button = ttk.Button(self.root, text="Request DisplayInfo Off (F15)", command=lambda: self.start(True))
        self.off_button.pack(pady=5)
        self.running = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        if self.running:
            self.show("Wait for the finite test to stop. Escape in the game cancels input.")
        else:
            self.root.destroy()

    def show(self, message):
        self.root.after(0, self.status.set, message)

    def start(self, off_only):
        if self.running:
            return
        self.running = True
        self.test_button.config(state="disabled")
        self.off_button.config(state="disabled")
        threading.Thread(target=self.run, args=(off_only,), daemon=True).start()

    def finish(self):
        self.running = False
        self.test_button.config(state="normal")
        self.off_button.config(state="normal")

    def run(self, off_only):
        child = None
        output = ROOT / "research" / "native_displayinfo" / f"trial_{time.time_ns()}"
        report = {"mode": "off_request" if off_only else "one_native_pulse", "console_input": False,
                  "started_at": time.time(), "outcome": "not_started"}
        try:
            state = json.loads((output.parent / "installation.json").read_text(encoding="utf-8"))
            target = GAME / "USER/Client/0/Controls/defaultProfile.xml"
            if Path(state["target"]).resolve() != target.resolve() or sha256_file(target) != state["candidate_sha256"]:
                raise RuntimeError("Native test profile is not installed as prepared")
            hwnd = game_window_handle()
            if not hwnd:
                raise RuntimeError("Star Citizen window was not found")
            keyboard = Keyboard(hwnd, hold=.060, gap=.005)
            child = subprocess.Popen([sys.executable, "-B", str(ROOT / "tools/probe_displayinfo_pulse.py"),
                                      "--seconds", "30", "--stop-after-quiet", "0",
                                      "--publish-status", "--output", str(output)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            deadline = time.monotonic() + 15
            self.show("Arming read-only capture. No game input yet.")
            while not output.with_suffix(".ready.json").exists():
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Capture did not become ready; no input sent")
                time.sleep(.05)
            for remaining in (3, 2, 1):
                self.show(f"Native key test in {remaining}s. Keep this tester focused; game will come forward.")
                time.sleep(1)
            report["handoff"] = keyboard.handoff_from_tester()
            if off_only:
                off_at = time.time()
                keyboard.key(0x7E)
                wait_visibility(output, False, 2, keyboard, after=off_at, stable_for=.150)
                report["outcome"] = "off_key_sent_panel_absent"
            else:
                wait_visibility(output, False, 1, keyboard, stable_for=.150)
                native_pulse(keyboard, lambda visible, after, stable: wait_visibility(
                    output, visible, 2, keyboard, after=after, stable_for=stable))
                report["outcome"] = "panel_captured_then_absent"
        except Exception as exc:
            report["error"] = str(exc)
            report["outcome"] = "unverified_or_failed"
        finally:
            if child:
                output.with_suffix(".stop").touch()
                try:
                    child.wait(timeout=40)  # Offline OCR happens after the native Off request.
                except subprocess.TimeoutExpired:
                    child.terminate()
                    report["capture_error"] = "Capture/OCR did not finish in time"
            if report["outcome"] == "panel_captured_then_absent":
                try:
                    capture = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
                    report["readings"] = [sample for burst in capture["bursts"] for sample in burst["samples"]
                        if all(sample["values"].get(key) is not None for key in ("server_fps", "srv_pop", "shard_pop"))]
                    report["outcome"] = ("snapshot_captured_and_off_confirmed" if report["readings"] and not capture["errors"]
                                         else "native_toggle_observed_no_complete_snapshot")
                except (OSError, ValueError, KeyError) as exc:
                    report["outcome"] = "native_toggle_observed_no_complete_snapshot"
                    report["capture_error"] = str(exc)
            if output.parent.exists():
                report["finished_at"] = time.time()
                output.with_suffix(".native.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.show((f"Native pulse verified, console untouched.\n{report['readings'][-1]['values']}\nAutomatic sampling remains disabled."
                       if report["outcome"] == "snapshot_captured_and_off_confirmed" else
                       "Native panel On/Off observed, but no complete population/FPS snapshot decoded."
                       if report["outcome"] == "native_toggle_observed_no_complete_snapshot" else
                       "Off key sent; panel absent." if report["outcome"] == "off_key_sent_panel_absent" else
                       f"Test unverified: {report.get('error', 'Capture failed')}.\n"
                       "If the panel remains visible, use Request Off. No recurring input is running."))
            self.root.after(0, self.finish)


if __name__ == "__main__":
    Tester().root.mainloop()
