"""Optional fixed-font DisplayInfo decoder and friendly text labels.

This decoder requires visible game text. The application state lives in
telemetry_core.py; there is no synthetic latency fallback.
"""

import os
import re
import json
import time
import ctypes
import hashlib
import tkinter as tk
import cv2
import numpy as np
from config import get_monitor_by_id

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARD_HISTORY_FILE = os.path.join(BASE_DIR, "shard_history.json")
GLYPH_ATLAS_FILE = os.path.join(BASE_DIR, "displayinfo_glyphs.npz")
DEFAULT_GAME_LOG = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Deterministic 2-word callsign vocabulary for instant human recognition when server hopping
CALLSIGN_ADJECTIVES = [
    "SOLAR", "CRIMSON", "IRON", "COBALT", "ASTRAL", "NEON", "QUANTUM", "OBSIDIAN",
    "APEX", "SILENT", "GOLDEN", "FROST", "VORTEX", "HYPER", "SHADOW", "TITAN",
    "NOVA", "EMBER", "STORM", "CYBER", "STELLAR", "ONYX", "PLASMA", "VALIANT",
    "ARCTIC", "RADIANT", "PHANTOM", "OMEGA", "VECTOR", "ZENITH", "PRIME", "ECLIPSE"
]

CALLSIGN_NOUNS = [
    "FALCON", "VANGUARD", "VALKYRIE", "NOMAD", "PHOENIX", "DRIFTER", "SENTINEL", "HORIZON",
    "CORSAIR", "LANCER", "SABRE", "GLADIUS", "POLARIS", "KRAKEN", "JAVELIN", "SPECTRE",
    "WARDEN", "HARBINGER", "ECLIPSE", "REDEEMER", "PERSEUS", "ODYSSEY", "CARRACK", "PIONEER",
    "RECLAIMER", "PROSPECTOR", "MOLE", "VULTURE", "STARFARER", "HERCULES", "LIBERATOR", "NAUTILUS"
]

# Region code translations (from AWS / StarEngine region tags)
REGION_MAP = {
    "use1": "US-EAST",
    "use2": "US-EAST",
    "usw1": "US-WEST",
    "usw2": "US-WEST",
    "usc1": "US-CENTRAL",
    "euw1": "EU-WEST",
    "euw2": "EU-WEST",
    "euc1": "EU-CENTRAL",
    "apse1": "ASIA-SE",
    "apse2": "AUS-SYD",
    "apne1": "ASIA-NE",
    "ape1": "ASIA-EAST",
}

