"""
SynthScan - Persistent Configuration & Multi-Monitor Manager
"""

import json
import os

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
    """Monitor geometry only. No graphics capture or pixel access."""
    try:
        import ctypes
        from ctypes import wintypes as w
        user=ctypes.WinDLL('user32',use_last_error=True)
        callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HMONITOR,w.HDC,ctypes.POINTER(w.RECT),w.LPARAM)
        monitors=[]
        @callback_type
        def visit(monitor,dc,rect,param):
            r=rect.contents
            monitors.append(dict(left=r.left,top=r.top,width=r.right-r.left,height=r.bottom-r.top,is_primary=r.left==0 and r.top==0))
            return True
        user.EnumDisplayMonitors.argtypes=[w.HDC,ctypes.POINTER(w.RECT),callback_type,w.LPARAM]
        if user.EnumDisplayMonitors(None,None,visit,0) and monitors:
            monitors.sort(key=lambda m:not m['is_primary'])
            return [dict(m,id=i) for i,m in enumerate(monitors,1)]
    except (OSError,AttributeError):pass
    return [{"id":1,"left":0,"top":0,"width":2560,"height":1440,"is_primary":True}]


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
