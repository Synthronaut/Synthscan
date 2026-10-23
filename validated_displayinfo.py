"""Conservative recognition of rendered diagnostics, independent of mining OCR.

The legacy digit atlas contains mislabeled variants. Only its word anchors are
used here. Numeric fields are recognized twice, at different scales, and must
agree. This is still a screen reader, never a debug-off telemetry provider.
"""
import re
import math
import time

import cv2
import numpy as np

from displayinfo_reader import FastDisplayInfoBitmapReader

# Right-aligned closing bracket in the 9-pixel diagnostic font, manually checked
# against pulse_dim.png. Match its shape independently of text brightness. This
# lets OCR exclude the bracket instead of confusing it with a trailing digit 1.
POPULATION_BRACKET = np.array([
    [9, 9, 9, 9, 9, 9], [9, 69, 76, 30, 9, 9], [9, 9, 57, 24, 7, 9],
    [9, 9, 59, 26, 6, 9], [9, 10, 59, 26, 7, 9], [10, 10, 59, 26, 6, 9],
    [10, 9, 59, 26, 7, 9], [9, 10, 59, 26, 7, 10], [11, 10, 59, 26, 7, 10],
    [9, 27, 64, 26, 7, 10], [9, 28, 26, 8, 7, 9], [10, 10, 7, 7, 9, 9],
], dtype=np.float32)


def numeric_token(text, kind):
    """Require field punctuation/units; never turn a damaged suffix into digits."""
    text = text.strip()
    if kind == "integer":
        match = re.fullmatch(r"(\d{1,6})\s*[,.]?", text)
    elif kind == "node":
        match = re.match(r"^(\d{1,6})\s*,", text)
    elif kind == "fps":
        match = re.match(r"^(\d{1,3}[.,]\d)\s*(?:[\[{]|$)", text)
    elif kind == "ping":
        # The recognizer often reads the unit's s as 5. It is not a value digit.
        match = re.match(r"^(\d{1,5}[.,]\d)\s*m[s5]", text, re.I)
    else:
        raise ValueError(kind)
    if not match:
        return None
    value = float(match[1].replace(",", ".")) if kind in {"fps", "ping"} else int(match[1])
    limit = {"fps": 240, "ping": 30000}.get(kind, 100000)
    return value if 0 <= value <= limit else None