# Friendly location dictionary for common Star Citizen internal zone / LZ codes
LOCATION_FRIENDLY_MAP = {
    "RR ARC LEO": "BAIJINI POINT (ARCCORP)",
    "RR HUR LEO": "EVERUS HARBOR (HURSTON)",
    "RR CRU LEO": "SERAPHIM (CRUSADER)",
    "RR MIC LEO": "PORT TRESSLER (MICROTECH)",
    "RR HUR L1": "HUR-L1 GREEN GLADE",
    "RR HUR L2": "HUR-L2 FAITHFUL DREAM",
    "RR HUR L3": "HUR-L3 THUNDERING EXPRESS",
    "RR HUR L4": "HUR-L4 MELODIC FIELDS",
    "RR HUR L5": "HUR-L5 HIGH COURSE",
    "RR CRU L1": "CRU-L1 AMBITIOUS DREAM",
    "RR CRU L4": "CRU-L4 SHALLOW FIELDS",
    "RR CRU L5": "CRU-L5 BEAUTIFUL GLEN",
    "RR ARC L1": "ARC-L1 WIDE FOREST",
    "RR ARC L2": "ARC-L2 LIVELY PATHWAY",
    "RR ARC L3": "ARC-L3 MODERN EXPRESS",
    "RR ARC L4": "ARC-L4 FAINT GLEN",
    "RR ARC L5": "ARC-L5 YELLOW CORE",
    "RR MIC L1": "MIC-L1 SHALLOW FRONTIER",
    "RR MIC L2": "MIC-L2 LONG FOREST",
    "RR MIC L3": "MIC-L3 ENDLESS ODYSSEY",
    "RR MIC L4": "MIC-L4 RED CROSSROADS",
    "RR MIC L5": "MIC-L5 MODERN ICARUS",
    "STANTON 1": "HURSTON",
    "STANTON 1A": "ARIEL",
    "STANTON 1B": "ABERDEEN",
    "STANTON 1C": "MAGDA",
    "STANTON 1D": "ITA",
    "STANTON 2": "CRUSADER",
    "STANTON 2A": "CELLIN",
    "STANTON 2B": "DAYMAR",
    "STANTON 2C": "YELA",
    "STANTON 3": "ARCCORP",
    "STANTON 3A": "LYRIA",
    "STANTON 3B": "WALA",
    "STANTON 4": "MICROTECH",
    "STANTON 4A": "CALLIOPE",
    "STANTON 4B": "CLIO",
    "STANTON 4C": "EUTERPE",
    "GRIM HEX": "GRIM HEX",
    "GRIMHEX": "GRIM HEX",
    "CELLIN": "CELLIN",
    "DAYMAR": "DAYMAR",
    "YELA": "YELA",
    "HURSTON": "HURSTON",
    "ARIEL": "ARIEL",
    "ABERDEEN": "ABERDEEN",
    "MAGDA": "MAGDA",
    "ITA": "ITA",
    "CRUSADER": "CRUSADER",
    "ARCCORP": "ARCCORP",
    "LYRIA": "LYRIA",
    "WALA": "WALA",
    "MICROTECH": "MICROTECH",
    "CALLIOPE": "CALLIOPE",
    "CLIO": "CLIO",
    "EUTERPE": "EUTERPE",
    "PYRO": "PYRO",
    "SERAPHIM": "SERAPHIM",
    "BAIJINI": "BAIJINI POINT",
    "EVERUS": "EVERUS HARBOR",
    "TRESSLER": "PORT TRESSLER",
    # Jump point stations & Gateways
    "RR JP STANTONPYRO": "PYRO GATEWAY",
    "RR JP PYROSTANTON": "STANTON GATEWAY",
    "RR JP STANTONMAGNUS": "MAGNUS GATEWAY",
    "RR JP STANTONTERRA": "TERRA GATEWAY",
    "RR JP PYRONYX": "NYX GATEWAY",
    "RR_JP_STANTONPYRO": "PYRO GATEWAY",
    "RR_JP_PYROSTANTON": "STANTON GATEWAY",
    "RR_JP_STANTONMAGNUS": "MAGNUS GATEWAY",
    "RR_JP_STANTONTERRA": "TERRA GATEWAY",
    "RR_JP_PYRONYX": "NYX GATEWAY",

    # Pyro Stations & Rest Stops (mined directly from global.ini)
    "RR_P3_LEO": "ORBITUARY",
    "RR_P3": "ORBITUARY",
    "RRP3_LEO": "ORBITUARY",
    "RRP3 LEO": "ORBITUARY",
    "RR P3 LEO": "ORBITUARY",
    "RS_INT_P3LEO": "ORBITUARY",
    "ORBITUARY": "ORBITUARY",
    "848868938": "ORBITUARY",

    "RR_P2_L4": "CHECKMATE",
    "RS_INT_P2L4": "CHECKMATE",
    "CHECKMATE": "CHECKMATE",

    "RR_P3_L1": "STARLIGHT SERVICE STATION",
    "RS_INT_P3L1": "STARLIGHT SERVICE STATION",
    "STARLIGHT": "STARLIGHT SERVICE STATION",

    "RR_P3_L3": "PATCH CITY",
    "RS_INT_P3L3": "PATCH CITY",
    "PATCH CITY": "PATCH CITY",

    "RR_P5_L2": "GASLIGHT",
    "RS_INT_P5L2": "GASLIGHT",
    "GASLIGHT": "GASLIGHT",

    "RR_P5_L4": "ROD'S FUEL 'N SUPPLIES",
    "RS_INT_P5L4": "ROD'S FUEL 'N SUPPLIES",
    "ROD'S FUEL": "ROD'S FUEL 'N SUPPLIES",

    "RR_P5_L5": "RAT'S NEST",
    "RS_INT_P5L5": "RAT'S NEST",
    "RAT'S NEST": "RAT'S NEST",

    "RR_P6": "RUIN STATION",
    "RR_P6_LEO": "RUIN STATION",
    "RS_INT_P6LEO": "RUIN STATION",
    "RUIN STATION": "RUIN STATION",

    "RR_P6_L3": "ENDGAME",
    "RS_INT_P6L3": "ENDGAME",
    "ENDGAME": "ENDGAME",

    "RR_P6_L4": "DUDLEY & DAUGHTERS",
    "RS_INT_P6L4": "DUDLEY & DAUGHTERS",

    "RR_P6_L5": "MEGUMI REFUELING",
    "RS_INT_P6L5": "MEGUMI REFUELING",

    # Stanton Orbital Transfer Stations (mined directly from global.ini)
    "STANTON1_TRANSFER": "EVERUS HARBOR",
    "EVERUS HARBOR": "EVERUS HARBOR",
    "EVERUS": "EVERUS HARBOR",

    "STANTON2_TRANSFER": "SERAPHIM STATION",
    "STANTON2_TRANSFER_SERAPHIM": "SERAPHIM STATION",
    "SERAPHIM STATION": "SERAPHIM STATION",
    "SERAPHIM": "SERAPHIM STATION",
    "3781743795": "SERAPHIM STATION",

    "STANTON3_TRANSFER": "BAIJINI POINT",
    "BAIJINI POINT": "BAIJINI POINT",
    "BAIJINI": "BAIJINI POINT",

    "STANTON4_TRANSFER": "PORT TRESSLER",
    "PORT TRESSLER": "PORT TRESSLER",
    "TRESSLER": "PORT TRESSLER",

    "THECOLLECTORASTEROID": "THE COLLECTOR",
    "THECOLLECTORASTEROID_STANTON": "THE COLLECTOR",
    "PYRO GATEWAY": "PYRO GATEWAY",
    "STANTON GATEWAY": "STANTON GATEWAY",
    "MAGNUS GATEWAY": "MAGNUS GATEWAY",
    "TERRA GATEWAY": "TERRA GATEWAY",
    "NYX GATEWAY": "NYX GATEWAY",
    "1547955914": "PYRO GATEWAY",
}

