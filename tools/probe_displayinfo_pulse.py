"""Measure short rendered DisplayInfo pulses; never sends game input.

Run before the finite, manually invoked console batch. Capture every eligible
window frame, locate the existing font anchor, and decode saved corner images
only AFTER capture ends. Native frame timestamps measure captured visibility,
not physical monitor scanout. No inventory/session records are changed.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class PulseTrace:
    def __init__(self):
        self.frames = []
        self.bursts = []
        self.current = None

    def add(self, native_100ns, at, visible, score, image=None):
        row = {"native_100ns": int(native_100ns), "at": at,
               "visible": bool(visible), "anchor_score": float(score)}
        previous = self.frames[-1] if self.frames else None
        self.frames.append(row)
        if visible:
            if self.current is None:
                self.current = {"first": row, "previous": previous,
                                "count": 0, "images": []}
            self.current["last"] = row
            self.current["count"] += 1
            if image is not None:
                # First three and latest frames, bounded independently of pulse length.
                entry = (row, image.copy())
                if len(self.current["images"]) < 4:
                    self.current["images"].append(entry)
                else:
                    self.current["images"][-1] = entry
        elif self.current is not None:
            self.current["next"] = row
            self.bursts.append(self.current)
            self.current = None

    def summarize(self):
        intervals = [(b["native_100ns"]-a["native_100ns"])/10000
                     for a, b in zip(self.frames, self.frames[1:])
                     if b["native_100ns"] > a["native_100ns"]]
        bursts = []
        for burst in self.bursts + ([self.current] if self.current else []):
            first, last = burst["first"], burst["last"]
            previous, following = burst["previous"], burst.get("next")
            bursts.append({"frames": burst["count"], "first_at": first["at"],
                           "last_at": last["at"],
                           "bracketed": previous is not None and following is not None,
                           "captured_span_ms": (last["native_100ns"]-first["native_100ns"])/10000,
                           "first_visible_to_absent_ms": ((following["native_100ns"]-first["native_100ns"])/10000
                                               if following else None),
                           "outer_bracket_ms": ((following["native_100ns"]-previous["native_100ns"])/10000
                                                if previous and following else None)})
        return {"frames": len(self.frames),
                "median_capture_interval_ms": statistics.median(intervals) if intervals else None,
                "bursts": bursts,
                "ended_with_displayinfo_detected": bool(self.frames and self.frames[-1]["visible"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--output", type=Path, default=ROOT/"research"/"displayinfo_pulse")
    parser.add_argument("--stop-after-quiet", type=float, default=4)
    parser.add_argument("--publish-status", action="store_true", help="Publish latest detector status for the manual macro tester")
    args = parser.parse_args()
    if not 5 <= args.seconds <= 1800:
        parser.error("--seconds must be between 5 and 1800")
    import cv2
    import numpy as np
    from telemetry_ipc import publish_json
    from windows_capture import WindowsCapture
    from window_telemetry_capture import game_window_handle
    from validated_displayinfo import ValidatedDisplayInfoReader
    cv2.setNumThreads(1)
    hwnd = game_window_handle()
    if not hwnd:
        raise RuntimeError("A non-minimized Star Citizen window is required")
    reader = ValidatedDisplayInfoReader()
    template = reader.anchors.kw["kw_sfps"]
    trace = PulseTrace()
    ready, closed = threading.Event(), threading.Event()
    errors = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stop_path = args.output.with_suffix(".stop")
    if stop_path.exists():
        raise RuntimeError(f"Remove stale stop marker before starting: {stop_path}")
    capture = WindowsCapture(window_hwnd=hwnd, cursor_capture=False,
                             draw_border=False, minimum_update_interval=0)
    started = time.monotonic()
    last_visible = None
    last_published_at = None

    @capture.event
    def on_frame_arrived(frame, control):
        nonlocal last_visible
        try:
            # Match the existing font at full resolution, no numeric OCR here.
            corner = frame.frame_buffer[:min(420, frame.height), max(0, frame.width-1400):, :3]
            gray = cv2.cvtColor(corner[10:min(210, corner.shape[0])], cv2.COLOR_BGR2GRAY).astype(np.float32)
            score = cv2.minMaxLoc(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))[1]
            visible = score >= .80
            now = time.monotonic()
            if visible:
                last_visible = now
            trace.add(frame.timespan, time.time(), visible, score, corner if visible else None)
            ready.set()
        except Exception as exc:
            errors.append(repr(exc))
            control.stop()
            closed.set()

    @capture.event
    def on_closed():
        closed.set()

    controller = capture.start_free_threaded()
    try:
        if not ready.wait(10):
            raise RuntimeError("No game frame received within ten seconds")
        args.output.with_suffix(".ready.json").write_text(json.dumps({"status": "ready", "at": time.time()}))
        print("READY: capture is armed; run the finite console batch now.", flush=True)
        while time.monotonic()-started < args.seconds and not closed.wait(.01):
            if args.publish_status and trace.frames and trace.frames[-1]["at"] != last_published_at:
                publish_json(args.output.with_suffix(".status.json"),
                             {"written_at": time.time(), "frame": trace.frames[-1],
                              "frames": len(trace.frames)})
                last_published_at = trace.frames[-1]["at"]
            if stop_path.exists():
                break
            if last_visible and args.stop_after_quiet > 0 and time.monotonic()-last_visible > args.stop_after_quiet:
                break
    finally:
        controller.stop()
    report = trace.summarize()
    report.update(errors=errors, timeline=trace.frames,
                  measurement="Windows Graphics Capture frame timestamps; not monitor scanout",
                  automation="None: this probe never sends input or changes game settings")
    all_bursts = trace.bursts + ([trace.current] if trace.current else [])
    for index, (burst, summary) in enumerate(zip(all_bursts, report["bursts"])):
        decoded = []
        for sample, (row, crop) in enumerate(burst["images"]):
            path = args.output.with_name(args.output.name+f"_{index:02d}_{sample:02d}").with_suffix(".png")
            cv2.imwrite(str(path), crop)
            values = reader.parse_image(crop)
            decoded.append({"image": path.name, "at": row["at"],
                            "values": {k: values.get(k) for k in ("server_fps", "srv_pop", "shard_pop", "server_name")}})
        summary["samples"] = decoded
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "timeline"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
