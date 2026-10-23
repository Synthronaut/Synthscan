"""Native mining capture/readers, with the earlier RapidOCR path retained."""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import re
import ctypes
import threading
import time
import cv2
import numpy as np
import mss
from PIL import Image, ImageGrab
from radar_db import parse_signature
from config import get_monitor_by_id


def read_signature_candidates(ocr_results):
    """Accept a whole numeric/RS row, never a number pulled out of other text.

This is a guard for the existing OCR path, not Bedrock's marker locator. A
plausible arithmetic value alone cannot identify a scanner label on screen.
"""
    found = {}
    for box, text, confidence in ocr_results or []:
        if float(confidence) < .78:
            continue
        token = re.fullmatch(r"(?:RS\s*[:=]?\s*)?([0-9]{4,6}|[0-9]{1,3}(?:,[0-9]{3}){1,2})", text.strip(), re.IGNORECASE)
        if not token:
            continue
        number = int(token[1].replace(",", ""))
        match = parse_signature(number)
        if match and (number not in found or confidence > found[number][1]):
            match["ocr_confidence"] = float(confidence)
            found[number] = (match, float(confidence))
    return found

try:
    cv2.setNumThreads(1)
except Exception:
    pass


def is_star_citizen_foreground():
    """
    Returns True if the current Windows foreground window belongs to Star Citizen.
    """
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return False
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value.strip().lower()
        return "star citizen" in title
    except Exception:
        return False