class ValidatedDisplayInfoReader:
    def __init__(self, recognizer=None):
        self.anchors = FastDisplayInfoBitmapReader()
        self._recognizer = recognizer
        self.last_evidence = {}

    def _recognize(self, image):
        if self._recognizer is None:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1,
                              use_text_det=False, use_angle_cls=False)
            self._recognizer = engine.text_recognizer
        # Single-field calls avoid a different field's width changing batch padding.
        result, _ = self._recognizer([image])
        return result[0] if result else ("", 0)

    def _number(self, frame, rect, kind, key):
        x, y, end = rect
        if y < 1 or end <= x + 4 or y + 10 > frame.shape[0]:
            return None
        strip = frame[y-1:y+10, x:end]
        readings = []
        for scale in (3, 4):
            enlarged = cv2.resize(strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            enlarged = cv2.copyMakeBorder(enlarged, 8, 8, 8, 8, cv2.BORDER_REPLICATE)
            text, score = self._recognize(enlarged)
            readings.append((text, float(score), numeric_token(text, kind)))
        self.last_evidence[key] = readings
        if any(not math.isfinite(score) or score < .60 or value is None for _, score, value in readings):
            return None
        return readings[0][2] if readings[0][2] == readings[1][2] else None

    def _population_clause(self, frame, shard):
        """Read the complete labelled clause when a faint single digit fails.

        Keep numeric tokens literal. Only the fixed 'srv' label permits the
        recognizer's s/5 ambiguity; counts and the closing bracket are required.
        """
        x, y, _ = shard
        if x < frame.shape[1]-220 or y < 1 or y+11 > frame.shape[0]:
            return None
        bracket = cv2.cvtColor(frame[y-1:y+11, -12:-6], cv2.COLOR_BGR2GRAY).astype(np.float32)
        bracket_score = float(cv2.matchTemplate(bracket, POPULATION_BRACKET, cv2.TM_CCOEFF_NORMED)[0, 0])
        bracket_verified = bracket_score >= .90
        self.last_evidence["population_bracket_score"] = bracket_score
        strip = frame[y-1:y+10, max(0, x-1):(-12 if bracket_verified else None)]
        readings = []
        for scale in (3, 4):
            enlarged = cv2.resize(strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            enlarged = cv2.copyMakeBorder(enlarged, 8, 8, 8, 8, cv2.BORDER_REPLICATE)
            text, score = self._recognize(enlarged)
            # Label glyphs may read as 5/s and y/v in this tiny font. This
            # tolerance applies only to fixed labels, never to numeric tokens.
            pattern = r"\s*[s5]hard\s+(\d{1,6})\s*,\s*[s5]r[vy]{1,2}\s+(\d{1,6})\s*"
            if not bracket_verified:
                pattern += r"\]\s*"
            match = re.fullmatch(pattern, text, re.I)
            values = tuple(map(int, match.groups())) if match else None
            if values and not 0 <= values[1] <= values[0] <= 100000:
                values = None
            readings.append((text, float(score), values))
        self.last_evidence["population_clause"] = readings
        if any(not math.isfinite(score) or score < .75 or values is None for _, score, values in readings):
            return None
        return readings[0][2] if readings[0][2] == readings[1][2] else None

    def parse_image(self, image, prev_state=None):
        # Never carry numeric or server-name readings into a new image.
        state = self.anchors.parse_image(None)
        if prev_state:
            state["shard_id"] = prev_state.get("shard_id", "--")
        self.last_evidence = {}
        if image is None or not self.anchors.loaded:
            return state
        if hasattr(image, "convert"):
            frame = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        else:
            frame = np.asarray(image)
        if frame.ndim != 3 or frame.shape[2] < 3 or frame.shape[0] < 120 or frame.shape[1] < 400:
            return state
        frame = frame[:, :, :3]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        height, width = gray.shape

        def locate(key, low, high, threshold):
            template = self.anchors.kw.get(key)
            roi = gray[max(0, low):min(height, high)]
            if template is None or roi.shape[0] < template.shape[0] or width < template.shape[1]:
                return None
            _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED))
            return (x, max(0, low)+y, x+template.shape[1]) if score >= threshold else None

        fps = locate("kw_sfps", 10, min(height, 210), .80)
        if not fps:
            return state
        # Nested zones add lines; do not assume a fixed vertical location.
        y = fps[1]
        game = locate("kw_game", y+10, y+25, .70)
        shard = locate("kw_shard", y+10, y+25, .60)
        local = locate("kw_srv", y+10, y+25, .80)
        restart = locate("kw_restarts", y+10, y+25, .55)
        row_valid = (shard and local and shard[0] < local[0]
                     and abs(shard[1]-local[1]) <= 1)

        # The 9-pixel font profile ends this right-aligned row in ', srv N]'.
        # Exclude the closing bracket, which OCR otherwise sometimes calls '1'.
        local_value = self._number(frame, (local[2], local[1], width-12), "integer", "srv_pop") if row_valid else None
        shard_value = self._number(frame, (shard[2], shard[1], local[0]-1), "integer", "shard_pop") if row_valid else None
        clause = self._population_clause(frame, shard) if shard else None
        if clause is not None:
            if ((shard_value is not None and shard_value != clause[0])
                    or (local_value is not None and local_value != clause[1])):
                local_value = shard_value = None
            else:
                shard_value, local_value = clause
        if local_value is not None and shard_value is not None and local_value > shard_value:
            local_value = shard_value = None
        state["srv_pop"], state["shard_pop"] = local_value, shard_value
        if game and restart and shard and game[0] < restart[0] < shard[0]:
            node = self._number(frame, (game[2], game[1], restart[0]-1), "node", "server_name")
            if node is not None:
                state["server_name"], state["srv_id"] = f"GAME-{node}", str(node)
        fps_candidates = []
        for span in (40, 47, 55):
            value = self._number(frame, (fps[2], y, min(width, fps[2]+span)), "fps", f"server_fps_{span}")
            if value is not None:
                fps_candidates.append(value)
        if fps_candidates and len(set(fps_candidates)) == 1:
            state["server_fps"] = fps_candidates[0]
        ping = locate("kw_ping", y+21, y+40, .80)
        if ping:
            state["ping_ms"] = self._number(frame, (ping[2], ping[1], min(width, ping[2]+65)), "ping", "ping_ms")
        state["detected_lines"] = 3
        state["max_y"] = (ping[1]+11) if ping else ((local[1]+11) if local else y+11)
        state["last_seen_ts"] = time.time()
        state["_validated_fields"] = [key for key in ("ping_ms", "server_fps", "shard_pop", "srv_pop")
                                       if state.get(key) is not None]
        if state["server_name"] != "--":
            state["_validated_fields"].append("server_name")
        return state