# Complete mapping from location names to official in-game clinics & hospitals (mined directly from global.ini)
LOCATION_TO_CLINIC = {
    # Pyro Clinics
    "ORBITUARY": "Orbituary Clinic",
    "ORBITUARY CLINIC": "Orbituary Clinic",
    "RR_P3": "Orbituary Clinic",
    "RR_P3_LEO": "Orbituary Clinic",
    "RRP3_LEO": "Orbituary Clinic",
    "RRP3 LEO": "Orbituary Clinic",
    "RR P3 LEO": "Orbituary Clinic",
    "RS_INT_P3LEO": "Orbituary Clinic",
    "848868938": "Orbituary Clinic",

    "CHECKMATE": "Checkmate Clinic",
    "CHECKMATE CLINIC": "Checkmate Clinic",
    "RR_P2_L4": "Checkmate Clinic",
    "RS_INT_P2L4": "Checkmate Clinic",

    "STARLIGHT SERVICE STATION": "Starlight Clinic",
    "STARLIGHT": "Starlight Clinic",
    "RR_P3_L1": "Starlight Clinic",
    "RS_INT_P3L1": "Starlight Clinic",

    "PATCH CITY": "Patch City Clinic",
    "RR_P3_L3": "Patch City Clinic",
    "RS_INT_P3L3": "Patch City Clinic",

    "GASLIGHT": "Gaslight Clinic",
    "RR_P5_L2": "Gaslight Clinic",
    "RS_INT_P5L2": "Gaslight Clinic",

    "ROD'S FUEL 'N SUPPLIES": "Rod's Clinic",
    "RR_P5_L4": "Rod's Clinic",
    "RS_INT_P5L4": "Rod's Clinic",

    "RAT'S NEST": "Rat's Nest Clinic",
    "RR_P5_L5": "Rat's Nest Clinic",
    "RS_INT_P5L5": "Rat's Nest Clinic",

    "RUIN STATION": "Ruin Clinic",
    "RUIN CLINIC": "Ruin Clinic",
    "RR_P6": "Ruin Clinic",
    "RR_P6_LEO": "Ruin Clinic",
    "RS_INT_P6LEO": "Ruin Clinic",

    "ENDGAME": "Endgame Clinic",
    "RR_P6_L3": "Endgame Clinic",
    "RS_INT_P6L3": "Endgame Clinic",

    "DUDLEY & DAUGHTERS": "Dudley Clinic",
    "RR_P6_L4": "Dudley Clinic",
    "RS_INT_P6L4": "Dudley Clinic",

    "MEGUMI REFUELING": "Megumi Clinic",
    "RR_P6_L5": "Megumi Clinic",
    "RS_INT_P6L5": "Megumi Clinic",

    "PYRO GATEWAY": "Pyro Gateway Clinic",
    "1547955914": "Pyro Gateway Clinic",
    "STANTON GATEWAY": "Stanton Gateway Clinic",
    "MAGNUS GATEWAY": "Magnus Gateway Clinic",
    "TERRA GATEWAY": "Terra Gateway Clinic",
    "NYX GATEWAY": "Nyx Gateway Clinic",

    # Stanton Clinics
    "BAIJINI POINT": "Baijini Point Clinic",
    "STANTON3_TRANSFER": "Baijini Point Clinic",

    "EVERUS HARBOR": "Everus Harbor Clinic",
    "STANTON1_TRANSFER": "Everus Harbor Clinic",

    "SERAPHIM STATION": "Seraphim Clinic",
    "SERAPHIM": "Seraphim Clinic",
    "STANTON2_TRANSFER": "Seraphim Clinic",
    "STANTON2_TRANSFER_SERAPHIM": "Seraphim Clinic",
    "3781743795": "Seraphim Clinic",

    "PORT TRESSLER": "Port Tressler Clinic",
    "STANTON4_TRANSFER": "Port Tressler Clinic",

    "GRIM HEX": "GrimHex Hospital",
    "LEVSKI": "Levski Clinic",
    "NYX_LEVSKI": "Levski Clinic",
    "ORISON": "Orison General",
    "CRUSADER": "Orison General",
    "NEW BABBAGE": "Brentworth Care Center",
    "MICROTECH": "Brentworth Care Center",
    "LORVILLE": "Maria Pure of Heart",
    "HURSTON": "Maria Pure of Heart",
    "AREA18": "Empire Health Services",
    "ARCCORP": "Empire Health Services",

    # Stanton Rest Stop Clinics
    "CRU-L1": "CRU-L1 Ambitious Dream Clinic",
    "CRU-L4": "CRU-L4 Shallow Fields Clinic",
    "CRU-L5": "CRU-L5 Beautiful Glen Clinic",
    "HUR-L1": "HUR-L1 Green Glade Clinic",
    "HUR-L2": "HUR-L2 Faithful Dream Clinic",
    "HUR-L3": "HUR-L3 Thundering Express Clinic",
    "HUR-L4": "HUR-L4 Melodic Fields Clinic",
    "HUR-L5": "HUR-L5 High Course Clinic",
    "ARC-L1": "ARC-L1 Wide Forest Clinic",
    "ARC-L2": "ARC-L2 Lively Pathway Clinic",
    "ARC-L3": "ARC-L3 Modern Express Clinic",
    "ARC-L4": "ARC-L4 Faint Glen Clinic",
    "ARC-L5": "ARC-L5 Yellow Core Clinic",
    "MIC-L1": "MIC-L1 Shallow Frontier Clinic",
    "MIC-L2": "MIC-L2 Long Forest Clinic",
    "MIC-L3": "MIC-L3 Endless Odyssey Clinic",
    "MIC-L4": "MIC-L4 Red Crossroads Clinic",
    "MIC-L5": "MIC-L5 Modern Icarus Clinic",
}