class SignatureDetector:
    def __init__(self, screen_res=(2560, 1440), box_size=(520, 320), offset=(0, 0), game_monitor=1, require_game_focus=True):
        self.screen_res = screen_res
        self.box_size = box_size
        self.offset = offset
        self.game_monitor = game_monitor
        self.require_game_focus = require_game_focus
        self.ocr = None  # Lazy-loaded only when rock radar scanning is actively enabled!
        self._ocr_lock = threading.Lock()
        self._tls = threading.local()
        self.monitor_rect = {}
        self._pending_sig = None
        self._pending_count = 0
        self._pending_at = 0
        self.native_enabled = True
        self.native_context = {}
        self.native_client = None
        self.terminal_native_client = None
        self._native_create_lock = threading.Lock()
        self._native_closed = False
        self.latest_native_result = None
        self.native_error = ''
        self._last_panel_at = 0
        self._last_native_retry = 0
        self._last_loadout_at = 0
        self.update_roi()

    def set_native_context(self, session, fit=None):
        self.native_context = dict(session=session or '',fit=fit)

    def scan_native(self):
        from native_mining import NativeMiningError, marker_match
        self.latest_native_result = None
        if time.monotonic()-self._last_native_retry<5:
            return None,None,[]
        client=self.get_native_client()
        context=self.native_context.copy()
        panel=time.monotonic()-self._last_panel_at>=1.5
        loadout=panel and time.monotonic()-self._last_loadout_at>=15
        fields=dict(session=context.get('session',''),panel=panel,contents=panel,loadout=loadout)
        if context.get('fit'):
            fields['fit']=context['fit']
        try:
            result=client.request('scan_live',**fields)
            result['_session']=context.get('session','')
            result['_fit']=context.get('fit')
            self.latest_native_result=result
            if panel:self._last_panel_at=time.monotonic()
            if loadout:self._last_loadout_at=time.monotonic()
            self.native_error=''
            match,number=marker_match(result)
            return match,number,[]
        except (NativeMiningError,OSError) as exc:
            self.native_error=str(exc)
            client.close()
            with self._native_create_lock:
                if self.native_client is client:self.native_client=None
            self._last_native_retry=time.monotonic()
            return None,None,[]

    def close(self):
        with self._native_create_lock:
            self._native_closed=True
            clients=(self.native_client,self.terminal_native_client)
        for client in clients:
            if client:client.close()

    def get_native_client(self, terminal=False):
        from native_mining import NativeMiningClient,NativeMiningError
        name='terminal_native_client' if terminal else 'native_client'
        with self._native_create_lock:
            if getattr(self,'_native_closed',False):
                raise NativeMiningError('Mining readers have been shut down')
            client=getattr(self,name,None)
            if client is None or client.closed:
                client=NativeMiningClient()
                setattr(self,name,client)
            return client

    def _get_ocr(self):
        if self.ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            # The installed RapidOCR defaults to enlarging the short side to
            # 736px, turning a tiny marker into a multi-megapixel OCR job.
            self.ocr = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1,
                                det_model_path=None, det_limit_type="max", det_limit_side_len=1280)
        return self.ocr

    def _get_sct(self):
        if not hasattr(self._tls, "sct") or self._tls.sct is None:
            self._tls.sct = mss.MSS()
        return self._tls.sct

    def set_game_monitor(self, mon_id):
        self.game_monitor = int(mon_id)
        self.update_roi()

    def update_roi(self):
        # 1. Try to center on Star Citizen's actual window rect if active
        try:
            u32 = ctypes.windll.user32
            h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                u32.SetThreadDesktop(h_desk)
            hwnd = u32.FindWindowW("CryENGINE", "Star Citizen ") or u32.FindWindowW("CryENGINE", None)
            if hwnd and u32.IsWindowVisible(hwnd) and not u32.IsIconic(hwnd):
                from ctypes import wintypes
                r = wintypes.RECT()
                u32.GetWindowRect(hwnd, ctypes.byref(r))
                gw = r.right - r.left
                gh = r.bottom - r.top
                if gw > 400 and gh > 300:
                    cx = r.left + (gw // 2) + self.offset[0]
                    cy = r.top + (gh // 2) + self.offset[1]
                    w, h = self.box_size
                    self.screen_res = (gw, gh)
                    self.monitor_rect = {
                        "left": max(r.left, cx - w // 2),
                        "top": max(r.top, cy - h // 2),
                        "width": min(w, gw),
                        "height": min(h, gh)
                    }
                    return
        except Exception:
            pass

        # 2. Fallback to game monitor rect
        mon = get_monitor_by_id(self.game_monitor)
        m_left = mon["left"]
        m_top = mon["top"]
        m_w = mon["width"]
        m_h = mon["height"]
        self.screen_res = (m_w, m_h)

        cx = m_left + (m_w // 2) + self.offset[0]
        cy = m_top + (m_h // 2) + self.offset[1]
        w, h = self.box_size
        self.monitor_rect = {
            "left": max(m_left, cx - w // 2),
            "top": max(m_top, cy - h // 2),
            "width": w,
            "height": h
        }

    def _grab_rect_pil(self, rect):
        left = rect["left"]
        top = rect["top"]
        width = rect["width"]
        height = rect["height"]
        bbox = (left, top, left + width, top + height)

        try:
            sct = self._get_sct()
            sct_img = sct.grab(rect)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception:
            pass

        try:
            return ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")
        except Exception:
            pass

        try:
            return ImageGrab.grab(bbox=bbox).convert("RGB")
        except Exception:
            return ImageGrab.grab().convert("RGB")

    def grab_full_game_monitor_pil(self):
        mon = get_monitor_by_id(self.game_monitor)
        rect = {
            "left": mon["left"],
            "top": mon["top"],
            "width": mon["width"],
            "height": mon["height"]
        }
        return self._grab_rect_pil(rect)

    def grab_displayinfo_pil(self, rect):
        """
        Captures the top-right r_DisplayInfo region on the Game Monitor (no OCR, < 1ms).
        """
        try:
            return self._grab_rect_pil(rect)
        except Exception:
            return None

    def scan_screen(self):
        """
        Grabs screen ROI on the Game Monitor, runs single-threaded OCR if HUD pixels are present,
        and extracts valid radar signatures.
        """
        if getattr(self,'native_enabled',False):
            return self.scan_native()
        if self.require_game_focus and not is_star_citizen_foreground():
            self._pending_sig = None
            self._pending_count = 0
            return None, None, []

        pil_img = self._grab_rect_pil(self.monitor_rect)
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_cyan = cv2.inRange(hsv, (80, 50, 150), (105, 255, 255))
        mask_white = cv2.inRange(hsv, (0, 0, 200), (180, 50, 255))
        mask_amber = cv2.inRange(hsv, (12, 80, 150), (35, 255, 255))
        mask = cv2.bitwise_or(cv2.bitwise_or(mask_cyan, mask_white), mask_amber)

        # Skip nearly empty crops; bright terrain must not discard a marker.
        nz = cv2.countNonZero(mask)
        if nz < 120:
            self._pending_sig = None
            self._pending_count = 0
            return None, None, []

        # Keep the original color/anti-aliasing. Thresholding joins the strokes
        # in the game's small font and erased all four reviewed marker crops.
        # Small saved crops need enlargement; the live ROI is already larger.
        ocr_frame = (cv2.resize(frame, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                     if frame.shape[0] < 180 else frame)

        with self._ocr_lock:
            ocr_engine = self._get_ocr()
            ocr_res, _ = ocr_engine(ocr_frame, use_cls=False)

        if not ocr_res:
            self._pending_sig = None
            self._pending_count = 0
            return None, None, []

        raw_texts = [r[1] for r in ocr_res]
        candidates = read_signature_candidates(ocr_res)
        # Two different valid numbers in a crop need a marker locator to pick
        # between them. OCR confidence is not evidence of which one is a rock.
        if len(candidates) != 1:
            self._pending_sig = None
            self._pending_count = 0
            return None, None, raw_texts

        best_num, (best_match, _) = next(iter(candidates.items()))
        now = time.monotonic()
        if self._pending_sig == best_num and now - self._pending_at <= 3:
            self._pending_count += 1
        else:
            self._pending_sig = best_num
            self._pending_count = 1
        self._pending_at = now
        if self._pending_count < 2:
            return None, None, raw_texts
        return best_match, best_num, raw_texts

    def scan_loading_screen_for_shard_name(self):
        """
        Scans the center area of the game screen during queue / loading screen
        to detect CIG's two-word shard codename (e.g. 'Innovative Technology', 'Adaptable Weightlessness').
        Runs in ~30-50ms using RapidOCR, only invoked during the loading screen window.
        """
        mon = get_monitor_by_id(self.game_monitor)
        box_w = int(mon["width"] * 0.60)
        box_h = int(mon["height"] * 0.35)
        rect = {
            "left": mon["left"] + (mon["width"] - box_w) // 2,
            "top": mon["top"] + int(mon["height"] * 0.32),
            "width": box_w,
            "height": box_h
        }
        try:
            pil_img = self._grab_rect_pil(rect)
            if pil_img is None:
                return None
            ocr = self._get_ocr()
            img_np = np.array(pil_img)
            results, _ = ocr(img_np)
            if not results:
                return None
            full_text = " ".join([r[1] for r in results if r and len(r) > 2 and r[1] and float(r[2]) >= 0.90])
            pattern = r'(?:connecting\s+to(?:\s+shard)?\s*:?|shard\s*(?:name)?\s*[:\-])\s*([A-Za-z]{3,}[\s_]+[A-Za-z]{3,})'
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                raw_name = m.group(1).replace('_', ' ').strip().upper()
                raw_name = re.sub(r'[\.\,\;]+$', '', raw_name)
                words = raw_name.split()
                generic = {'YOUR', 'CURRENT', 'POSITION', 'IN', 'QUEUE', 'IS', 'THE', 'SERVER', 'SHARD', 'LOADING', 'CONNECTING'}
                if len(words) == 2 and not generic.intersection(words):
                    return " ".join(words)
            # Unlabelled two-word text can be a loading tip or unrelated UI.
            return None
        except Exception:
            return None

