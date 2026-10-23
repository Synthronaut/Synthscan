"""Read-only WGC telemetry probe. Never sends game input or changes records.

This tests window-surface capture, NOT telemetry with r_DisplayInfo disabled.
Optional dependencies: windows-capture, plus the app's existing OpenCV/Pillow.
Use --dependency-dir when testing a separately installed copy of windows-capture.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-dir", type=Path)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--save-samples", action="store_true", help="Save each diagnostic corner alongside its decoded sample")
    parser.add_argument("--reader", choices=("validated", "legacy"), default="validated")
    parser.add_argument("--output", type=Path, default=ROOT / "research" / "window_capture_probe")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 30:
        parser.error("--seconds must be between 1 and 30")
    if args.dependency_dir:
        sys.path.insert(0, str(args.dependency_dir.resolve()))
    from windows_capture import WindowsCapture
    import cv2
    from displayinfo_reader import FastDisplayInfoBitmapReader
    from validated_displayinfo import ValidatedDisplayInfoReader
    reader = ValidatedDisplayInfoReader() if args.reader == "validated" else FastDisplayInfoBitmapReader()

    user = ctypes.windll.user32
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.IsIconic.argtypes = [wintypes.HWND]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    hwnd = user.FindWindowW("CryENGINE", None)
    if not hwnd or user.IsIconic(hwnd):
        raise RuntimeError("A non-minimized Star Citizen window is required")
    process_id = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, process_id.value)  # Query name only; no VM access.
    if not handle:
        raise RuntimeError("Cannot verify game window owner")
    try:
        name = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(name))
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
            raise RuntimeError("Cannot read game process image name")
        if Path(name.value).name.lower() != "starcitizen.exe":
            raise RuntimeError("CryENGINE window is not owned by StarCitizen.exe")
    finally:
        kernel.CloseHandle(handle)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    capture = WindowsCapture(window_hwnd=int(hwnd), cursor_capture=False,
                             draw_border=False, minimum_update_interval=500)
    samples = []
    ready = threading.Event()
    last_sample = 0
    last_crop = None
    started = time.monotonic()

    @capture.event
    def on_frame_arrived(frame, control):
        nonlocal last_sample, last_crop
        now = time.monotonic()
        if now - last_sample >= .75:
            # Copy only the diagnostic corner, never a whole gameplay recording.
            last_crop = frame.frame_buffer[:min(420, frame.height), max(0, frame.width-1400):, :3].copy()
            result = reader.parse_image(last_crop)
            image_name = None
            if args.save_samples:
                image_path = args.output.with_name(args.output.name + f"_{len(samples):03d}").with_suffix(".png")
                cv2.imwrite(str(image_path), last_crop)
                image_name = image_path.name
            samples.append({"at": time.time(), "image": image_name, "frame_size": [frame.width, frame.height],
                            "values": {key: result.get(key) for key in
                                       ("ping_ms", "server_fps", "server_name", "restarts", "shard_pop", "srv_pop")}})
            last_sample = now
            ready.set()
        if now - started >= args.seconds:
            control.stop()

    @capture.event
    def on_closed():
        ready.set()

    controller = capture.start_free_threaded()
    try:
        ready.wait(min(5, args.seconds))
        # A finite timeout also stops captures that produce no further frames.
        remaining = args.seconds - (time.monotonic() - started)
        if remaining > 0:
            threading.Event().wait(remaining)
    finally:
        controller.stop()
    report = {"source": "windows_graphics_capture_window", "reader": args.reader, "samples": samples,
              "debug_off_solution": False,
              "limitation": "Rendered debug text is still required; capture alone does not remove it from the player's view."}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if last_crop is not None:
        cv2.imwrite(str(args.output.with_suffix(".png")), last_crop)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