def generate_server_callsign(region_raw: str, shard_id: str, srv_id: str = "") -> str:
    """
    Generates a consistent, memorable Two-Word Callsign for a given Shard (e.g., 'STELLAR SABRE').
    Uses deterministic hashing on region + shard_id so the same shard ALWAYS has the exact same two-word name.
    """
    if not shard_id or str(shard_id) == "--":
        return "UNLINKED SECTOR"
    seed_key = f"{region_raw.lower().strip()}:{str(shard_id).strip()}"
    digest = hashlib.md5(seed_key.encode("utf-8")).digest()
    adj_idx = digest[0] % len(CALLSIGN_ADJECTIVES)
    noun_idx = digest[1] % len(CALLSIGN_NOUNS)
    return f"{CALLSIGN_ADJECTIVES[adj_idx]} {CALLSIGN_NOUNS[noun_idx]}"


def translate_region(raw_reg: str) -> str:
    if not raw_reg:
        return "UNKNOWN"
    clean = raw_reg.lower().strip()
    clean = clean.replace("u5", "us").replace("ap5", "aps").replace("10", "1b")
    for prefix, friendly in REGION_MAP.items():
        if clean.startswith(prefix):
            return f"{friendly} ({clean.upper()})"
    if clean.startswith("us"):
        return f"US ({clean.upper()})"
    if clean.startswith("eu"):
        return f"EU ({clean.upper()})"
    return clean.upper()







