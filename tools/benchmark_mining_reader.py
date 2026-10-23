"""Replay the actual SynthScan reader against upstream marker crops.

No game capture, keyboard input, live-app launch or player-record writes.
These four small crops are a regression sample, not a live accuracy benchmark.
"""
from pathlib import Path
import json
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from detector import SignatureDetector


def main():
    detector = SignatureDetector.__new__(SignatureDetector)
    detector.require_game_focus = False
    detector.monitor_rect = {}
    detector.ocr = None
    detector._ocr_lock = threading.Lock()
    detector._pending_sig = None
    detector._pending_count = 0
    detector._pending_at = 0
    rows = []
    for path in sorted((ROOT / "research/bedrock_upstream/tests").glob("*marker*.png")):
        image = Image.open(path).convert("RGB")
        detector._grab_rect_pil = lambda rect: image
        detector._pending_sig = None
        detector._pending_count = 0
        expected = int(path.stem.rsplit("_", 1)[-1])
        started = time.perf_counter()
        first, first_number, _ = detector.scan_screen()
        match, number, raw = detector.scan_screen()
        rows.append({"fixture": path.name, "expected": expected, "accepted": number,
                     "correct": number == expected, "first_frame_rejected": first is None,
                     "details": match["details"] if match else None, "raw_text": raw,
                     "two_reads_ms": round((time.perf_counter()-started)*1000, 1)})
    report = {"fixture_count": len(rows), "correct": sum(row["correct"] for row in rows),
              "incorrect_accepted": sum(row["accepted"] is not None and not row["correct"] for row in rows),
              "scope": "Four upstream crops, no live game or full-screen marker localization; misses remain.", "readings": rows}
    output = ROOT / "research/bedrock_mining_replay.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
