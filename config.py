"""
SynthScan - Persistent Configuration & Multi-Monitor Manager
"""

import json
import os
import mss

from installation import RELEASE,PROFILE
CONFIG_FILE = str(PROFILE/'config.json') if RELEASE else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

DEFAULT_CONFIG = {
    "mode": "auto",
    "poll_interval_ms": 350,
    "voice_enabled": True,
    "voice_volume": 100,
    "voice_rate": 1,
    "voice_profile": "origin",
    "voice_chime": True,
    "overlay_enabled": True,
    "overlay_x": 40,
    "overlay_y": 60,
    "overlay_opacity": 0.88,
    "game_monitor": 1,
    "ui_monitor": 2,
    "window_x": None,
    "window_y": None,
    "window_w": 1140,
    "window_h": 760,
    "screen_resolution": [2560, 1440],
    "scan_box_size": [700, 450],
    "tolerance": 60,
    "top_hud_enabled": True,
    "top_hud_compact": True,
    "hud_layout": "panel",
    "hud_scale": 1.0,
    "hud_position": {"x": 0.5, "y": 0.0},
    "top_hud_interval_ms": 750,
    "telemetry_capture_enabled": True,
    "top_hud_opacity": 0.70,
    "medical_imprint": "GRIM HEX"
}


def get_monitors():
    """
    Returns list of physical monitor dicts (1-indexed in mss, returned as 0-indexed list with 'id': 1, 2, ...).
    Each entry: {'id': idx, 'left': ..., 'top': ..., 'width': ..., 'height': ..., 'is_primary': ...}
    """
    try:
        with mss.MSS() as sct:
            mons = []
            for idx, m in enumerate(sct.monitors[1:], start=1):
                mons.append({
                    "id": idx,
                    "left": int(m.get("left", 0)),
                    "top": int(m.get("top", 0)),
                    "width": int(m.get("width", 2560)),
                    "height": int(m.get("height", 1440)),
                    "is_primary": bool(m.get("is_primary", idx == 1))
                })
            if mons:
                return mons
    except Exception:
        pass
    return [{"id": 1, "left": 0, "top": 0, "width": 2560, "height": 1440, "is_primary": True}]


def get_monitor_by_id(mon_id):
    mons = get_monitors()
    for m in mons:
        if m["id"] == mon_id:
            return m
    return mons[0]


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print("Failed to save config:", e)