def translate_location(raw_loc: str, raw_planet: str = "") -> str:
    explicit = {
        "STANTON1_LORVILLE": "LORVILLE (HURSTON)",
        "STANTON3_AREA18": "AREA18 (ARCCORP)",
        "STANTON4_NEWBABBAGE": "NEW BABBAGE (MICROTECH)",
        "STANTON2_ORISON": "ORISON (CRUSADER)",
    }
    direct = (raw_loc or "").strip().upper()
    if direct in explicit:
        return explicit[direct]
    sorted_map = sorted(LOCATION_FRIENDLY_MAP.items(), key=lambda item: len(item[0]), reverse=True)

    candidate = (raw_loc or "").strip()
    if candidate:
        norm = re.sub(r'[^A-Za-z0-9_\-\s]', ' ', candidate).upper()
        norm = re.sub(r'\s+', ' ', norm).strip()
        norm = norm.replace("LE0", "LEO")
        # Log location names vary between spaces and underscores. Never resolve
        # numeric inventory IDs through the old hardcoded station guesses.
        if norm.isdigit():
            return "UNKNOWN"
        for k, v in sorted_map:
            if k.replace("_", " ") in norm.replace("_", " "):
                return v
        if len(norm) >= 3:
            return norm[:28]

    if raw_planet:
        p = raw_planet.upper().replace("00C", "OOC").replace("5TANTON", "STANTON")
        p = re.sub(r'OOC[\s_]*', '', p)
        p = p.replace("_", " ").strip()
        for k, v in sorted_map:
            if k in p:
                return v
        parts = [tok for tok in p.split() if tok not in ("STANTON", "OOC", "LOAD", "COMPLETE")]
        if parts:
            return " ".join(parts)[-26:]
    return "DEEP SPACE"


class FastDisplayInfoBitmapReader:
    """
    Legacy bitmap experiment retained for word anchors and comparison probes.
    Its digit atlas misclassifies live readings. Production numeric recognition
    uses ValidatedDisplayInfoReader; do not use this class as an accurate feed.
    """
    def __init__(self, atlas_path=GLYPH_ATLAS_FILE):
        self.loaded = False
        self.digits = {}
        self.kw = {}
        self._prev_srv_strip = None
        self._cached_srv_info = {}
        self._load_atlas(atlas_path)

    def _load_atlas(self, atlas_path):
        if not os.path.exists(atlas_path):
            return
        try:
            atlas = np.load(atlas_path)
            for k in ("kw_fps", "kw_sfps", "kw_game", "kw_restarts", "kw_shard", "kw_srv", "kw_ping", "kw_rl_ent", "kw_ent"):
                if k in atlas:
                    self.kw[k] = atlas[k].astype(np.float32)
            for d in range(10):
                dk = f"d_{d}"
                if dk in atlas:
                    self.digits[str(d)] = atlas[dk].astype(np.float32)
            self.loaded = bool(self.digits and "kw_sfps" in self.kw)
        except Exception:
            self.loaded = False

    def _read_number(self, strip_9px, is_float=False):
        if strip_9px is None or strip_9px.shape[0] < 9 or strip_9px.shape[1] < 6:
            return None
        hits = []
        for ch, t_arr in self.digits.items():
            best_map = np.max([cv2.matchTemplate(strip_9px, t, cv2.TM_CCOEFF_NORMED)[0] for t in t_arr], axis=0)
            for x in np.where(best_map >= 0.72)[0]:
                hits.append((int(x), float(best_map[x]), ch))
        if not hits:
            return None
        hits.sort(key=lambda h: -h[1])
        kept = []
        for x, sc, ch in hits:
            if all(abs(x - kx) >= 4 for kx, _, _ in kept):
                kept.append((x, sc, ch))
        kept.sort(key=lambda h: h[0])

        out = [kept[0][2]]
        for i in range(1, len(kept)):
            dx = kept[i][0] - kept[i - 1][0]
            if dx > 16:
                break
            if is_float and 10 <= dx <= 16 and "." not in out:
                out.append(".")
            out.append(kept[i][2])
        s = "".join(out)
        try:
            return float(s) if is_float else int(s)
        except Exception:
            return None

    def _read_all_numbers(self, strip_9px):
        if strip_9px is None or strip_9px.shape[0] < 9 or strip_9px.shape[1] < 6:
            return []
        hits = []
        for ch, t_arr in self.digits.items():
            best_map = np.max([cv2.matchTemplate(strip_9px, t, cv2.TM_CCOEFF_NORMED)[0] for t in t_arr], axis=0)
            for x in np.where(best_map >= 0.76)[0]:
                hits.append((int(x), float(best_map[x]), ch))
        if not hits:
            return []
        hits.sort(key=lambda h: -h[1])
        kept = []
        for x, sc, ch in hits:
            if all(abs(x - kx) >= 4 for kx, _, _ in kept):
                kept.append((x, sc, ch))
        kept.sort(key=lambda h: h[0])

        groups = []
        cur = []
        for h in kept:
            if not cur:
                cur.append(h)
            else:
                if (h[0] - cur[-1][0]) <= 18:
                    cur.append(h)
                else:
                    groups.append(cur)
                    cur = [h]
        if cur:
            groups.append(cur)

        nums = []
        for g in groups:
            s = [g[0][2]]
            has_dot = False
            for i in range(1, len(g)):
                dx = g[i][0] - g[i - 1][0]
                if 10 <= dx <= 18 and not has_dot:
                    s.append(".")
                    has_dot = True
                s.append(g[i][2])
            try:
                val_str = "".join(s)
                nums.append(float(val_str) if "." in val_str else int(val_str))
            except Exception:
                pass
        return nums

    def parse_image(self, pil_or_bgr, prev_state=None):
        state = dict(prev_state) if prev_state else {
            "server_fps": None,
            "client_fps": None,
            "region_raw": "",
            "region_display": "--",
            "server_name": "--",
            "shard_id": "--",
            "srv_id": "--",
            "shard_pop": None,
            "srv_pop": None,
            "callsign": "AWAITING TELEMETRY",
            "restarts": None,
            "ping_ms": None,
            "loss_pct": None,
            "bwin_kbps": None,
            "entities": None,
            "location_raw": "",
            "planet_raw": "",
            "location_display": "--",
            "hop_status": "",
            "region_shards_seen": 0,
            "detected_lines": 0,
            "max_y": 0,
            "last_seen_ts": 0
        }

        if not self.loaded or pil_or_bgr is None:
            return state

        try:
            if hasattr(pil_or_bgr, "convert"):
                arr = np.array(pil_or_bgr)
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
            else:
                gray = cv2.cvtColor(pil_or_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        except Exception:
            return state

        h_img, w_img = gray.shape[:2]
        if h_img < 120 or w_img < 400:
            return state

        # 1. Fast SIMD gate: find 'Server FPS' anchor in y=15..115 across full horizontal width
        kw_sfps = self.kw["kw_sfps"]
        roi_sfps = gray[15:min(115, h_img), :]
        m_sfps = cv2.matchTemplate(roi_sfps, kw_sfps, cv2.TM_CCOEFF_NORMED)
        if m_sfps.max() < 0.65:
            state["detected_lines"] = 0
            state["server_fps"] = None
            state["client_fps"] = None
            state["bwin_kbps"] = None
            state["loss_pct"] = None
            if self._cached_srv_info:
                state.update(self._cached_srv_info)
            return state

        dy, dx = np.unravel_index(np.argmax(m_sfps), m_sfps.shape)
        y_sfps = 15 + int(dy)
        x_sfps = int(dx) + kw_sfps.shape[1]

        sfps_val = self._read_number(gray[y_sfps:y_sfps + 9, x_sfps:min(w_img, x_sfps + 46)], is_float=True)
        if sfps_val is not None and 0.0 <= sfps_val <= 60.0:
            state["server_fps"] = sfps_val
        else:
            state["server_fps"] = None

        # 2. Client FPS (2 lines above Server FPS: y_sfps - 26)
        y_fps = max(2, y_sfps - 26)
        kw_fps = self.kw.get("kw_fps")
        if kw_fps is not None:
            m_fps = cv2.matchTemplate(gray[y_fps - 2:y_fps + 11, :], kw_fps, cv2.TM_CCOEFF_NORMED)
            if m_fps.max() > 0.55:
                fy, fx = np.unravel_index(np.argmax(m_fps), m_fps.shape)
                ry = y_fps - 2 + int(fy)
                rx = int(fx) + kw_fps.shape[1]
                cfps_val = self._read_number(gray[ry:ry + 9, rx:min(w_img, rx + 48)], is_float=True)
                if cfps_val is not None and 1.0 <= cfps_val <= 500.0:
                    state["client_fps"] = cfps_val

        # 3. Server / Shard Pop / Srv Pop / Restarts line (1 line below Server FPS: y_sfps + 13)
        # Format in Star Citizen: 'Server: pub-...-game-204, restarts 0, pop. [shard 61, srv 5]'
        y_srv_top = max(0, y_sfps + 6)
        y_srv_bot = min(h_img, y_sfps + 24)
        srv_band = gray[y_srv_top:y_srv_bot, :]
        if (
            self._prev_srv_strip is not None
            and self._prev_srv_strip.shape == srv_band.shape
            and float(np.mean(np.abs(srv_band - self._prev_srv_strip))) < 2.5
            and self._cached_srv_info
            and all(k in self._cached_srv_info for k in ("shard_pop", "srv_pop", "restarts"))
        ):
            state.update(self._cached_srv_info)
        else:
            new_srv_info = {}
            for key, kw_name, w_num in [
                ("game_num", "kw_game", 36),
                ("restarts", "kw_restarts", 28),
                ("shard_pop", "kw_shard", 34),
                ("srv_pop", "kw_srv", 28),
            ]:
                kw = self.kw.get(kw_name)
                if kw is None:
                    continue
                if srv_band.shape[1] < kw.shape[1] or srv_band.shape[0] < kw.shape[0]:
                    continue
                mk = cv2.matchTemplate(srv_band, kw, cv2.TM_CCOEFF_NORMED)
                if mk.max() > 0.48:
                    ky, kx = np.unravel_index(np.argmax(mk), mk.shape)
                    ry = y_srv_top + int(ky)
                    rx = int(kx) + kw.shape[1]
                    val = self._read_number(gray[ry:ry + 9, rx:min(w_img, rx + w_num)], is_float=False)
                    if val is not None:
                        if key == "game_num":
                            new_srv_info["server_name"] = f"GAME-{val}"
                            new_srv_info["srv_id"] = str(val)
                        elif key in ("shard_pop", "srv_pop", "restarts"):
                            new_srv_info[key] = int(val)
            if new_srv_info:
                self._prev_srv_strip = srv_band.copy()
                if self._cached_srv_info:
                    self._cached_srv_info.update(new_srv_info)
                else:
                    self._cached_srv_info = new_srv_info
                state.update(self._cached_srv_info)
            elif self._cached_srv_info:
                state.update(self._cached_srv_info)

        # 4. Ping line (2 lines below Server FPS: y_sfps + 24)
        y_ping = y_sfps + 24
        kw_ping = self.kw.get("kw_ping")
        if kw_ping is not None and (y_ping + 11) <= h_img:
            p_sub = gray[y_ping - 2:y_ping + 11, :]
            mp = cv2.matchTemplate(p_sub, kw_ping, cv2.TM_CCOEFF_NORMED)
            if mp.max() > 0.65:
                py, px = np.unravel_index(np.argmax(mp), mp.shape)
                ry = y_ping - 2 + int(py)
                rx = int(px) + kw_ping.shape[1]
                p_val = self._read_number(gray[ry:ry + 9, rx:min(w_img, rx + 48)], is_float=True)
                if p_val is not None and 1.0 <= p_val <= 3000.0:
                    state["ping_ms"] = p_val
                
                # Multi-number extraction on Net line: [ping, loss, bWin, bWOut]
                net_strip = gray[ry:ry + 9, rx:min(w_img, rx + 240)]
                net_nums = self._read_all_numbers(net_strip)
                if len(net_nums) >= 2:
                    state["loss_pct"] = float(net_nums[1])
                if len(net_nums) >= 3:
                    state["bwin_kbps"] = float(net_nums[2])

        # 5. Entities & vertical extent (check if r_DisplayInfo 3 full block is active)
        kw_ent = self.kw.get("kw_ent")
        max_y = y_sfps + 55
        if kw_ent is not None and h_img >= 305:
            e_sub = gray[270:min(315, h_img), :]
            me = cv2.matchTemplate(e_sub, kw_ent, cv2.TM_CCOEFF_NORMED)
            if me.max() > 0.65:
                ey, ex = np.unravel_index(np.argmax(me), me.shape)
                ry = 270 + int(ey)
                rx = int(ex) + kw_ent.shape[1]
                e_val = self._read_number(gray[ry:ry + 9, rx:min(w_img, rx + 50)], is_float=False)
                if e_val is not None:
                    state["entities"] = e_val
                max_y = ry + 32

        # If not connected to a live shard (e.g. main menu), server_fps is strictly None
        if state.get("shard_id") == "--" and state.get("server_name") == "--":
            state["server_fps"] = None

        state["detected_lines"] = 6
        state["max_y"] = max_y
        state["last_seen_ts"] = time.time()
        return state


