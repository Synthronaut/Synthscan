"""
SynthScan // Star Citizen Industrial MFD, Radar Signature Telemetry, Refinery Vault & SynthStrings Suite
Overhauled v2.0 - Multi-Monitor Native, Thread-Safe OCR, RSI / mobiGlas Building Blocks UI
"""

import os
import sys

_app_lock = _show_request = None
if __name__ == "__main__":
    from app_lifecycle import SingleInstance, Signal, send_signal
    _app_lock = SingleInstance()
    if not _app_lock.acquired:
        if "--autostart" not in sys.argv:
            send_signal("show")
        raise SystemExit(0)
    _show_request = Signal("show")

import time
import math
import ctypes
import datetime
import threading
import queue
import logging

logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthscan.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Ensure process always attaches to the user's visible interactive 'Default' desktop
# and uses 1:1 physical pixel coordinates (Per-Monitor DPI Aware) across mss and Tkinter.
try:
    _u32 = ctypes.windll.user32
    _h_desk = _u32.OpenDesktopW("Default", 0, False, 0x01FF)
    if _h_desk:
        _u32.SetThreadDesktop(_h_desk)
except Exception:
    pass

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw, ImageGrab

from config import load_config, save_config, get_monitors, get_monitor_by_id
from radar_db import parse_signature, match_summary, reference_groups
from voice import VoiceEngine, SHIP_VOICE_PROFILES
from detector import SignatureDetector, is_star_citizen_foreground
from overlay import HUDOverlay
from telemetry_hud import TopTelemetryHUD
from window_telemetry_capture import WindowTelemetryCapture, game_window_handle
from refinery_db import (
    load_inventory,
    save_inventory,
    add_haul_record,
    clear_inventory,
    delete_single_ore as db_delete_single_ore,
    compute_total_value,
    parse_refinery_image,
    get_ore_batches,
    get_ore_quality_summary,
    ORE_CATALOG
)
from crafting_db import (
    load_recipes,
    craft_item,
    add_custom_recipe,
    delete_recipe
)
from blueprint_db import (
    BlueprintManager,
    parse_fabricator_screen
)
from synthstrings_sync import (
    sync_blueprints_to_global_ini,
    restore_synthstrings_backup
)
from patch_engine import (
    get_current_game_version,
    apply_all_rules_and_adapt,
    PatchWatcher
)
from server_log_manager import ServerLogManager, format_duration


# --- ANTI-GRAVITY BRUSHED METAL & TITANIUM AVIONICS PALETTE ---
# Tactile, precision-machined industrial aesthetics with subtle metallic depth.
# Replaces generic neon-blue sci-fi templates with rich, polished gunmetal, titanium, and stainless steel.
SC_BG_ABYSS     = "#0f1115"   # Deep matte gunmetal chassis void
SC_BG_HEADER    = "#14171d"   # Machined titanium command header
SC_BG_RAIL      = "#12151b"   # Tactical avionics sidebar column
SC_BG_PANEL     = "#181b22"   # Core instrument viewport background
SC_BG_CARD      = "#1e222a"   # Cast dark alloy chassis card
SC_BG_CARD_ALT  = "#262b35"   # Elevated brushed steel surface / tactile pill
SC_BG_CARD_HOVER= "#313744"   # Satin metal hover sheen
SC_BORDER_CYAN  = "#566275"   # Crisp brushed steel / polished aluminum edge highlight
SC_BORDER_DIM   = "#2c323e"   # Subtle beveled steel casing frame border
SC_BORDER_MED   = "#3f4756"   # Medium brushed alloy bevel
SC_TEXT_BRIGHT  = "#f8fafc"   # Crisp polished silver/white readout
SC_TEXT_CYAN    = "#d0d7e2"   # Satin aluminum primary instrumentation text
SC_TEXT_AMBER   = "#d99b43"   # Warm industrial tungsten gold / quantum ore
SC_TEXT_GREEN   = "#48bb78"   # Calibrated avionics green (online/complete)
SC_TEXT_RED     = "#e05260"   # Precision hazard coral-crimson (alert/insufficient)
SC_TEXT_MUTED   = "#7e889b"   # Machined titanium secondary technical label
SC_TEXT_FAINT   = "#4a5363"   # Laser-etched chassis markings & ticks

FONT_TECH = "Bahnschrift"
FONT_MONO = "Consolas"





class SynthScanApp:
    def __init__(self, start_hidden=False):
        self._starting_hidden = start_hidden
        # Set process priority to BELOW_NORMAL_PRIORITY_CLASS (0x00004000) so StarCitizen.exe
        # always preempts SynthScan with zero frame hitches.
        try:
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
        except Exception:
            pass

        self.cfg = load_config()
        self.is_running = True
        self.is_scanning = False  # Default Mining Reticle OCR to STANDBY so 0% CPU is used unless actively mining!
        self.last_detected_sig = 0
        self.last_spoken_sig = 0
        self.last_match = None
        self.last_match_time = 0
        self.radar_sweep_angle = 0
        self.purge_confirm_armed = False
        self.restore_confirm_armed = False
        self.comms_history = []

        self.monitors = get_monitors()
        # Default UI to Monitor 2 if 2+ monitors exist, Game to Monitor 1
        if len(self.monitors) >= 2 and self.cfg.get("ui_monitor") not in [m["id"] for m in self.monitors]:
            self.cfg["ui_monitor"] = 2
        elif len(self.monitors) == 1:
            self.cfg["ui_monitor"] = 1

        if self.cfg.get("game_monitor") not in [m["id"] for m in self.monitors]:
            self.cfg["game_monitor"] = 1

        self.bp_manager = BlueprintManager()

        # 1. Initialize Main CTk Root FIRST (Single Tk root eliminates dual-root bugs!)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk(fg_color=SC_BG_ABYSS)
        if start_hidden:
            self.root.withdraw()
        self.root.title("SYNTHSCAN // UEE INDUSTRIAL & RADAR MFD v2.0")
        self.root.minsize(1020, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.root.report_callback_exception = self._report_callback_exception

        self._apply_initial_window_geometry()

        # 2. Initialize Subsystems (HUDOverlay and TopTelemetryHUD are Toplevels of self.root)
        self.server_logger = ServerLogManager()
        self.top_hud = TopTelemetryHUD(
            master=self.root,
            game_monitor=self.cfg.get("game_monitor", 1),
            enabled=self.cfg.get("top_hud_enabled", True),
            opacity=self.cfg.get("top_hud_opacity", 0.70),
            server_logger=self.server_logger
        )
        self.root.app_instance = self
        self.last_top_hud_poll = 0.0
        self.last_loading_ocr_scan = 0.0
        self.telemetry_queue = queue.Queue(maxsize=2)
        self.ui_events = queue.SimpleQueue()
        self.telemetry_stop = threading.Event()
        try:
            self.top_hud.bar_win.update()
        except Exception:
            pass

        self.voice = VoiceEngine(
            enabled=self.cfg.get("voice_enabled", True),
            volume=self.cfg.get("voice_volume", 80),
            rate=self.cfg.get("voice_rate", 1),
            profile=self.cfg.get("voice_profile", "origin"),
            chime_enabled=self.cfg.get("voice_chime", True)
        )
        self.top_hud.on_health_alert_cb = lambda msg: self.voice.speak(msg, cooldown=90.0, allow_when_game_closed=False, category="health_alert")

        self.overlay = HUDOverlay(
            master=self.root,
            x=self.cfg.get("overlay_x", 40),
            y=self.cfg.get("overlay_y", 60),
            opacity=self.cfg.get("overlay_opacity", 0.88),
            visible=self.cfg.get("overlay_enabled", True) and self.top_hud.layout=='ribbon',
            game_monitor=self.cfg.get("game_monitor", 1)
        )

        self.top_hud.on_preferences_changed = self._hud_preferences_changed

        self.detector = SignatureDetector(
            screen_res=tuple(self.cfg.get("screen_resolution", [2560, 1440])),
            box_size=(520, 320),
            game_monitor=self.cfg.get("game_monitor", 1),
            require_game_focus=True
        )

        from refinery_orders import RefineryOrderBook
        self.refinery_orders = RefineryOrderBook()
        self.terminal_tracking = self.cfg.get('terminal_tracking', True)
        self.terminal_station = self.cfg.get('terminal_station', '')
        from fabricator_inbox import FabricatorInbox
        self.fabricator_inbox = FabricatorInbox()
        self.fabricator_pending = self.fabricator_inbox.pending
        from mining_loadout import load_fit
        self.native_fit = None
        self.native_reader_status = 'Native mining reader ready; start scanning to load it.'
        self.native_rock = None
        self.native_detected_fit = None
        try:
            self.native_fit = load_fit()
        except (OSError,ValueError) as exc:
            self.native_reader_status = 'Saved loadout could not be read; original file preserved: '+str(exc)
        self.last_terminal_scan = 0.0
        self.terminal_job_lock = threading.Lock()

        # 3. Build Star Citizen MFD GUI
        self._build_mfd_shell()
        self.switch_page("home")

        # Track window movement to persist monitor placement
        self.root.bind("<Configure>", self._on_window_configure)

        # 4. Start Background Scanner Thread
        self.scan_thread = threading.Thread(target=self._scanner_loop, daemon=True)
        self.scan_thread.start()
        self.hud_capture_thread = threading.Thread(target=self._hud_capture_loop, daemon=True)
        self.hud_capture_thread.start()

        # 5. Start UI Telemetry & Radar Sweep Tick
        self.root.after(80, self._telemetry_tick)

        # 6. Initialize System Tray Icon
        self._init_tray()

        # 7. Start Blueprint Game Log Watcher
        self.bp_manager.start_game_log_watcher(self._on_live_blueprint_unlocked)

        # 8. Start Game Version & Patch Auto-Adapt Sentinel
        self.patch_watcher = PatchWatcher()
        self.patch_watcher.start(on_patch_detected_cb=self._on_game_patch_detected, interval_sec=3600)

        mon_count = len(self.monitors)
        ui_mon = self.cfg.get("ui_monitor", 1)
        gm_mon = self.cfg.get("game_monitor", 1)
        self.log_comms(
            f"MFD ONLINE // {mon_count} DISPLAY(S) LINKED // UI ON MON {ui_mon} // GAME CAPTURE ON MON {gm_mon}",
            level="ok"
        )
        self._starting_hidden = False
        logging.info("SynthScan ready: compact HUD=%s, background launch=%s", self.top_hud.compact, start_hidden)

    def _report_callback_exception(self, kind, value, tb):
        logging.error("UI action failed", exc_info=(kind, value, tb))
        if hasattr(self, "comms_history"):
            self.log_comms("ACTION FAILED // Details saved in synthscan.log", level="error")

    def toggle_compact_hud(self):
        self.cfg["top_hud_compact"] = not self.top_hud.compact
        self.top_hud.set_compact(self.cfg["top_hud_compact"])
        save_config(self.cfg)

    def toggle_game_autolaunch(self):
        from auto_launch import install, uninstall, shortcut_path
        if shortcut_path().exists():
            uninstall()
        else:
            install()

    # =========================================================================
    # MULTI-MONITOR WINDOW PLACEMENT & ROUTING
    # =========================================================================
    def _apply_initial_window_geometry(self):
        self.monitors = get_monitors()
        w = int(self.cfg.get("window_w", 1140))
        h = int(self.cfg.get("window_h", 760))
        scale = self.root._get_window_scaling()
        if self.cfg.get("window_geometry_units") != "logical":
            # Old saves used physical sizes, which CTk scaled a second time on
            # every launch. Keep sizes logical and screen positions physical.
            w, h = round(w / scale), round(h / scale)
            self.cfg["window_geometry_units"] = "logical"
        target = get_monitor_by_id(self.cfg.get("ui_monitor", 1))
        w = max(1020, min(w, int((target["width"] - 40) / scale)))
        h = max(680, min(h, int((target["height"] - 80) / scale)))
        saved_x = self.cfg.get("window_x")
        saved_y = self.cfg.get("window_y")

        # Check if saved_x/saved_y is valid and on the desired UI monitor (or if user explicitly placed it)
        if saved_x is not None and saved_y is not None:
            # Verify coordinate is within total virtual screen bounds
            min_x = min(m["left"] for m in self.monitors)
            max_x = max(m["left"] + m["width"] for m in self.monitors)
            min_y = min(m["top"] for m in self.monitors)
            max_y = max(m["top"] + m["height"] for m in self.monitors)
            # If user has 2 monitors and saved_x was stuck on Monitor 1 (0..2560) from old config, move to Monitor 2
            if len(self.monitors) >= 2 and self.cfg.get("ui_monitor", 2) == 2 and saved_x < self.monitors[1]["left"]:
                self._center_on_monitor(2, w, h, save=False)
                return
            if min_x - 100 <= saved_x <= max_x - 100 and min_y - 50 <= saved_y <= max_y - 100:
                saved_x = min(max(target["left"] + 16, saved_x), target["left"] + target["width"] - round(w * scale) - 16)
                saved_y = min(max(target["top"] + 16, saved_y), target["top"] + target["height"] - round(h * scale) - 48)
                self.root.geometry(f"{w}x{h}+{int(saved_x)}+{int(saved_y)}")
                if not self._starting_hidden:
                    self.root.deiconify()
                return

        target_mon = 2 if len(self.monitors) >= 2 else 1
        self._center_on_monitor(target_mon, w, h, save=False)

    def _center_on_monitor(self, mon_id, w=None, h=None, save=True):
        mon = get_monitor_by_id(mon_id)
        scale = self.root._get_window_scaling()
        if w is None:
            w = max(1020, round(self.root.winfo_width() / scale) if self.root.winfo_width() > 400 else int(self.cfg.get("window_w", 1140)))
        if h is None:
            h = max(680, round(self.root.winfo_height() / scale) if self.root.winfo_height() > 300 else int(self.cfg.get("window_h", 760)))
        w = min(w, int((mon["width"] - 40) / scale))
        h = min(h, int((mon["height"] - 80) / scale))

        x = mon["left"] + max(20, (mon["width"] - round(w * scale)) // 2)
        y = mon["top"] + max(20, (mon["height"] - round(h * scale)) // 2)

        self.cfg["ui_monitor"] = mon["id"]
        self.cfg["window_x"] = x
        self.cfg["window_y"] = y
        self.cfg["window_w"] = w
        self.cfg["window_h"] = h
        self.cfg["window_geometry_units"] = "logical"
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        if not self._starting_hidden:
            self.root.deiconify()
            self.root.lift()

        if save:
            save_config(self.cfg)
            self._refresh_monitor_buttons()
            self.log_comms(f"UI DECK RELOCATED TO MONITOR {mon['id']} ({mon['width']}x{mon['height']} @ X={mon['left']})", level="info")
            if hasattr(self, "mon_diagram_canvas"):
                self._draw_monitor_diagram()

    def set_game_monitor(self, mon_id):
        mon = get_monitor_by_id(mon_id)
        self.cfg["game_monitor"] = mon["id"]
        self.cfg["screen_resolution"] = [mon["width"], mon["height"]]
        self.detector.set_game_monitor(mon["id"])
        self.overlay.set_game_monitor(mon["id"])
        self.top_hud.set_game_monitor(mon["id"])
        save_config(self.cfg)
        self._refresh_monitor_buttons()
        if hasattr(self, "mon_diagram_canvas"):
            self._draw_monitor_diagram()
        self.log_comms(f"STAR CITIZEN TARGET LOCKED TO MONITOR {mon['id']} ({mon['width']}x{mon['height']})", level="ok")

    def _detect_current_ui_monitor(self):
        try:
            cx = self.root.winfo_x() + (self.root.winfo_width() // 2)
            cy = self.root.winfo_y() + (self.root.winfo_height() // 2)
            for m in self.monitors:
                if m["left"] <= cx < (m["left"] + m["width"]) and m["top"] <= cy < (m["top"] + m["height"]):
                    return m["id"]
        except Exception:
            pass
        return self.cfg.get("ui_monitor", 1)

    def _on_window_configure(self, event):
        if event.widget is self.root:
            if getattr(self, "_win_conf_after_id", None):
                try:
                    self.root.after_cancel(self._win_conf_after_id)
                except Exception:
                    pass
            self._win_conf_after_id = self.root.after(300, self._apply_window_configure)

    def _apply_window_configure(self):
        try:
            if self.root.state() == "normal":
                x, y = self.root.winfo_x(), self.root.winfo_y()
                w, h = self.root.winfo_width(), self.root.winfo_height()
                if w >= 800 and h >= 500:
                    self.cfg["window_x"] = x
                    self.cfg["window_y"] = y
                    scale = self.root._get_window_scaling()
                    self.cfg["window_w"] = round(w / scale)
                    self.cfg["window_h"] = round(h / scale)
                    self.cfg["window_geometry_units"] = "logical"
                    cur_mon = self._detect_current_ui_monitor()
                    if cur_mon != self.cfg.get("ui_monitor"):
                        self.cfg["ui_monitor"] = cur_mon
                        self._refresh_monitor_buttons()
                        if hasattr(self, "mon_diagram_canvas"):
                            self._draw_monitor_diagram()
        except Exception:
            pass

    def _spawn_centered_toplevel(self, title, width, height):
        top = ctk.CTkToplevel(self.root)
        top.title(title)
        top.configure(fg_color=SC_BG_PANEL)
        top.transient(self.root)
        top.wm_attributes("-topmost", True)
        top.resizable(False, False)
        try:
            self.root.update_idletasks()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            scale = top._get_window_scaling()
            tx = rx + max(10, (rw - round(width * scale)) // 2)
            ty = ry + max(10, (rh - round(height * scale)) // 2)
            top.geometry(f"{width}x{height}+{tx}+{ty}")
        except Exception:
            top.geometry(f"{width}x{height}")
        top.lift()
        top.focus_force()
        return top

    # =========================================================================
    # STAR CITIZEN MFD SHELL (HEADER, LEFT RAIL, VIEWPORT, COMMS FOOTER)
    # =========================================================================
    def _build_mfd_shell(self):
        # 1. TOP TELEMETRY COMMAND BAR
        self.header_frame = ctk.CTkFrame(
            self.root,
            fg_color=SC_BG_HEADER,
            corner_radius=0,
            height=62,
            border_width=1,
            border_color=SC_BORDER_DIM
        )
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        # Left Brand & Designation
        brand_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        brand_box.pack(side="left", padx=(14, 10), pady=6)

        # Little Canvas Holo Emblem
        emblem = tk.Canvas(brand_box, width=36, height=36, bg=SC_BG_HEADER, highlightthickness=0)
        emblem.pack(side="left", padx=(0, 10))
        emblem.create_polygon(18, 3, 33, 11, 33, 25, 18, 33, 3, 25, 3, 11, outline="#657388", fill="#222731", width=2)
        emblem.create_oval(13, 13, 23, 23, outline="#d99b43", width=1.5)
        emblem.create_line(18, 2, 18, 10, fill="#8896aa", width=1)
        emblem.create_line(18, 26, 18, 34, fill="#8896aa", width=1)

        title_col = ctk.CTkFrame(brand_box, fg_color="transparent")
        title_col.pack(side="left")
        ctk.CTkLabel(
            title_col,
            text="SYNTHSCAN  //  INDUSTRIAL MFD",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            text_color=SC_TEXT_BRIGHT
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col,
            text="SYS.VER 2.0  •  RADAR TELEMETRY & REFINERY VAULT",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w")

        # Right Quick Controls (Radar Pause, Monitor Switcher, Clock)
        right_hdr = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        right_hdr.pack(side="right", padx=10, pady=8)

        # Shard Quick-Tag & Server Name in header
        cur_active = self.server_logger.get_active_session()
        init_name = (cur_active.get("server_name") if cur_active else "TAG SHARD") or "TAG SHARD"
        if len(init_name) > 14:
            init_name = init_name[:12] + ".."
        self.btn_hdr_shard = ctk.CTkButton(
            right_hdr,
            text=f"🏷️ {init_name}",
            command=self.open_tag_shard_dialog,
            fg_color="#262b35",
            hover_color="#343c4a",
            border_width=1,
            border_color="#4f596b",
            text_color="#d0d7e2",
            corner_radius=4,
            width=120,
            height=32,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold")
        )
        self.btn_hdr_shard.pack(side="left", padx=(0, 6))

        # A user-maintained note; the game does not supply an active imprint.
        self.btn_hdr_med = ctk.CTkButton(
            right_hdr,
            text="🏥 RESPAWN NOTE",
            command=self.open_set_medical_imprint_dialog,
            fg_color="#18231c",
            hover_color="#223227",
            border_width=1,
            border_color="#2f573c",
            text_color="#48bb78",
            corner_radius=4,
            width=120,
            height=32,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold")
        )
        self.btn_hdr_med.pack(side="left", padx=(0, 8))

        # Monitor Snap Controls right in the header!
        mon_strip = ctk.CTkFrame(right_hdr, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        mon_strip.pack(side="left", padx=(0, 10), ipady=2)

        ctk.CTkLabel(
            mon_strip,
            text="UI DECK:",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_MUTED
        ).pack(side="left", padx=(8, 4))

        self.btn_hdr_mon1 = ctk.CTkButton(
            mon_strip,
            text="MON 1",
            width=58,
            height=26,
            corner_radius=3,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=lambda: self._center_on_monitor(1)
        )
        self.btn_hdr_mon1.pack(side="left", padx=2, pady=3)

        self.btn_hdr_mon2 = ctk.CTkButton(
            mon_strip,
            text="MON 2",
            width=58,
            height=26,
            corner_radius=3,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=lambda: self._center_on_monitor(2 if len(self.monitors) >= 2 else 1)
        )
        self.btn_hdr_mon2.pack(side="left", padx=(2, 6), pady=3)

        # Voice Mute & Volume Strip in Header
        voice_strip = ctk.CTkFrame(right_hdr, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        voice_strip.pack(side="left", padx=(0, 10), ipady=2)

        cur_voice_on = bool(self.cfg.get("voice_enabled", True))
        cur_vol = int(self.cfg.get("voice_volume", 80))

        self.btn_hdr_mute = ctk.CTkButton(
            voice_strip,
            text=f"🔊 {cur_vol}%" if cur_voice_on and cur_vol > 0 else "🔇 MUTED",
            width=68,
            height=26,
            corner_radius=3,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            fg_color="#262b35" if cur_voice_on and cur_vol > 0 else "#2a1619",
            hover_color="#343c4a" if cur_voice_on and cur_vol > 0 else "#381d22",
            text_color=SC_TEXT_CYAN if cur_voice_on and cur_vol > 0 else SC_TEXT_RED,
            border_width=1,
            border_color="#4f596b" if cur_voice_on and cur_vol > 0 else "#5a2930",
            command=self.toggle_voice_mute
        )
        self.btn_hdr_mute.pack(side="left", padx=(4, 2), pady=3)

        self.slider_hdr_vol = ctk.CTkSlider(
            voice_strip,
            from_=0,
            to=100,
            width=70,
            height=16,
            progress_color=SC_TEXT_AMBER,
            command=self.on_hdr_volume_change
        )
        self.slider_hdr_vol.set(cur_vol)
        self.slider_hdr_vol.pack(side="left", padx=(2, 6), pady=3)

        # Radar Status & Toggle Button (Starts in STANDBY for 0% idle CPU overhead)
        self.btn_toggle_scan = ctk.CTkButton(
            right_hdr,
            text="○ RADAR: STANDBY",
            command=self.toggle_scanning,
            fg_color="#20242c",
            hover_color="#292e38",
            border_width=1,
            border_color="#3a4250",
            text_color=SC_TEXT_MUTED,
            corner_radius=4,
            width=135,
            height=32,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold")
        )
        self.btn_toggle_scan.pack(side="left", padx=(6, 0))

        self._refresh_monitor_buttons()

        # 2. BOTTOM COMMS & TELEMETRY TICKER BAR (Replaces intrusive popups!)
        self.footer_frame = ctk.CTkFrame(
            self.root,
            fg_color=SC_BG_HEADER,
            corner_radius=0,
            height=38,
            border_width=1,
            border_color=SC_BORDER_DIM
        )
        self.footer_frame.pack(fill="x", side="bottom")
        self.footer_frame.pack_propagate(False)

        self.lbl_comms_badge = ctk.CTkLabel(
            self.footer_frame,
            text="[ COMMS // OK ]",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=SC_TEXT_GREEN
        )
        self.lbl_comms_badge.pack(side="left", padx=(14, 8))

        self.lbl_comms_msg = ctk.CTkLabel(
            self.footer_frame,
            text="SYSTEM INITIALIZED. ALL SUBSYSTEMS NOMINAL.",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=SC_TEXT_BRIGHT
        )
        self.lbl_comms_msg.pack(side="left", padx=4)

        self.lbl_clock = ctk.CTkLabel(
            self.footer_frame,
            text="UEE TIME // --:--:--",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=SC_TEXT_MUTED
        )
        self.lbl_clock.pack(side="right", padx=14)

        sc_info = get_current_game_version()
        self.lbl_footer_build = ctk.CTkLabel(
            self.footer_frame,
            text=f"SC BUILD: {sc_info.get('build_num', 'LIVE')}  |  ",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=SC_TEXT_CYAN
        )
        self.lbl_footer_build.pack(side="right")

        # 3. MIDDLE BODY: LEFT MFD RAIL + MAIN VIEWPORT
        self.body_frame = ctk.CTkFrame(self.root, fg_color=SC_BG_ABYSS, corner_radius=0)
        self.body_frame.pack(fill="both", expand=True)

        # Left MFD Navigation Rail
        self.rail_frame = ctk.CTkFrame(
            self.body_frame,
            fg_color=SC_BG_RAIL,
            corner_radius=0,
            width=235,
            border_width=1,
            border_color=SC_BORDER_DIM
        )
        self.rail_frame.pack(side="left", fill="y")
        self.rail_frame.pack_propagate(False)

        ctk.CTkLabel(
            self.rail_frame,
            text="SYNTHSCAN",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(14, 6))

        self.nav_buttons = {}
        nav_list = ctk.CTkScrollableFrame(self.rail_frame, fg_color='transparent', corner_radius=0)
        nav_list.pack(fill='both', expand=True, pady=(0, 8))
        nav_specs = [
            ("home", "Home", "Choose your next task"),
            ("hud", "HUD layout", "Position, size & preview"),
            ("blueprints", "Library", "Items, materials & blueprints"),
            ("mining_planner", "Mining planner", "Locations & secondary ores"),
            ("refinery", "Materials & refinery", "Your ledger & scanned orders"),
            ("radar", "Mining scanner", "Recognize rock signatures"),
            ("servers", "Session history", "Shards, visits & notes"),
            ("crafting", "Custom crafting", "Your saved recipes & deductions"),
            ("performance", "Graphics lab", "Quality & frame pacing"),
            ("system", "Settings", "Monitors, HUD & voice"),
        ]

        for key, title, sub in nav_specs:
            btn_card = ctk.CTkFrame(
                nav_list,
                fg_color=SC_BG_CARD,
                corner_radius=4,
                border_width=1,
                border_color=SC_BORDER_DIM,
                cursor="hand2"
            )
            btn_card.pack(fill="x", padx=10, pady=4)

            indicator = ctk.CTkFrame(btn_card, width=4, height=44, fg_color=SC_BORDER_DIM, corner_radius=0)
            indicator.pack(side="left", fill="y")

            txt_frame = ctk.CTkFrame(btn_card, fg_color="transparent")
            txt_frame.pack(side="left", fill="both", expand=True, padx=10, pady=6)

            lbl_t = ctk.CTkLabel(
                txt_frame,
                text=title,
                font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
                text_color=SC_TEXT_BRIGHT,
                anchor="w"
            )
            lbl_t.pack(fill="x")

            lbl_s = ctk.CTkLabel(
                txt_frame,
                text=sub,
                font=ctk.CTkFont(family=FONT_MONO, size=9),
                text_color=SC_TEXT_MUTED,
                anchor="w"
            )
            lbl_s.pack(fill="x")

            for w in (btn_card, indicator, txt_frame, lbl_t, lbl_s):
                w.bind("<Button-1>", lambda e, k=key: self.switch_page(k))

            self.nav_buttons[key] = (btn_card, indicator, lbl_t, lbl_s)

        # Mini Live Radar Scope at bottom of Left Rail
        scope_box = ctk.CTkFrame(
            self.rail_frame,
            fg_color=SC_BG_CARD,
            corner_radius=4,
            border_width=1,
            border_color=SC_BORDER_DIM
        )
        # The full mining scanner owns the live scope. Keep the existing canvas
        # available to its update loop without crowding every page's navigation.

        ctk.CTkLabel(
            scope_box,
            text="// LIVE RETICLE TELEMETRY",
            font=ctk.CTkFont(family=FONT_MONO, size=9, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=10, pady=(6, 2))

        self.mini_radar_canvas = tk.Canvas(
            scope_box,
            width=195,
            height=130,
            bg="#0d0f14",
            highlightthickness=1,
            highlightbackground=SC_BORDER_DIM
        )
        self.mini_radar_canvas.pack(padx=10, pady=4)

        self.lbl_rail_sig = ctk.CTkLabel(
            scope_box,
            text="AWAITING PING...",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            text_color=SC_TEXT_BRIGHT
        )
        self.lbl_rail_sig.pack(padx=10, pady=(2, 0))

        self.lbl_rail_sub = ctk.CTkLabel(
            scope_box,
            text="TARGET: MON 1 RETICLE",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=SC_TEXT_MUTED
        )
        self.lbl_rail_sub.pack(padx=10, pady=(0, 8))

        # Main Viewport Container
        self.viewport = ctk.CTkFrame(
            self.body_frame,
            fg_color=SC_BG_PANEL,
            corner_radius=0
        )
        self.viewport.pack(side="left", fill="both", expand=True)
        self.viewport.grid_rowconfigure(0, weight=1)
        self.viewport.grid_columnconfigure(0, weight=1)

        # Build MFD pages inside self.viewport (lazy loading for instant UI startup!)
        self.pages = {}
        self._page_builders = {
            "home": self._build_page_home,
            "hud": self._build_page_hud,
            "refinery": self._build_page_refinery,
            "crafting": self._build_page_crafting,
            "blueprints": self._build_page_blueprints,
            "radar": self._build_page_radar,
            "servers": self._build_page_servers,
            "system": self._build_page_system,
            "performance": self._build_page_performance,
            "mining_planner": self._build_page_mining_planner,
        }
        for k in self._page_builders:
            f = ctk.CTkFrame(self.viewport, fg_color=SC_BG_PANEL, corner_radius=0)
            f.grid(row=0, column=0, sticky="nsew", padx=14, pady=12)
            self.pages[k] = f

        # Refinery widgets are also referenced by the existing status loop.
        self._build_page_refinery(self.pages["refinery"])
        self._built_pages = {"refinery"}

    def switch_page(self, page_key):
        if page_key in self._page_builders and page_key not in self._built_pages:
            self._page_builders[page_key](self.pages[page_key])
            self._built_pages.add(page_key)

        self.pages[page_key].tkraise()

        for k, (card, ind, lbl_t, lbl_s) in self.nav_buttons.items():
            if k == page_key:
                card.configure(fg_color=SC_BG_CARD_ALT, border_color="#657388")
                ind.configure(fg_color="#d8dee9")
                lbl_t.configure(text_color=SC_TEXT_BRIGHT)
                lbl_s.configure(text_color="#9aa5b5")
            else:
                card.configure(fg_color=SC_BG_CARD, border_color=SC_BORDER_DIM)
                ind.configure(fg_color=SC_BORDER_DIM)
                lbl_t.configure(text_color=SC_TEXT_MUTED)
                lbl_s.configure(text_color="#505866")

        if page_key == "system" and hasattr(self, "mon_diagram_canvas"):
            self._draw_monitor_diagram()

    def _build_page_performance(self, parent):
        from performance_lab_ui import PerformanceLabPage
        self.performance_lab_page = PerformanceLabPage(parent)

    def _refresh_monitor_buttons(self):
        ui_mon = self.cfg.get("ui_monitor", 1)
        if hasattr(self, "btn_hdr_mon1"):
            if ui_mon == 1:
                self.btn_hdr_mon1.configure(fg_color="#38404f", border_width=1, border_color="#657388", text_color=SC_TEXT_BRIGHT)
                self.btn_hdr_mon2.configure(fg_color=SC_BG_CARD, border_width=1, border_color=SC_BORDER_DIM, text_color=SC_TEXT_MUTED)
            else:
                self.btn_hdr_mon2.configure(fg_color="#38404f", border_width=1, border_color="#657388", text_color=SC_TEXT_BRIGHT)
                self.btn_hdr_mon1.configure(fg_color=SC_BG_CARD, border_width=1, border_color=SC_BORDER_DIM, text_color=SC_TEXT_MUTED)

    def log_comms(self, message, level="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        colors = {
            "ok":    (SC_TEXT_GREEN, "[ COMMS // NOMINAL ]"),
            "info":  (SC_TEXT_CYAN,  "[ COMMS // TELEMETRY ]"),
            "warn":  (SC_TEXT_AMBER, "[ COMMS // CAUTION ]"),
            "error": (SC_TEXT_RED,   "[ COMMS // ALERT ]")
        }
        col, badge = colors.get(level, (SC_TEXT_CYAN, "[ COMMS // INFO ]"))
        self.comms_history.insert(0, f"[{ts}] {badge} {message}")
        self.comms_history = self.comms_history[:50]

        def _apply():
            if hasattr(self, "lbl_comms_badge"):
                self.lbl_comms_badge.configure(text=badge, text_color=col)
                self.lbl_comms_msg.configure(text=f"{message}  ({ts})", text_color=SC_TEXT_BRIGHT if level != "error" else SC_TEXT_RED)
        self.root.after(0, _apply)

    # =========================================================================
    # PAGE 01: REFINERY VAULT & DIRECT OCR SCANNER
    # =========================================================================
    def _build_page_refinery(self, parent):
        from terminal_tracking_ui import TerminalTrackingPanel
        self.terminal_panel = TerminalTrackingPanel(parent, self)
        # Top Command Banner
        cmd_bar = ctk.CTkFrame(parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        cmd_bar.pack(fill="x", pady=(0, 10))

        left_cmd = ctk.CTkFrame(cmd_bar, fg_color="transparent")
        left_cmd.pack(side="left", padx=12, pady=10)

        self.btn_direct_snap = ctk.CTkButton(
            left_cmd,
            text="[ SCAN REFINERY TERMINAL ]",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            command=self.one_click_screen_capture,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color="#f8fafc",
            corner_radius=4,
            height=38,
            width=240
        )
        self.btn_direct_snap.pack(side="left", padx=(0, 10))

        btn_clip = ctk.CTkButton(
            left_cmd,
            text="PASTE CLIPBOARD",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            command=self.import_from_clipboard,
            fg_color=SC_BG_CARD_ALT,
            hover_color="#313744",
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color="#d0d7e2",
            corner_radius=4,
            height=38,
            width=140
        )
        btn_clip.pack(side="left", padx=4)

        btn_manual = ctk.CTkButton(
            left_cmd,
            text="+ MANUAL ORE ENTRY",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            command=self.open_manual_add_dialog,
            fg_color=SC_BG_CARD_ALT,
            hover_color="#313744",
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color="#d0d7e2",
            corner_radius=4,
            height=38,
            width=155
        )
        btn_manual.pack(side="left", padx=4)

        btn_history = ctk.CTkButton(
            left_cmd,
            text="📜 REFINED HAUL LOGS",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            command=self.open_refinery_history_dialog,
            fg_color=SC_BG_CARD_ALT,
            hover_color="#313744",
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color="#d0d7e2",
            corner_radius=4,
            height=38,
            width=175
        )
        btn_history.pack(side="left", padx=4)

        right_cmd = ctk.CTkFrame(cmd_bar, fg_color="transparent")
        right_cmd.pack(side="right", padx=12, pady=10)

        self.btn_purge_vault = ctk.CTkButton(
            right_cmd,
            text="PURGE VAULT",
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=self.on_clear_inventory,
            fg_color="#2a1619",
            hover_color="#381d22",
            border_width=1,
            border_color="#5a2930",
            text_color=SC_TEXT_RED,
            corner_radius=4,
            height=38,
            width=120
        )
        self.btn_purge_vault.pack(side="right")

        # 3 Telemetry KPI Cards
        kpi_row = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 10))

        def _make_kpi(col_parent, label, init_val, val_color):
            card = ctk.CTkFrame(col_parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
            card.pack(side="left", fill="both", expand=True, padx=4)
            accent_bar = ctk.CTkFrame(card, height=3, fg_color=val_color, corner_radius=0)
            accent_bar.pack(fill="x", side="top")
            ctk.CTkLabel(
                card,
                text=f"// {label}",
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                text_color=SC_TEXT_MUTED
            ).pack(anchor="w", padx=14, pady=(8, 0))
            val_lbl = ctk.CTkLabel(
                card,
                text=init_val,
                font=ctk.CTkFont(family=FONT_MONO, size=20, weight="bold"),
                text_color=val_color
            )
            val_lbl.pack(anchor="w", padx=14, pady=(2, 10))
            return val_lbl

        self.lbl_total_scu = _make_kpi(kpi_row, "TOTAL REFINED CARGO MASS", "0.00 SCU", SC_TEXT_CYAN)
        self.lbl_total_value = _make_kpi(kpi_row, "ESTIMATED UEE MARKET VALUE", "0 aUEC", SC_TEXT_AMBER)
        self.lbl_top_asset = _make_kpi(kpi_row, "PRIMARY HIGH-VALUE COMMODITY", "NONE", SC_TEXT_GREEN)

        # Ore Vault Table Container
        vault_frame = ctk.CTkFrame(parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        vault_frame.pack(fill="both", expand=True)

        # Table Column Headers
        hdr_row = ctk.CTkFrame(vault_frame, fg_color=SC_BG_HEADER, corner_radius=0, height=34)
        hdr_row.pack(fill="x", padx=2, pady=(2, 0))
        hdr_row.pack_propagate(False)

        ctk.CTkLabel(hdr_row, text="  COMMODITY DESIGNATION", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=210, anchor="w").pack(side="left", padx=8)
        ctk.CTkLabel(hdr_row, text="CLASSIFICATION", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=110, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(hdr_row, text="VAULT RATIO", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=160, anchor="w").pack(side="left", padx=8)
        ctk.CTkLabel(hdr_row, text="DEL", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=40, anchor="center").pack(side="right", padx=12)
        ctk.CTkLabel(hdr_row, text="EST. VALUE (aUEC)", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=140, anchor="e").pack(side="right", padx=10)
        ctk.CTkLabel(hdr_row, text="VOLUME (SCU)", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED, width=110, anchor="e").pack(side="right", padx=10)

        self.ore_scroll = ctk.CTkScrollableFrame(vault_frame, fg_color=SC_BG_PANEL, corner_radius=0)
        self.ore_scroll.pack(fill="both", expand=True, padx=2, pady=2)

        self.refresh_inventory_ui()

    def one_click_screen_capture(self):
        """
        Captures the configured Star Citizen Game Monitor directly into memory and runs OCR on a worker thread.
        If SynthScan is on Monitor 2 while Game is on Monitor 1, the UI never even hides or flickers!
        """
        self.btn_direct_snap.configure(text="[ SCANNING TERMINAL... ]", state="disabled")
        ui_mon = self._detect_current_ui_monitor()
        gm_mon = self.cfg.get("game_monitor", 1)

        if ui_mon == gm_mon:
            # Only hide briefly if SynthScan is on the same screen as the game
            self.root.withdraw()
            self.root.after(140, lambda: self._start_refinery_capture_worker(restore_ui=True))
        else:
            self._start_refinery_capture_worker(restore_ui=False)

    def _start_refinery_capture_worker(self, restore_ui=False):
        try:
            shot = self.detector.grab_full_game_monitor_pil()
        except Exception as exc:
            self.btn_direct_snap.configure(text='[ SCAN REFINERY TERMINAL ]', state='normal')
            self.log_comms('TERMINAL CAPTURE FAILED: ' + str(exc), level='error')
            return
        finally:
            if restore_ui:
                self.root.deiconify()
        self.log_comms('READING WORK ORDERS; NO CARGO INVENTORY WILL BE CREDITED BY A SCREENSHOT.', level='info')
        def worker():
            try:
                result = self._read_terminal_image(shot)
            except Exception as exc:
                result = dict(error=str(exc), orders=[], blueprints=[])
            self.ui_events.put(('terminal_manual', result, None))
        threading.Thread(target=worker, daemon=True).start()


    def _apply_parsed_refinery_haul(self, parsed, source="TERMINAL"):
        if not parsed:
            self.log_comms("NO REFINERY ORE QUANTITIES DETECTED ON GAME SCREEN. ENSURE WORK ORDER / STORAGE IS VISIBLE.", level="warn")
            return

        add_haul_record(parsed, source=source)
        self.refresh_inventory_ui()
        self.refresh_crafting_ui()
        self.refresh_blueprints_ui()

        ores_summary = ", ".join(f"{scu:.1f} SCU {ore}" for ore, scu in parsed.items())
        self.voice.speak(f"Refinery haul logged: {ores_summary}", cooldown=0)
        self.log_comms(f"HAUL LOGGED ({source}): {ores_summary}", level="ok")

    def refresh_inventory_ui(self):
        for child in self.ore_scroll.winfo_children():
            child.destroy()

        inv = load_inventory()
        totals = inv.get("totals", {})
        total_scu, total_value = compute_total_value(totals)

        self.lbl_total_scu.configure(text=f"{total_scu:,.2f} SCU")
        self.lbl_total_value.configure(text=f"{total_value:,} aUEC")

        if totals:
            top_ore = max(totals.items(), key=lambda x: x[1] * ORE_CATALOG.get(x[0], {}).get("price", 0))
            self.lbl_top_asset.configure(text=f"{top_ore[0].upper()} ({top_ore[1]:.1f} SCU)")
        else:
            self.lbl_top_asset.configure(text="NONE")

        if not totals:
            empty_frame = ctk.CTkFrame(self.ore_scroll, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
            empty_frame.pack(fill="x", padx=20, pady=40)
            ctk.CTkLabel(
                empty_frame,
                text="// REFINERY ORE VAULT IS CURRENTLY EMPTY",
                font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"),
                text_color=SC_TEXT_CYAN
            ).pack(pady=(20, 4))
            ctk.CTkLabel(
                empty_frame,
                text="Add collected cargo manually here. Terminal scans track refinery stock separately under Work orders.",
                font=ctk.CTkFont(family=FONT_MONO, size=11),
                text_color=SC_TEXT_MUTED
            ).pack(pady=(0, 20))
            return

        sorted_ores = sorted(totals.items(), key=lambda x: x[1] * ORE_CATALOG.get(x[0], {}).get("price", 0), reverse=True)
        max_scu = max([scu for _, scu in sorted_ores] + [1.0])

        for ore, scu in sorted_ores:
            info = ORE_CATALOG.get(ore, {"color": SC_TEXT_CYAN, "tier": "Common", "price": 500})
            val = int(scu * info["price"])
            accent = info["color"]

            row = ctk.CTkFrame(self.ore_scroll, fg_color=SC_BG_CARD, corner_radius=3, border_width=1, border_color=SC_BORDER_DIM)
            row.pack(fill="x", padx=6, pady=3)

            # Left Rarity Accent Strip
            strip = ctk.CTkFrame(row, width=4, height=38, fg_color=accent, corner_radius=0)
            strip.pack(side="left", fill="y")

            # Ore Name & Quality Summary
            name_box = ctk.CTkFrame(row, fg_color="transparent", width=210)
            name_box.pack(side="left", padx=(12, 6), pady=3)
            ctk.CTkLabel(
                name_box,
                text=ore.upper(),
                font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
                text_color=SC_TEXT_BRIGHT,
                anchor="w"
            ).pack(anchor="w")
            qual_summary = get_ore_quality_summary(ore)
            if qual_summary:
                ctk.CTkLabel(
                    name_box,
                    text=qual_summary,
                    font=ctk.CTkFont(family=FONT_MONO, size=9),
                    text_color="#8c97a8",
                    anchor="w"
                ).pack(anchor="w")

            # Tier Pill
            tier_pill = ctk.CTkFrame(row, fg_color=SC_BG_CARD_ALT, corner_radius=3, width=95, height=22)
            tier_pill.pack(side="left", padx=6)
            tier_pill.pack_propagate(False)
            ctk.CTkLabel(
                tier_pill,
                text=info["tier"].upper(),
                font=ctk.CTkFont(family=FONT_MONO, size=9, weight="bold"),
                text_color=accent
            ).pack(expand=True)

            # Visual SCU Progress Bar
            pbar = ctk.CTkProgressBar(
                row,
                width=150,
                height=8,
                corner_radius=2,
                fg_color="#12151b",
                progress_color=accent
            )
            pbar.set(min(1.0, max(0.04, scu / max_scu)))
            pbar.pack(side="left", padx=12)

            # Delete button
            btn_del = ctk.CTkButton(
                row,
                text="✕",
                width=28,
                height=26,
                corner_radius=3,
                fg_color="#262b35",
                hover_color=SC_TEXT_RED,
                text_color=SC_TEXT_BRIGHT,
                command=lambda o=ore: self.delete_single_ore(o)
            )
            btn_del.pack(side="right", padx=10)

            # Market Value
            ctk.CTkLabel(
                row,
                text=f"{val:,} aUEC",
                font=ctk.CTkFont(family=FONT_MONO, size=12, weight="bold"),
                text_color=SC_TEXT_AMBER,
                width=140,
                anchor="e"
            ).pack(side="right", padx=10)

            # SCU Readout
            ctk.CTkLabel(
                row,
                text=f"{scu:,.2f} SCU",
                font=ctk.CTkFont(family=FONT_MONO, size=12, weight="bold"),
                text_color=SC_TEXT_CYAN,
                width=110,
                anchor="e"
            ).pack(side="right", padx=10)

    def import_from_clipboard(self):
        image = ImageGrab.grabclipboard()
        if not hasattr(image, 'convert'):
            self.log_comms('COPY A TERMINAL SCREENSHOT FIRST.', level='warn')
            return
        def worker():
            try:
                result = self._read_terminal_image(image)
            except Exception as exc:
                result = dict(error=str(exc), orders=[], blueprints=[])
            self.ui_events.put(('terminal_manual', result, None))
        threading.Thread(target=worker, daemon=True).start()


    def open_refinery_history_dialog(self):
        dialog = self._spawn_centered_toplevel("PERSISTENT REFINED MATERIAL HAUL LOG", 660, 520)

        top = ctk.CTkFrame(dialog, fg_color=SC_BG_CARD, corner_radius=0, height=48)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(
            top,
            text="// PERSISTENT REFINED MATERIAL HAUL LOGS",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(side="left", padx=16, pady=12)

        def _clear_history():
            inv = load_inventory()
            inv["history"] = []
            save_inventory(inv)
            self.log_comms("REFINERY HAUL HISTORY LOGS CLEARED.", level="warn")
            dialog.destroy()

        ctk.CTkButton(
            top,
            text="CLEAR LOGS",
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=_clear_history,
            fg_color="#2a1619",
            hover_color="#381d22",
            border_width=1,
            border_color="#5a2930",
            text_color=SC_TEXT_RED,
            height=28,
            width=100
        ).pack(side="right", padx=16, pady=10)

        log_scroll = ctk.CTkScrollableFrame(dialog, fg_color=SC_BG_PANEL, corner_radius=0)
        log_scroll.pack(fill="both", expand=True, padx=8, pady=8)

        inv = load_inventory()
        history = inv.get("history", [])

        if not history:
            empty_box = ctk.CTkFrame(log_scroll, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
            empty_box.pack(fill="x", padx=20, pady=40)
            ctk.CTkLabel(
                empty_box,
                text="// NO HAULS RECORDED YET",
                font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
                text_color=SC_TEXT_CYAN
            ).pack(pady=(20, 4))
            ctk.CTkLabel(
                empty_box,
                text="This view contains cargo haul history. Terminal observations and finished refinery stock are under Work orders.",
                font=ctk.CTkFont(family=FONT_MONO, size=11),
                text_color=SC_TEXT_MUTED
            ).pack(pady=(0, 20))
            return

        for entry in history:
            ts = entry.get("timestamp", "UNKNOWN TIME")
            src = entry.get("source", "MANUAL")
            is_craft = "Fabricated" in src or "Crafted" in src

            card = ctk.CTkFrame(log_scroll, fg_color=SC_BG_CARD, corner_radius=3, border_width=1, border_color=SC_BORDER_DIM)
            card.pack(fill="x", padx=4, pady=4)

            accent = SC_TEXT_AMBER if is_craft else SC_TEXT_GREEN
            strip = ctk.CTkFrame(card, width=4, height=44, fg_color=accent, corner_radius=0)
            strip.pack(side="left", fill="y")

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, padx=10, pady=6)

            top_line = ctk.CTkFrame(content, fg_color="transparent")
            top_line.pack(fill="x")

            ctk.CTkLabel(
                top_line,
                text=f"[{ts}] {src.upper()}",
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                text_color=SC_TEXT_BRIGHT
            ).pack(side="left")

            tot_scu = entry.get("total_scu", 0.0)
            tot_val = entry.get("total_value", 0)
            if tot_scu > 0:
                ctk.CTkLabel(
                    top_line,
                    text=f"{tot_scu:,.2f} SCU  //  {tot_val:,} aUEC",
                    font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                    text_color=SC_TEXT_CYAN
                ).pack(side="right")

            details = entry.get("details", [])
            batch_details = entry.get("batch_details", [])
            items = entry.get("items", {})

            item_lines = []
            if details:
                for d in details:
                    item_lines.append(f"{d.get('ore')}: {d.get('scu', 0.0):.2f} SCU [{d.get('quality', 850)} Q] (~{d.get('est_value', 0):,} aUEC)")
            elif batch_details:
                for b in batch_details:
                    item_lines.append(f"{b.get('ore')}: -{b.get('scu', 0.0):.2f} SCU [{b.get('quality', 850)} Q]")
            elif items:
                for o, q in items.items():
                    item_lines.append(f"{o}: {q:.2f} SCU")

            if item_lines:
                ctk.CTkLabel(
                    content,
                    text=" • " + "  |  ".join(item_lines),
                    font=ctk.CTkFont(family=FONT_MONO, size=10),
                    text_color="#9aa5b5",
                    anchor="w"
                ).pack(anchor="w", pady=(2, 0))

    def open_manual_add_dialog(self):
        dialog = self._spawn_centered_toplevel("MANUAL COMMODITY ENTRY // VAULT", 380, 340)

        ctk.CTkLabel(dialog, text="// MANUAL ORE DEPOSIT", font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"), text_color=SC_TEXT_CYAN).pack(anchor="w", padx=20, pady=(16, 8))

        ctk.CTkLabel(dialog, text="COMMODITY DESIGNATION:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(4, 2))
        combo_ore = ctk.CTkComboBox(dialog, values=sorted(list(ORE_CATALOG.keys())), width=320, font=ctk.CTkFont(family=FONT_MONO, size=12))
        combo_ore.set("Quantainium")
        combo_ore.pack(anchor="w", padx=20, pady=4)

        ctk.CTkLabel(dialog, text="VOLUME IN SCU:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(6, 2))
        entry_scu = ctk.CTkEntry(dialog, placeholder_text="e.g. 32.50", width=320, font=ctk.CTkFont(family=FONT_MONO, size=12))
        entry_scu.pack(anchor="w", padx=20, pady=4)

        ctk.CTkLabel(dialog, text="MATERIAL QUALITY RATING (0 - 1000):", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(6, 2))
        entry_qual = ctk.CTkEntry(dialog, placeholder_text="e.g. 910 or 800 (default: 850)", width=320, font=ctk.CTkFont(family=FONT_MONO, size=12))
        entry_qual.insert(0, "850")
        entry_qual.pack(anchor="w", padx=20, pady=4)

        def on_add():
            ore = combo_ore.get()
            try:
                scu = float(entry_scu.get().strip())
                if scu <= 0:
                    return
                try:
                    q_val = int(entry_qual.get().strip() or "850")
                except ValueError:
                    q_val = 850
                add_haul_record({ore: scu}, source="MANUAL", quality_map={ore: q_val})
                self.refresh_inventory_ui()
                self.refresh_crafting_ui()
                self.refresh_blueprints_ui()
                self.log_comms(f"DEPOSITED {scu:,.2f} SCU OF {ore.upper()} [{q_val} Q] TO VAULT.", level="ok")
                dialog.destroy()
            except ValueError:
                self.log_comms("INVALID SCU QUANTITY ENTERED.", level="error")

        ctk.CTkButton(
            dialog,
            text="[ COMMIT TO VAULT ]",
            command=on_add,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color="#f8fafc",
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            width=320,
            height=36
        ).pack(padx=20, pady=16)

    def delete_single_ore(self, ore_name):
        db_delete_single_ore(ore_name)
        self.refresh_inventory_ui()
        self.refresh_crafting_ui()
        self.refresh_blueprints_ui()
        self.log_comms(f"REMOVED {ore_name.upper()} FROM REFINERY VAULT.", level="info")

    def on_clear_inventory(self):
        if not self.purge_confirm_armed:
            self.purge_confirm_armed = True
            self.btn_purge_vault.configure(text="CONFIRM PURGE?", fg_color=SC_TEXT_RED, text_color=SC_TEXT_BRIGHT)
            self.log_comms("CLICK [ CONFIRM PURGE? ] AGAIN WITHIN 4 SECONDS TO WIPE ORE VAULT.", level="warn")
            self.root.after(4000, self._reset_purge_btn)
            return

        self.purge_confirm_armed = False
        self._reset_purge_btn()
        clear_inventory()
        self.refresh_inventory_ui()
        self.refresh_crafting_ui()
        self.refresh_blueprints_ui()
        self.log_comms("REFINERY ORE VAULT PURGED.", level="warn")

    def _reset_purge_btn(self):
        self.purge_confirm_armed = False
        if hasattr(self, "btn_purge_vault"):
            self.btn_purge_vault.configure(text="PURGE VAULT", fg_color="#2a0f18", text_color=SC_TEXT_RED)

    # =========================================================================
    # PAGE 02: FABRICATOR // CRAFT & DEDUCT
    # =========================================================================
    def _build_page_crafting(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        toolbar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            toolbar,
            text="// FABRICATOR SCHEMATICS & VAULT DEDUCTION",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(side="left", padx=14, pady=12)

        self.var_use_best_materials = tk.BooleanVar(master=self.root, value=True)

        self.btn_toggle_best_mat = ctk.CTkButton(
            toolbar,
            text="⭐ USE BEST MATERIALS: ACTIVE",
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=self._toggle_best_materials,
            fg_color="#38404f",
            hover_color="#414b5c",
            border_width=1,
            border_color="#657388",
            text_color=SC_TEXT_BRIGHT,
            height=34,
            width=230
        )
        self.btn_toggle_best_mat.pack(side="left", padx=12, pady=8)

        ctk.CTkButton(
            toolbar,
            text="+ NEW CUSTOM SCHEMATIC",
            command=self.open_custom_recipe_dialog,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            height=34,
            width=190
        ).pack(side="right", padx=12, pady=8)

        self.craft_scroll = ctk.CTkScrollableFrame(parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        self.craft_scroll.pack(fill="both", expand=True)

        self.refresh_crafting_ui()

    def _toggle_best_materials(self):
        curr = self.var_use_best_materials.get()
        new_val = not curr
        self.var_use_best_materials.set(new_val)
        if new_val:
            self.btn_toggle_best_mat.configure(
                text="⭐ USE BEST MATERIALS: ACTIVE",
                fg_color="#38404f",
                hover_color="#414b5c",
                border_color="#657388",
                text_color=SC_TEXT_BRIGHT
            )
            self.log_comms("FABRICATOR: 'USE BEST MATERIALS' ACTIVE (Consumes highest quality batches).", level="info")
        else:
            self.btn_toggle_best_mat.configure(
                text="🛡️ SAVE BEST MATERIALS: ACTIVE",
                fg_color="#2b2618",
                hover_color="#38301c",
                border_color="#7a6226",
                text_color=SC_TEXT_AMBER
            )
            self.log_comms("FABRICATOR: 'SAVE BEST MATERIALS' ACTIVE (Consumes lower quality batches first).", level="warn")
        self.refresh_crafting_ui()

    def refresh_crafting_ui(self):
        for child in self.craft_scroll.winfo_children():
            child.destroy()

        inv = load_inventory()
        totals = inv.get("totals", {})
        recipes = load_recipes()
        use_best_val = self.var_use_best_materials.get() if hasattr(self, "var_use_best_materials") else True

        categories = {}
        for r in recipes:
            cat = r.get("category", "General")
            categories.setdefault(cat, []).append(r)

        for cat_name, cat_recipes in categories.items():
            cat_header = ctk.CTkLabel(
                self.craft_scroll,
                text=f"// SECTOR: {cat_name.upper()}",
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                text_color=SC_TEXT_AMBER
            )
            cat_header.pack(anchor="w", padx=12, pady=(12, 4))

            for r in cat_recipes:
                card = tk.Frame(self.craft_scroll, bg=SC_BG_PANEL, highlightbackground=SC_BORDER_DIM, highlightthickness=1)
                card.pack(fill="x", padx=8, pady=4)

                left = tk.Frame(card, bg=SC_BG_PANEL)
                left.pack(side="left", fill="both", expand=True, padx=12, pady=8)

                ctk.CTkLabel(
                    left,
                    text=r["name"].upper(),
                    font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"),
                    text_color=SC_TEXT_BRIGHT
                ).pack(anchor="w")

                if r.get("desc"):
                    ctk.CTkLabel(
                        left,
                        text=r["desc"],
                        font=ctk.CTkFont(family=FONT_MONO, size=10),
                        text_color=SC_TEXT_MUTED
                    ).pack(anchor="w", pady=(1, 4))

                cost_box = tk.Frame(left, bg=SC_BG_PANEL)
                cost_box.pack(anchor="w")

                can_craft = True
                card_batch_selectors = {}

                for ore, req_scu in r.get("cost", {}).items():
                    avail = totals.get(ore, 0.0)
                    has_enough = avail >= req_scu
                    if not has_enough:
                        can_craft = False

                    status_color = SC_TEXT_GREEN if has_enough else SC_TEXT_RED
                    batches = get_ore_batches(ore)

                    # Pill container
                    pill = tk.Frame(cost_box, bg=SC_BG_CARD, highlightbackground=status_color, highlightthickness=1)
                    pill.pack(side="left", padx=(0, 8), pady=2)

                    distinct_qualities = list({b.get("quality", 850) for b in batches})
                    if len(batches) > 1 and len(distinct_qualities) > 1:
                        # Multiple differing quality batches exist - offer selector
                        ctk.CTkLabel(
                            pill,
                            text=f"{ore.upper()}: {req_scu:.2f} SCU",
                            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                            text_color=status_color
                        ).pack(side="left", padx=(8, 4), pady=3)

                        auto_label = f"Auto (Best: {batches[0]['quality']} Q)" if use_best_val else f"Auto (Lowest: {batches[-1]['quality']} Q)"
                        batch_opts = [auto_label]
                        batch_map = {auto_label: None}
                        for b in batches:
                            opt = f"{b.get('scu', 0.0):.1f} SCU @ {b.get('quality', 850)} Q"
                            batch_opts.append(opt)
                            batch_map[opt] = b.get("id")

                        combo_batch = ctk.CTkComboBox(
                            pill,
                            values=batch_opts,
                            width=145,
                            height=22,
                            font=ctk.CTkFont(family=FONT_MONO, size=9),
                            fg_color=SC_BG_PANEL,
                            border_width=0
                        )
                        combo_batch.set(auto_label)
                        combo_batch.pack(side="left", padx=(0, 6), pady=2)
                        card_batch_selectors[ore] = (combo_batch, batch_map)
                    else:
                        q_str = f" [{batches[0]['quality']} Q]" if batches else ""
                        pill_text = f"{ore.upper()}: {req_scu:.2f} SCU{q_str} (VAULT: {avail:.2f})"
                        ctk.CTkLabel(
                            pill,
                            text=pill_text,
                            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                            text_color=status_color
                        ).pack(padx=8, pady=3)

                right = tk.Frame(card, bg=SC_BG_PANEL)
                right.pack(side="right", padx=12, pady=8)

                combo_count = ctk.CTkComboBox(right, values=["1x", "2x", "5x", "10x"], width=70, font=ctk.CTkFont(family=FONT_MONO, size=11))
                combo_count.set("1x")
                combo_count.pack(side="left", padx=6)

                def _make_craft_cmd(rec_ref=r, count_cb=combo_count, batch_sels=card_batch_selectors):
                    return lambda: self.on_craft_click(rec_ref, count_cb.get(), batch_sels)

                btn_craft = ctk.CTkButton(
                    right,
                    text="[ FABRICATE ]" if can_craft else "[ INSUFFICIENT ]",
                    fg_color="#323a48" if can_craft else "#1c2027",
                    hover_color="#414b5c" if can_craft else "#242a34",
                    border_width=1,
                    border_color="#6c7c94" if can_craft else "#2c323e",
                    text_color=SC_TEXT_BRIGHT if can_craft else SC_TEXT_MUTED,
                    font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
                    width=140,
                    height=34,
                    command=_make_craft_cmd()
                )
                btn_craft.pack(side="left", padx=4)

    def on_craft_click(self, recipe, count_str, batch_selectors=None):
        multiplier = int(count_str.replace("x", ""))
        use_best = self.var_use_best_materials.get() if hasattr(self, "var_use_best_materials") else True

        selected_batches = {}
        if batch_selectors:
            for ore, (cb, b_map) in batch_selectors.items():
                chosen_opt = cb.get()
                b_id = b_map.get(chosen_opt)
                if b_id:
                    selected_batches[ore] = b_id

        ok, msg, deducted = craft_item(recipe, count=multiplier, use_best_materials=use_best, selected_batches=selected_batches)
        if ok:
            mode_desc = "BEST QUALITY" if use_best else "SAVED BEST"
            self.voice.speak(f"Fabricated {multiplier} {recipe['name']}. Materials deducted.", cooldown=0)
            self.refresh_inventory_ui()
            self.refresh_crafting_ui()
            self.refresh_blueprints_ui()
            self.log_comms(f"FABRICATED {multiplier}x {recipe['name'].upper()} ({mode_desc}) // {msg}", level="ok")
        else:
            self.voice.speak(f"Insufficient materials for {recipe['name']}.", cooldown=0)
            self.log_comms(f"FABRICATION BLOCKED ({recipe['name'].upper()}): {msg}", level="error")

    def open_custom_recipe_dialog(self):
        d = self._spawn_centered_toplevel("NEW FABRICATION SCHEMATIC", 420, 410)

        ctk.CTkLabel(d, text="// REGISTER CUSTOM SCHEMATIC", font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"), text_color=SC_TEXT_CYAN).pack(anchor="w", padx=20, pady=(16, 8))

        ctk.CTkLabel(d, text="SCHEMATIC NAME:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(4, 2))
        entry_name = ctk.CTkEntry(d, placeholder_text="e.g. Surge Module / Heavy Plating", width=360)
        entry_name.pack(anchor="w", padx=20, pady=4)

        ctk.CTkLabel(d, text="CATEGORY:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(6, 2))
        entry_cat = ctk.CTkEntry(d, placeholder_text="e.g. Ship Components / Weapons", width=360)
        entry_cat.pack(anchor="w", padx=20, pady=4)

        ctk.CTkLabel(d, text="PRIMARY INPUT ORE & SCU:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(6, 2))
        row1 = ctk.CTkFrame(d, fg_color="transparent")
        row1.pack(anchor="w", padx=20, pady=2)
        combo1 = ctk.CTkComboBox(row1, values=sorted(list(ORE_CATALOG.keys())), width=220)
        combo1.set("Quantainium")
        combo1.pack(side="left")
        entry_qty1 = ctk.CTkEntry(row1, placeholder_text="SCU e.g. 0.5", width=130)
        entry_qty1.pack(side="left", padx=8)

        ctk.CTkLabel(d, text="SECONDARY INPUT ORE & SCU (OPTIONAL):", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(6, 2))
        row2 = ctk.CTkFrame(d, fg_color="transparent")
        row2.pack(anchor="w", padx=20, pady=2)
        combo2 = ctk.CTkComboBox(row2, values=["None"] + sorted(list(ORE_CATALOG.keys())), width=220)
        combo2.set("None")
        combo2.pack(side="left")
        entry_qty2 = ctk.CTkEntry(row2, placeholder_text="SCU e.g. 1.0", width=130)
        entry_qty2.pack(side="left", padx=8)

        def on_save_recipe():
            name = entry_name.get().strip()
            cat = entry_cat.get().strip() or "Custom"
            if not name:
                self.log_comms("SCHEMATIC NAME REQUIRED.", level="error")
                return

            cost = {}
            try:
                q1 = float(entry_qty1.get().strip())
                if q1 > 0:
                    cost[combo1.get()] = q1
            except ValueError:
                self.log_comms("INVALID PRIMARY ORE SCU VALUE.", level="error")
                return

            if combo2.get() != "None" and entry_qty2.get().strip():
                try:
                    q2 = float(entry_qty2.get().strip())
                    if q2 > 0:
                        cost[combo2.get()] = q2
                except ValueError:
                    pass

            add_custom_recipe(name, cat, cost)
            self.refresh_crafting_ui()
            self.log_comms(f"CUSTOM SCHEMATIC '{name.upper()}' REGISTERED.", level="ok")
            d.destroy()

        ctk.CTkButton(
            d,
            text="[ REGISTER SCHEMATIC ]",
            command=on_save_recipe,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            width=360,
            height=36
        ).pack(padx=20, pady=18)

    # =========================================================================
    # PAGE 03: BLUEPRINTS & SYNTHSTRINGS MATRIX
    # =========================================================================
    def _build_page_blueprints(self, parent):
        from game_library_ui import GameLibraryPage
        self.library_page = GameLibraryPage(parent, self)

    def _build_page_home(self, parent):
        from game_library_ui import HomePage
        self.home_page = HomePage(parent, self)

    def _build_page_hud(self, parent):
        from hud_studio_ui import HUDStudioPage
        self.hud_studio = HUDStudioPage(parent, self)

    def open_library(self, mode='Items'):
        self.switch_page('blueprints')
        self.library_page.set_mode(mode)

    def _build_page_mining_planner(self, parent):
        from mining_planner_ui import MiningPlannerPage
        self.mining_planner_page = MiningPlannerPage(parent, self)

    def open_material_picker(self, materials):
        self.switch_page('mining_planner')
        self.mining_planner_page.set_targets(materials)


    def _build_category_menu(self, parent_frame):
        self.bp_cat_filter = "All"
        self.bp_cat_display = "ALL CATEGORIES"

        cat_frame = tk.Frame(parent_frame, bg=SC_BG_CARD, highlightthickness=1, highlightbackground=SC_BORDER_DIM)
        cat_frame.pack(side="left", padx=(0, 10))

        self.bp_cat_mb = tk.Menubutton(
            cat_frame,
            text="▼ ALL CATEGORIES",
            font=(FONT_MONO, 10, "bold"),
            fg=SC_TEXT_BRIGHT,
            bg=SC_BG_CARD,
            activeforeground=SC_TEXT_CYAN,
            activebackground="#2a303c",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=5,
            anchor="w"
        )
        self.bp_cat_mb.pack(side="left")

        btn_clear_cat = tk.Button(
            cat_frame,
            text="✕",
            command=lambda: self.set_category_filter("All", "ALL CATEGORIES"),
            font=(FONT_MONO, 9, "bold"),
            fg="#94a3b8",
            bg=SC_BG_CARD,
            activeforeground=SC_TEXT_RED,
            activebackground="#2a303c",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=6,
            pady=5
        )
        btn_clear_cat.pack(side="left")

        # Main Dropdown Menu
        m_opts = dict(tearoff=0, bg="#181b22", fg="#e2e8f0", activebackground="#334155", activeforeground="#38bdf8", font=(FONT_MONO, 10))
        cat_menu = tk.Menu(self.bp_cat_mb, **m_opts)
        self.bp_cat_mb.config(menu=cat_menu)

        cat_menu.add_command(label="-- ALL CATEGORIES --", command=lambda: self.set_category_filter("All", "ALL CATEGORIES"))
        cat_menu.add_separator()

        # 1. Ship Weapons (Cascades: Ship Weapons -> Sizes 1-6 -> Damage Types)
        sw_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="Ship Weapons ⯈", menu=sw_menu)
        sw_menu.add_command(label="[ ALL SHIP WEAPONS ]", command=lambda: self.set_category_filter(("Ship Weapons",), "SHIP WEAPONS"))
        sw_menu.add_separator()

        weapon_sizes = [
            ("Size 1", ["Ballistic", "Laser", "Distortion"]),
            ("Size 2", ["Ballistic", "Laser", "Distortion"]),
            ("Size 3", ["Ballistic", "Laser", "Distortion"]),
            ("Size 4", ["Ballistic", "Laser"]),
            ("Size 5", ["Ballistic", "Laser"]),
            ("Size 6", ["Ballistic", "Laser"]),
        ]
        for sz_label, dmgs in weapon_sizes:
            s_menu = tk.Menu(sw_menu, **m_opts)
            sw_menu.add_cascade(label=f"{sz_label} ⯈", menu=s_menu)
            s_menu.add_command(label=f"[ ALL {sz_label.upper()} ]", command=lambda sl=sz_label: self.set_category_filter(("Ship Weapons", sl), f"SHIP WEAPONS > {sl.upper()}"))
            s_menu.add_separator()
            for d in dmgs:
                s_menu.add_command(label=d, command=lambda sl=sz_label, dt=d: self.set_category_filter(("Ship Weapons", sl, dt), f"{sl.upper()} > {dt.upper()}"))

        # 2. Ship Components
        sc_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="Ship Components ⯈", menu=sc_menu)
        sc_menu.add_command(label="[ ALL SHIP COMPONENTS ]", command=lambda: self.set_category_filter(("Ship Components",), "SHIP COMPONENTS"))
        sc_menu.add_separator()
        for comp in ["Shield Generators", "Quantum Drives", "Power Plants", "Coolers"]:
            sc_menu.add_command(label=comp, command=lambda c=comp: self.set_category_filter(("Ship Components", c), f"SHIP > {c.upper()}"))

        # 3. Industrial Components
        ind_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="Industrial Components ⯈", menu=ind_menu)
        ind_menu.add_command(label="[ ALL INDUSTRIAL COMPONENTS ]", command=lambda: self.set_category_filter(("Industrial Components",), "IND COMPONENTS"))
        ind_menu.add_separator()
        for ind_c in ["Mining Lasers & Scrapers", "Industrial Propulsors", "Fuel Nozzles"]:
            ind_menu.add_command(label=ind_c, command=lambda ic=ind_c: self.set_category_filter(("Industrial Components", ic), f"IND > {ic.upper()}"))

        # 4. FPS Weapons
        fps_w_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="FPS Weapons ⯈", menu=fps_w_menu)
        fps_w_menu.add_command(label="[ ALL FPS WEAPONS ]", command=lambda: self.set_category_filter(("FPS Weapons",), "FPS WEAPONS"))
        fps_w_menu.add_separator()
        for wt in ["Pistols", "SMGs", "Shotguns", "Rifles & Snipers"]:
            fps_w_menu.add_command(label=wt, command=lambda w=wt: self.set_category_filter(("FPS Weapons", w), f"FPS > {w.upper()}"))

        # 5. FPS Gear
        fps_g_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="FPS Gear ⯈", menu=fps_g_menu)
        fps_g_menu.add_command(label="[ ALL FPS GEAR ]", command=lambda: self.set_category_filter(("FPS Gear",), "FPS GEAR"))
        fps_g_menu.add_separator()
        for gt in ["Magazines & Ammo", "Batteries", "Consumables & Supplies"]:
            fps_g_menu.add_command(label=gt, command=lambda g=gt: self.set_category_filter(("FPS Gear", g), f"GEAR > {g.upper()}"))

        # 6. Armor
        arm_menu = tk.Menu(cat_menu, **m_opts)
        cat_menu.add_cascade(label="Armor ⯈", menu=arm_menu)
        arm_menu.add_command(label="[ ALL ARMOR ]", command=lambda: self.set_category_filter(("Armor",), "ARMOR"))
        arm_menu.add_separator()
        for slot in ["Helmets", "Cores", "Arms", "Legs", "Backpacks"]:
            arm_menu.add_command(label=slot, command=lambda s=slot: self.set_category_filter(("Armor", s), f"ARMOR > {s.upper()}"))

        # 7. Flight Suits
        cat_menu.add_command(label="Flight Suits", command=lambda: self.set_category_filter(("Flight Suits",), "FLIGHT SUITS"))

    def set_category_filter(self, filter_spec, display_name):
        self.bp_cat_filter = filter_spec
        self.bp_cat_display = display_name
        label = f"▼ {display_name.upper()}"
        if len(label) > 28:
            label = label[:26] + "..."
        if hasattr(self, "bp_cat_mb"):
            self.bp_cat_mb.config(text=label)
        self.refresh_blueprints_ui()

    def _update_status_button_styles(self):
        st = getattr(self, "bp_status_filter", "ALL")
        if not hasattr(self, "btn_filter_all"):
            return
        is_all = (st == "ALL")
        is_owned = (st in ("OWNED", "UNLOCKED"))
        is_locked = (st in ("LOCKED", "MISSING"))
        is_fav = (st == "FAVORITES")

        self.btn_filter_all.configure(
            fg_color="#38404f" if is_all else "transparent",
            border_width=1 if is_all else 0,
            border_color="#657388" if is_all else SC_BG_CARD,
            text_color=SC_TEXT_BRIGHT if is_all else SC_TEXT_MUTED
        )
        self.btn_filter_owned.configure(
            fg_color="#38404f" if is_owned else "transparent",
            border_width=1 if is_owned else 0,
            border_color="#657388" if is_owned else SC_BG_CARD,
            text_color=SC_TEXT_GREEN if is_owned else SC_TEXT_MUTED
        )
        if hasattr(self, "btn_filter_locked"):
            self.btn_filter_locked.configure(
                fg_color="#38404f" if is_locked else "transparent",
                border_width=1 if is_locked else 0,
                border_color="#657388" if is_locked else SC_BG_CARD,
                text_color=SC_TEXT_AMBER if is_locked else SC_TEXT_MUTED
            )
        if hasattr(self, "btn_filter_favorites"):
            self.btn_filter_favorites.configure(
                fg_color="#38404f" if is_fav else "transparent",
                border_width=1 if is_fav else 0,
                border_color="#657388" if is_fav else SC_BG_CARD,
                text_color="#fbbf24" if is_fav else SC_TEXT_MUTED
            )

    def refresh_blueprints_ui(self):
        if hasattr(self, 'blueprint_page'):
            self.blueprint_page.refresh()


    def _bp_render_chunk(self, start_idx, end_idx, totals, cat_colors):
        bps = getattr(self, "_current_filtered_bps", [])
        chunk = bps[start_idx:end_idx]

        for bp in chunk:
            is_unlocked = bp.get("is_unlocked", False)
            border_col = "#566275" if is_unlocked else "#2c323e"
            card_bg = "#232832" if is_unlocked else "#181b22"

            card = tk.Frame(self.bp_scroll, bg=card_bg, highlightbackground=border_col, highlightcolor=border_col, highlightthickness=1)
            card.pack(fill="x", padx=8, pady=3)

            left = tk.Frame(card, bg=card_bg)
            left.pack(side="left", fill="both", expand=True, padx=12, pady=6)

            title_row = tk.Frame(left, bg=card_bg)
            title_row.pack(anchor="w")

            # Gold star favorite toggle button
            is_fav = bp.get("is_favorite", False)
            star_char = "★" if is_fav else "☆"
            star_fg = "#fbbf24" if is_fav else "#64748b"
            star_hover = "#f59e0b" if is_fav else "#94a3b8"

            tk.Button(
                title_row,
                text=star_char,
                command=lambda b=bp: self.on_toggle_favorite(b),
                font=(FONT_TECH, 12, "bold"),
                fg=star_fg,
                bg=card_bg,
                activeforeground=star_hover,
                activebackground=card_bg,
                bd=0,
                relief="flat",
                highlightthickness=0,
                cursor="hand2",
                padx=2,
                pady=0
            ).pack(side="left", padx=(0, 6))

            title_col = SC_TEXT_BRIGHT if is_unlocked else "#94a3b8"
            tk.Label(
                title_row,
                text=bp["name"].upper(),
                font=(FONT_TECH, 11, "bold"),
                fg=title_col,
                bg=card_bg
            ).pack(side="left")

            st_text = "✅ UNLOCKED" if is_unlocked else "⬜ LOCKED"
            st_fg = "#10b981" if is_unlocked else "#94a3b8"
            st_bg = "#032616" if is_unlocked else "#1b2028"
            st_act_bg = "#064e2e" if is_unlocked else "#262d39"
            st_act_fg = "#34d399" if is_unlocked else "#ffffff"
            st_bd = "#059669" if is_unlocked else "#334155"

            # Clickable toggle checkmark badge
            tk.Button(
                title_row,
                text=st_text,
                command=lambda b=bp, u=is_unlocked: self.on_toggle_blueprint_lock(b, lock=u),
                font=(FONT_MONO, 8, "bold"),
                fg=st_fg,
                bg=st_bg,
                activeforeground=st_act_fg,
                activebackground=st_act_bg,
                bd=1,
                relief="flat",
                highlightthickness=1,
                highlightbackground=st_bd,
                padx=7,
                pady=1,
                cursor="hand2"
            ).pack(side="left", padx=8)

            meta = bp.get("meta") or {}
            top_cat = meta.get("main") or bp.get("category", "General Equipment")
            sub_tag = meta.get("sub") or ""
            dmg_tag = meta.get("dmg") or ""
            badge_color = cat_colors.get(top_cat, SC_TEXT_MUTED)

            if dmg_tag and meta.get("size"):
                badge_label = f"{top_cat.upper()} • {meta.get('size').upper()} • {dmg_tag.upper()}"
            elif sub_tag and sub_tag != top_cat:
                badge_label = f"{top_cat.upper()} • {sub_tag.upper()}"
            else:
                badge_label = top_cat.upper()

            tk.Label(
                title_row,
                text=badge_label,
                font=(FONT_MONO, 8, "bold"),
                fg=badge_color,
                bg=SC_BG_CARD,
                padx=6,
                pady=1
            ).pack(side="left", padx=4)

            if is_unlocked:
                ts = bp.get("unlocked_at") or "Unknown"
                src = bp.get("source") or "Game Logs"
                sub_txt = f"UNLOCKED: {ts}   //   SOURCE: {src.upper()}"
                sub_col = SC_TEXT_MUTED
            else:
                sub_txt = "CONTRACT POOL // Click badge above to unlock"
                sub_col = "#64748b"

            tk.Label(
                left,
                text=sub_txt,
                font=(FONT_MONO, 9),
                fg=sub_col,
                bg=card_bg
            ).pack(anchor="w", pady=(2, 3))

            cost_box = tk.Frame(left, bg=card_bg)
            cost_box.pack(anchor="w")

            can_craft = is_unlocked
            for ore, req_scu in bp.get("cost", {}).items():
                avail = totals.get(ore, 0.0)
                has_enough = avail >= req_scu
                if not has_enough:
                    can_craft = False

                if is_unlocked:
                    status_color = SC_TEXT_GREEN if has_enough else SC_TEXT_RED
                    pill_text = f"{ore.upper()}: {req_scu:.2f} SCU ({avail:.2f})"
                else:
                    status_color = "#64748b"
                    pill_text = f"{ore.upper()}: {req_scu:.2f} SCU"

                tk.Label(
                    cost_box,
                    text=pill_text,
                    font=(FONT_MONO, 8, "bold"),
                    fg=status_color,
                    bg=SC_BG_CARD,
                    padx=6,
                    pady=2
                ).pack(side="left", padx=(0, 6))

            right = tk.Frame(card, bg=card_bg)
            right.pack(side="right", padx=12, pady=6)

            if is_unlocked:
                tk.Button(
                    right,
                    text="[ FABRICATE ]",
                    command=lambda b=bp: self.on_craft_blueprint_click(b),
                    bg="#323a48" if can_craft else "#1c2027",
                    activebackground="#414b5c" if can_craft else "#242a34",
                    fg=SC_TEXT_BRIGHT if can_craft else SC_TEXT_MUTED,
                    activeforeground=SC_TEXT_BRIGHT,
                    bd=1,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground="#6c7c94" if can_craft else "#2c323e",
                    font=(FONT_TECH, 10, "bold"),
                    padx=14,
                    pady=4,
                    cursor="hand2"
                ).pack()
            else:
                tk.Label(
                    right,
                    text="[ 🔒 LOCKED ]",
                    bg=card_bg,
                    fg="#475569",
                    font=(FONT_TECH, 9),
                    padx=10,
                    pady=4
                ).pack()

        if hasattr(self, "_btn_bp_more") and self._btn_bp_more:
            try:
                self._btn_bp_more.destroy()
            except Exception:
                pass

        if len(bps) > end_idx:
            rem = len(bps) - end_idx
            def _on_more():
                if hasattr(self, "_btn_bp_more") and self._btn_bp_more:
                    self._btn_bp_more.destroy()
                next_end = min(len(bps), end_idx + 30)
                self._bp_render_chunk(end_idx, next_end, totals, cat_colors)

            self._btn_bp_more = tk.Button(
                self.bp_scroll,
                text=f"[ SHOW MORE BLUEPRINTS (+{min(rem, 30)} of {rem} REMAINING) ]",
                command=_on_more,
                bg="#262b35",
                activebackground="#343c4a",
                fg=SC_TEXT_CYAN,
                activeforeground=SC_TEXT_BRIGHT,
                font=(FONT_TECH, 11, "bold"),
                bd=1,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#566275",
                padx=20,
                pady=8,
                cursor="hand2"
            )
            self._btn_bp_more.pack(fill="x", padx=14, pady=12)

    def on_sync_synthstrings_click(self):
        self.log_comms("SYNCHRONIZING BLUEPRINTS WITH STAR CITIZEN GLOBAL.INI...", level="info")

        def _worker():
            try:
                ok, msg, stats = sync_blueprints_to_global_ini()
            except Exception as e:
                ok, msg, stats = False, str(e), {}

            def _done():
                if ok:
                    self.voice.speak("SynthStrings synchronization complete.", allow_when_game_closed=True)
                    if hasattr(self, 'bp_lbl_complete'):
                        self.bp_lbl_complete.configure(text=f"{stats.get('complete_missions', 0)} MISSIONS 100% [ALL BP OWNED]")
                    if hasattr(self, 'bp_lbl_partial'):
                        self.bp_lbl_partial.configure(text=f"{stats.get('partial_missions', 0)} MISSIONS IN-PROGRESS [TAGGED]")
                    self.refresh_blueprints_ui()
                    self.log_comms(f"SYNTHSTRINGS SYNC COMPLETE // {stats.get('complete_missions', 0)} COMPLETE, {stats.get('partial_missions', 0)} PARTIAL MISSIONS TAGGED.", level="ok")
                else:
                    self.log_comms(f"SYNTHSTRINGS SYNC FAILED: {msg}", level="error")
            self.root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def on_toggle_blueprint_lock(self, bp: dict, lock: bool = False):
        name = bp.get("name")
        if not name:
            return
        if lock:
            removed = self.bp_manager.remove_blueprint(name)
            if removed:
                self.log_comms(f"BLUEPRINT LOCKED: {name.upper()}", level="warn")
                if getattr(self, "var_auto_sync", None) and self.var_auto_sync.get():
                    threading.Thread(target=sync_blueprints_to_global_ini, daemon=True).start()
                self.refresh_blueprints_ui()
        else:
            cat = bp.get("category")
            cost = bp.get("cost")
            self.bp_manager.add_or_update_blueprint(name, category=cat, cost=cost, source="Manual Entry")
            self.log_comms(f"BLUEPRINT UNLOCKED: {name.upper()}", level="ok")
            if getattr(self, "var_auto_sync", None) and self.var_auto_sync.get():
                threading.Thread(target=sync_blueprints_to_global_ini, daemon=True).start()
            self.refresh_blueprints_ui()

    def on_toggle_favorite(self, bp: dict):
        name = bp.get("name")
        if not name:
            return
        is_fav = self.bp_manager.toggle_favorite(name)
        status_str = "ADDED TO FAVORITES" if is_fav else "REMOVED FROM FAVORITES"
        self.log_comms(f"FAVORITES // {name.upper()}: {status_str}", level="ok" if is_fav else "info")
        self.refresh_blueprints_ui()

    def on_scan_blueprint_logs(self):
        def _worker():
            new_c, tot_c = self.bp_manager.scan_all_logs()
            if getattr(self, "var_auto_sync", None) and self.var_auto_sync.get() and new_c > 0:
                sync_blueprints_to_global_ini()

            def _done():
                self.voice.speak(f"Scanned game logs. {tot_c} blueprints total.", allow_when_game_closed=True)
                self.refresh_blueprints_ui()
                self.log_comms(f"LOG SCAN COMPLETE: {new_c} NEW BLUEPRINT(S) DISCOVERED // {tot_c} TOTAL IN ARCHIVE.", level="ok")
                self.show_log_scan_info_modal(scan_results={"new": new_c, "total": tot_c})
            self.root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def show_log_scan_info_modal(self, scan_results=None):
        modal = self._spawn_centered_toplevel("HOW BLUEPRINT SCANNING WORKS", 540, 360)
        modal.configure(fg_color="#181b22")
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text="BLUEPRINT LOG SCANNING INFO",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(padx=22, pady=(18, 8), anchor="w")

        res_box = ctk.CTkFrame(modal, fg_color="#232832", corner_radius=4, border_width=1, border_color="#38404f")
        res_box.pack(fill="x", padx=22, pady=(0, 12))

        if scan_results:
            n = scan_results.get("new", 0)
            t = scan_results.get("total", 0)
            summary_txt = f"✓ Log scan complete: Found {n} new blueprint(s) ({t} total in your archive)."
            res_color = SC_TEXT_GREEN
        else:
            summary_txt = "Scans Star Citizen's local session logs for blueprints received in-game."
            res_color = SC_TEXT_BRIGHT

        ctk.CTkLabel(
            res_box,
            text=summary_txt,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=res_color,
            padx=12,
            pady=8
        ).pack(anchor="w")

        info_txt = (
            "Why doesn't the scan find every single blueprint?\n"
            "Star Citizen only records blueprints in session log files when you receive them.\n"
            "Over time, the game automatically cleans up and deletes older session logs to save\n"
            "disk space. Any blueprints you earned before older logs were cleaned up won't be\n"
            "found in those files.\n\n"
            "How to unlock the rest:\n"
            "Scan your fabricator and review the detected names to confirm ownership.\n"
            "You can also select an item in the library and use Mark owned or Clear ownership."
        )

        ctk.CTkLabel(
            modal,
            text=info_txt,
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color="#94a3b8",
            justify="left"
        ).pack(padx=22, pady=(0, 16), anchor="w")

        ctk.CTkButton(
            modal,
            text="[ UNDERSTOOD ]",
            command=modal.destroy,
            fg_color="#323a48",
            hover_color="#414b5c",
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            height=32,
            width=130
        ).pack(side="right", padx=22, pady=(0, 16))

    def on_restore_synthstrings(self):
        if not self.restore_confirm_armed:
            self.restore_confirm_armed = True
            self.btn_restore_ini.configure(text="CONFIRM?", fg_color=SC_TEXT_RED, text_color=SC_TEXT_BRIGHT)
            self.log_comms("CLICK [ CONFIRM? ] AGAIN WITHIN 4 SECONDS TO RESTORE BACKUP GLOBAL.INI.", level="warn")
            self.root.after(4000, self._reset_restore_btn)
            return

        self._reset_restore_btn()
        ok, msg = restore_synthstrings_backup()
        if ok:
            self.voice.speak("Original localization restored.", allow_when_game_closed=True)
            self.refresh_blueprints_ui()
            self.log_comms(f"GLOBAL.INI RESTORED FROM BACKUP.", level="ok")
        else:
            self.log_comms(f"RESTORE FAILED: {msg}", level="error")

    def _reset_restore_btn(self):
        self.restore_confirm_armed = False
        if hasattr(self, "btn_restore_ini"):
            self.btn_restore_ini.configure(text="RESTORE INI", fg_color="#2a0f18", text_color=SC_TEXT_RED)

    def on_force_patch_check(self):
        self.log_comms("RUNNING PATCH SENTINEL & APPLYING LOCALIZATION RULES...", level="info")

        def _worker():
            ok, msg, report = apply_all_rules_and_adapt(force=True)

            def _done():
                if ok:
                    self.voice.speak("Game patch rules and blueprint synchronization applied.", allow_when_game_closed=True)
                    sc_info = get_current_game_version()
                    if hasattr(self, "bp_lbl_sc_ver"):
                        self.bp_lbl_sc_ver.configure(text=f"● BUILD {sc_info.get('build_num', 'LIVE')} SENTINEL ACTIVE")
                    self.refresh_blueprints_ui()
                    self.log_comms(f"PATCH AUTO-ADAPTATION COMPLETE FOR BUILD {sc_info.get('build_num', 'LIVE')}.", level="ok")
                else:
                    self.log_comms(f"PATCH ADAPTATION ERROR: {msg}", level="error")
            self.root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_game_patch_detected(self, report):
        new_b = report.get("new_build", "Unknown")
        self.voice.speak(f"Star Citizen update detected. SynthStrings updated for build {new_b}.")
        self.root.after(0, lambda: self._handle_patch_ui_update(report))

    def _handle_patch_ui_update(self, report):
        sc_info = get_current_game_version()
        if hasattr(self, "bp_lbl_sc_ver"):
            self.bp_lbl_sc_ver.configure(text=f"● BUILD {sc_info.get('build_num', 'LIVE')} SENTINEL ACTIVE")
        self.refresh_blueprints_ui()
        self.log_comms(f"GAME PATCH AUTO-ADAPTED // BUILD {report.get('new_build')} // {report.get('complete_missions')} COMPLETE MISSIONS.", level="ok")

    def on_craft_blueprint_click(self, bp):
        recipe = {
            "name": bp["name"],
            "category": bp.get("category", "Blueprints"),
            "cost": bp.get("cost", {})
        }
        ok, msg, _ = craft_item(recipe, count=1)
        if ok:
            self.voice.speak(f"Fabricated {bp['name']}", allow_when_game_closed=True)
            self.refresh_inventory_ui()
            self.refresh_crafting_ui()
            self.refresh_blueprints_ui()
            self.log_comms(f"BLUEPRINT FABRICATED: {bp['name'].upper()} // {msg}", level="ok")
        else:
            self.voice.speak("Insufficient ore for blueprint fabrication", allow_when_game_closed=True)
            self.log_comms(f"BLUEPRINT BLOCKED ({bp['name'].upper()}): {msg}", level="error")

    def _on_live_blueprint_unlocked(self, bp_data):
        name = bp_data.get("name", "Unknown Item")
        self.voice.speak(f"New Blueprint Unlocked: {name}")
        if getattr(self, "var_auto_sync", None) and self.var_auto_sync.get():
            threading.Thread(target=sync_blueprints_to_global_ini, daemon=True).start()
        self.root.after(0, self.refresh_blueprints_ui)
        self.log_comms(f"LIVE BLUEPRINT UNLOCKED FROM GAME.LOG: {name.upper()}", level="ok")

    # =========================================================================
    # PAGE 04: RADAR RETICLE ANALYZER & SIGNATURE MATRIX
    # =========================================================================
    def _build_page_radar(self, parent):
        from mining_setup_ui import MiningSetupPage
        tabs=ctk.CTkTabview(parent,fg_color=SC_BG_PANEL)
        tabs.pack(fill='both',expand=True)
        self.mining_setup=MiningSetupPage(tabs.add('Rock & loadout'),self)
        self._build_page_signature_tools(tabs.add('Signature tools'))

    def _build_page_signature_tools(self, parent):
        split = ctk.CTkFrame(parent, fg_color="transparent")
        split.pack(fill="both", expand=True)

        # Left Column: Interactive HUD Reticle Visualizer & Manual Decoder
        left_col = ctk.CTkFrame(split, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM, width=420)
        left_col.pack(side="left", fill="both", padx=(0, 8))
        left_col.pack_propagate(False)

        ctk.CTkLabel(
            left_col,
            text="// SHIP RETICLE SIGNATURE LOCK",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.reticle_canvas = tk.Canvas(
            left_col,
            width=388,
            height=220,
            bg="#0d0f14",
            highlightthickness=1,
            highlightbackground=SC_BORDER_DIM
        )
        self.reticle_canvas.pack(padx=14, pady=6)
        self._draw_large_reticle(None, None)

        self.lbl_live_title = ctk.CTkLabel(
            left_col,
            text="AWAITING RETICLE PING",
            font=ctk.CTkFont(family=FONT_TECH, size=18, weight="bold"),
            text_color=SC_TEXT_BRIGHT
        )
        self.lbl_live_title.pack(anchor="w", padx=14, pady=(6, 0))

        self.lbl_live_sub = ctk.CTkLabel(
            left_col,
            text="SC 4.10 MINERAL TABLES // AIM AT A SCANNED MARKER",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED
        )
        self.lbl_live_sub.pack(anchor="w", padx=14, pady=(2, 12))

        # Manual Decoder Card inside Left Column
        dec_box = ctk.CTkFrame(left_col, fg_color=SC_BG_PANEL, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        dec_box.pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(
            dec_box,
            text="// MANUAL RS SIGNATURE COMPUTER",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_AMBER
        ).pack(anchor="w", padx=12, pady=(10, 4))

        in_row = ctk.CTkFrame(dec_box, fg_color="transparent")
        in_row.pack(fill="x", padx=12, pady=6)

        self.entry_test_sig = ctk.CTkEntry(
            in_row,
            placeholder_text="ENTER RS (e.g. 6370)",
            font=ctk.CTkFont(family=FONT_MONO, size=12, weight="bold"),
            width=190,
            height=34
        )
        self.entry_test_sig.pack(side="left", padx=(0, 8))
        self.entry_test_sig.bind("<Return>", lambda _: self.on_manual_test())

        ctk.CTkButton(
            in_row,
            text="[ DECODE RS ]",
            command=self.on_manual_test,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=12, weight="bold"),
            width=140,
            height=34
        ).pack(side="left")

        preset_row = ctk.CTkFrame(dec_box, fg_color="transparent")
        preset_row.pack(fill="x", padx=12, pady=(2, 12))

        for sig in [3170, 6370, 8600, 15420, 4000, 12000]:
            ctk.CTkButton(
                preset_row,
                text=str(sig),
                width=54,
                height=26,
                corner_radius=3,
                fg_color=SC_BG_CARD,
                hover_color=SC_BG_CARD_ALT,
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                command=lambda s=sig: self.fill_test_sig(s)
            ).pack(side="left", padx=2)

        # Right Column: Star Citizen RS Signature Reference Matrix (Click any row to test!)
        right_col = ctk.CTkFrame(split, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        right_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            right_col,
            text="// UEE SURVEYOR RS SIGNATURE REFERENCE MATRIX (CLICK ANY ENTRY TO SIMULATE)",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=14, pady=(12, 6))

        ref_scroll = ctk.CTkScrollableFrame(right_col, fg_color=SC_BG_PANEL, corner_radius=0)
        ref_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        reference_colors = [SC_TEXT_CYAN, SC_TEXT_AMBER, SC_TEXT_GREEN, SC_TEXT_CYAN, SC_TEXT_MUTED, SC_TEXT_AMBER]
        ref_data = [(title, reference_colors[index], rows)
                    for index, (title, rows) in enumerate(reference_groups())]

        for sec_title, sec_col, rows in ref_data:
            sec = ctk.CTkFrame(ref_scroll, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
            sec.pack(fill="x", padx=6, pady=5)
            ctk.CTkLabel(sec, text=f"// {sec_title}", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=sec_col).pack(anchor="w", padx=12, pady=(8, 4))

            for item, val_str, raw_sig in rows:
                r_f = ctk.CTkFrame(sec, fg_color="transparent")
                r_f.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(r_f, text=item, font=ctk.CTkFont(family=FONT_TECH, size=12), text_color=SC_TEXT_BRIGHT).pack(side="left")
                ctk.CTkButton(
                    r_f,
                    text=val_str,
                    width=95,
                    height=24,
                    corner_radius=3,
                    fg_color=SC_BG_CARD_ALT,
                    hover_color="#343c4a",
                    text_color=sec_col,
                    font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                    command=lambda s=raw_sig: self.fill_test_sig(s)
                ).pack(side="right")

    def _draw_large_reticle(self, match, sig_num):
        if not hasattr(self, "reticle_canvas"):
            return
        c = self.reticle_canvas
        c.delete("all")
        w, h = 388, 220
        cx, cy = w // 2, h // 2

        accent = SC_TEXT_CYAN
        if match:
            colors = {
                "ship_mining": SC_TEXT_CYAN,
                "roc": SC_TEXT_GREEN,
                "hand": SC_TEXT_GREEN,
                "salvage": SC_TEXT_AMBER,
                "ambiguous": SC_TEXT_AMBER,
                "asteroid": SC_TEXT_CYAN,
                "surface": SC_TEXT_AMBER,
                "gemstone": SC_TEXT_GREEN,
                "derelict": SC_TEXT_RED
            }
            accent = colors.get(match.get("type", ""), SC_TEXT_CYAN)

        # HUD Background Grid
        for x in range(0, w, 32):
            c.create_line(x, 0, x, h, fill="#161920", width=1)
        for y in range(0, h, 32):
            c.create_line(0, y, w, y, fill="#161920", width=1)

        # Outer Reticle Ring & Crosshair Ticks
        c.create_oval(cx - 75, cy - 75, cx + 75, cy + 75, outline="#262d3a", width=1)
        c.create_oval(cx - 48, cy - 48, cx + 48, cy + 48, outline=accent, width=1)

        # Corner Target Lock Brackets
        b = 62
        bl = 16
        # TL
        c.create_line(cx - b, cy - b, cx - b + bl, cy - b, fill=accent, width=2)
        c.create_line(cx - b, cy - b, cx - b, cy - b + bl, fill=accent, width=2)
        # TR
        c.create_line(cx + b - bl, cy - b, cx + b, cy - b, fill=accent, width=2)
        c.create_line(cx + b, cy - b, cx + b, cy - b + bl, fill=accent, width=2)
        # BL
        c.create_line(cx - b, cy + b - bl, cx - b, cy + b, fill=accent, width=2)
        c.create_line(cx - b, cy + b, cx - b + bl, cy + b, fill=accent, width=2)
        # BR
        c.create_line(cx + b - bl, cy + b, cx + b, cy + b, fill=accent, width=2)
        c.create_line(cx + b, cy + b - bl, cx + b, cy + b, fill=accent, width=2)

        # Center Pip
        c.create_line(cx - 18, cy, cx - 5, cy, fill=accent, width=1)
        c.create_line(cx + 5, cy, cx + 18, cy, fill=accent, width=1)
        c.create_line(cx, cy - 18, cx, cy - 5, fill=accent, width=1)
        c.create_line(cx, cy + 5, cx, cy + 18, fill=accent, width=1)

        # Telemetry Overlays inside Canvas
        c.create_text(10, 14, text=f"GAME MON {self.cfg.get('game_monitor', 1)} // ROI 700x450", anchor="w", fill=SC_TEXT_MUTED, font=(FONT_MONO, 8, "bold"))
        if match and sig_num:
            status = (f"{len(match['candidates'])} MATCHES" if match.get("ambiguous") else
                      f"OCR {match['ocr_confidence']:.0%}" if match.get("ocr_confidence") is not None else "EXACT MATCH")
            c.create_text(w - 10, 14, text=status, anchor="e", fill=accent, font=(FONT_MONO, 8, "bold"))
            c.create_text(cx, cy - 88, text=f"RS {sig_num:,}", anchor="center", fill=SC_TEXT_BRIGHT, font=(FONT_MONO, 13, "bold"))
            c.create_text(cx, cy + 88, text=match["title"].upper(), anchor="center", fill=accent, font=(FONT_TECH, 12, "bold"))
        else:
            c.create_text(w - 10, 14, text="STANDBY", anchor="e", fill=SC_TEXT_MUTED, font=(FONT_MONO, 8, "bold"))
            c.create_text(cx, cy + 88, text="SCANNING SHIP CROSSHAIR...", anchor="center", fill=SC_TEXT_MUTED, font=(FONT_MONO, 9, "bold"))

    # =========================================================================
    # PAGE 05: MULTI-MONITOR ROUTING, HUD OVERLAY & VOICE COMMS
    # =========================================================================
    def _build_page_system(self, parent):
        # 1. MULTI-MONITOR ROUTING MATRIX
        mon_card = ctk.CTkFrame(parent, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        mon_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            mon_card,
            text="// MULTI-MONITOR DISPLAY ROUTING MATRIX",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            mon_card,
            text="Keep Star Citizen unobstructed on your primary display while operating SynthScan on your secondary monitor.",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 8))

        mon_inner = ctk.CTkFrame(mon_card, fg_color="transparent")
        mon_inner.pack(fill="x", padx=14, pady=(0, 12))

        # Visual Dual-Monitor Diagram Canvas
        self.mon_diagram_canvas = tk.Canvas(
            mon_inner,
            width=360,
            height=115,
            bg="#0d0f14",
            highlightthickness=1,
            highlightbackground=SC_BORDER_DIM
        )
        self.mon_diagram_canvas.pack(side="left", padx=(0, 16))

        mon_controls = ctk.CTkFrame(mon_inner, fg_color="transparent")
        mon_controls.pack(side="left", fill="both", expand=True)

        # Row A: Where should SynthScan UI live?
        r_ui = ctk.CTkFrame(mon_controls, fg_color=SC_BG_PANEL, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        r_ui.pack(fill="x", pady=4)
        ctk.CTkLabel(r_ui, text="SYNTHSCAN UI WINDOW:", font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"), text_color=SC_TEXT_BRIGHT).pack(side="left", padx=12, pady=10)

        for m in self.monitors:
            mid = m["id"]
            ctk.CTkButton(
                r_ui,
                text=f"SNAP UI TO MONITOR {mid} ({m['width']}x{m['height']})",
                command=lambda i=mid: self._center_on_monitor(i),
                fg_color="#323a48" if mid == 2 else SC_BG_CARD_ALT,
                hover_color="#414b5c" if mid == 2 else "#343c4a",
                border_width=1,
                border_color="#6c7c94" if mid == 2 else SC_BORDER_DIM,
                text_color=SC_TEXT_BRIGHT,
                font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
                height=30,
                width=190
            ).pack(side="right", padx=6, pady=6)

        # Row B: Where is Star Citizen running?
        r_gm = ctk.CTkFrame(mon_controls, fg_color=SC_BG_PANEL, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        r_gm.pack(fill="x", pady=4)
        ctk.CTkLabel(r_gm, text="STAR CITIZEN GAME DISPLAY:", font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"), text_color=SC_TEXT_AMBER).pack(side="left", padx=12, pady=10)

        for m in self.monitors:
            mid = m["id"]
            ctk.CTkButton(
                r_gm,
                text=f"TARGET MONITOR {mid}",
                command=lambda i=mid: self.set_game_monitor(i),
                fg_color=SC_BG_CARD_ALT,
                hover_color="#343c4a",
                border_width=1,
                border_color=SC_TEXT_AMBER if mid == 1 else SC_BORDER_DIM,
                text_color=SC_TEXT_AMBER if mid == 1 else SC_TEXT_BRIGHT,
                font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
                height=30,
                width=150
            ).pack(side="right", padx=6, pady=6)

        self._draw_monitor_diagram()

        # 2. BOTTOM SPLIT: IN-GAME HUD OVERLAY & VOICE COMMS
        bottom_split = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_split.pack(fill="both", expand=True)

        # Left: Click-Through HUD Overlay Config
        hud_card = ctk.CTkFrame(bottom_split, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        hud_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctk.CTkLabel(
            hud_card,
            text="In-game HUD",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.sw_overlay = ctk.CTkSwitch(
            hud_card,
            text="Mining scan results",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            progress_color=SC_TEXT_CYAN,
            command=self.on_overlay_toggle
        )
        self.sw_overlay.pack(anchor="w", padx=14, pady=(6, 4))
        if self.cfg.get("overlay_enabled", True):
            self.sw_overlay.select()

        self.sw_top_hud = ctk.CTkSwitch(
            hud_card,
            text="Server, region & visit history",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            progress_color=SC_TEXT_GREEN,
            command=self.on_top_hud_toggle
        )
        self.sw_top_hud.pack(anchor="w", padx=14, pady=4)
        if self.cfg.get("top_hud_enabled", True):
            self.sw_top_hud.select()

        ctk.CTkButton(hud_card, text="Open HUD layout editor →", command=lambda: self.switch_page('hud'),
                      fg_color=SC_BG_CARD_ALT, height=36).pack(fill='x', padx=14, pady=14)

        # Right: Voice Telemetry (TTS) Config
        voice_card = ctk.CTkFrame(bottom_split, fg_color=SC_BG_CARD, corner_radius=4, border_width=1, border_color=SC_BORDER_DIM)
        voice_card.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(
            voice_card,
            text="// SHIP COMPUTER NEURAL AI VOICE",
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            text_color=SC_TEXT_AMBER
        ).pack(anchor="w", padx=14, pady=(12, 4))

        sw_row = ctk.CTkFrame(voice_card, fg_color="transparent")
        sw_row.pack(fill="x", padx=14, pady=4)

        self.sw_voice = ctk.CTkSwitch(
            sw_row,
            text="VOICE CALLOUTS",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            progress_color=SC_TEXT_AMBER,
            command=self.on_voice_toggle
        )
        self.sw_voice.pack(side="left", padx=(0, 18))
        if self.cfg.get("voice_enabled", True):
            self.sw_voice.select()

        self.sw_chime = ctk.CTkSwitch(
            sw_row,
            text="COCKPIT HARMONIC CHIME",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            progress_color=SC_TEXT_CYAN,
            command=self.on_chime_toggle
        )
        self.sw_chime.pack(side="left")
        if self.cfg.get("voice_chime", True):
            self.sw_chime.select()

        ctk.CTkLabel(voice_card, text="SHIP MANUFACTURER AI PROFILE:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=14, pady=(6, 2))
        self._profile_label_to_key = {v["label"]: k for k, v in SHIP_VOICE_PROFILES.items()}
        self._profile_key_to_label = {k: v["label"] for k, v in SHIP_VOICE_PROFILES.items()}
        cur_prof = self.cfg.get("voice_profile", "origin")

        self.combo_voice_profile = ctk.CTkOptionMenu(
            voice_card,
            values=list(self._profile_label_to_key.keys()),
            command=self.on_voice_profile_change,
            fg_color=SC_BG_PANEL,
            button_color=SC_BG_CARD_ALT,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=SC_TEXT_CYAN,
            width=410,
            height=30
        )
        self.combo_voice_profile.set(self._profile_key_to_label.get(cur_prof, SHIP_VOICE_PROFILES["origin"]["label"]))
        self.combo_voice_profile.pack(anchor="w", padx=14, pady=4)

        ctk.CTkLabel(voice_card, text="TRANSMISSION VOLUME:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=14, pady=(6, 2))
        self.slider_vol = ctk.CTkSlider(voice_card, from_=0, to=100, progress_color=SC_TEXT_AMBER, command=self.on_volume_change)
        self.slider_vol.set(self.cfg.get("voice_volume", 80))
        self.slider_vol.pack(fill="x", padx=14, pady=2)

        ctk.CTkLabel(voice_card, text="CADENCE / SPEECH RATE:", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=SC_TEXT_MUTED).pack(anchor="w", padx=14, pady=(6, 2))
        self.slider_rate = ctk.CTkSlider(voice_card, from_=-5, to=5, progress_color=SC_TEXT_AMBER, command=self.on_rate_change)
        self.slider_rate.set(self.cfg.get("voice_rate", 1))
        self.slider_rate.pack(fill="x", padx=14, pady=2)

        btn_row = ctk.CTkFrame(voice_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=10)

        ctk.CTkButton(
            btn_row,
            text="[ TEST ORIGIN / SHIP AI ]",
            command=lambda: self.voice.speak("Origin Jumpworks telemetry online. Three asteroids detected.", cooldown=0, allow_when_game_closed=True),
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            width=185,
            height=32
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="[ SAVE CONFIGURATION ]",
            command=self.save_all_settings,
            fg_color="#18231c",
            hover_color="#223227",
            border_width=1,
            border_color="#2f573c",
            text_color="#48bb78",
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            width=170,
            height=32
        ).pack(side="right")

    def _draw_monitor_diagram(self):
        if not hasattr(self, "mon_diagram_canvas"):
            return
        c = self.mon_diagram_canvas
        c.delete("all")
        ui_mon = self.cfg.get("ui_monitor", 1)
        gm_mon = self.cfg.get("game_monitor", 1)

        boxes = [(15, 16, 170, 98, 1), (190, 16, 345, 98, 2)]
        for x1, y1, x2, y2, mid in boxes:
            exists = any(m["id"] == mid for m in self.monitors)
            outline = SC_BORDER_CYAN if mid == ui_mon else (SC_TEXT_AMBER if mid == gm_mon else SC_BORDER_DIM)
            c.create_rectangle(x1, y1, x2, y2, fill="#1e222a" if exists else "#12151b", outline=outline, width=2 if (mid in (ui_mon, gm_mon)) else 1)
            c.create_text(x1 + 8, y1 + 12, text=f"DISPLAY 0{mid}", anchor="w", fill=SC_TEXT_BRIGHT if exists else SC_TEXT_MUTED, font=(FONT_MONO, 9, "bold"))

            if not exists:
                c.create_text((x1 + x2) // 2, (y1 + y2) // 2 + 8, text="NOT CONNECTED", fill=SC_TEXT_MUTED, font=(FONT_MONO, 8))
                continue

            tags = []
            if mid == gm_mon:
                tags.append(("STAR CITIZEN + HUD", SC_TEXT_AMBER))
            if mid == ui_mon:
                tags.append(("SYNTHSCAN MFD UI", SC_TEXT_CYAN))

            ty = y1 + 36
            for t_str, t_col in tags:
                c.create_rectangle(x1 + 10, ty - 8, x2 - 10, ty + 10, fill="#262b35", outline=t_col)
                c.create_text((x1 + x2) // 2, ty + 1, text=t_str, fill=t_col, font=(FONT_MONO, 8, "bold"))
                ty += 24

    # =========================================================================
    # 05 // SERVER & SHARD SESSION LOG PAGE
    # =========================================================================
    def _build_page_servers(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        self.server_log_filter_text = ""
        self.server_log_filter_region = "ALL"

        # 1. Page Header Strip
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            hdr,
            text="// 05 // SERVER & SHARD SESSION LOG",
            font=ctk.CTkFont(family=FONT_TECH, size=18, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(side="left")

        ctk.CTkLabel(
            hdr,
            text="TRACKING SHARD IDENTIFIERS, TIMESTAMPS, VISITED ZONES & TACTICAL PVP / MINING NOTES",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED
        ).pack(side="left", padx=12, pady=(4, 0))

        # 2. ACTIVE SERVER INTEL CARD (Top Banner)
        self.card_active_server = ctk.CTkFrame(
            parent,
            fg_color=SC_BG_CARD,
            border_width=1,
            border_color=SC_BORDER_CYAN,
            corner_radius=4
        )
        self.card_active_server.pack(fill="x", padx=16, pady=(0, 10))

        top_active_row = ctk.CTkFrame(self.card_active_server, fg_color="transparent")
        top_active_row.pack(fill="x", padx=14, pady=(12, 4))

        # Left Info Block
        left_blk = ctk.CTkFrame(top_active_row, fg_color="transparent")
        left_blk.pack(side="left", fill="both", expand=True)

        status_line = ctk.CTkFrame(left_blk, fg_color="transparent")
        status_line.pack(anchor="w")

        self.lbl_active_dot = ctk.CTkLabel(
            status_line,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=SC_TEXT_GREEN
        )
        self.lbl_active_dot.pack(side="left", padx=(0, 6))

        self.lbl_active_status = ctk.CTkLabel(
            status_line,
            text="LIVE PU CONNECTION",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_GREEN
        )
        self.lbl_active_status.pack(side="left")

        self.lbl_active_name = ctk.CTkLabel(
            left_blk,
            text="AWAITING TELEMETRY...",
            font=ctk.CTkFont(family=FONT_TECH, size=20, weight="bold"),
            text_color=SC_TEXT_CYAN,
            anchor="w"
        )
        self.lbl_active_name.pack(fill="x", pady=(2, 2))

        self.lbl_active_ids = ctk.CTkLabel(
            left_blk,
            text="SHARD: --  |  ID: --  |  IP: --",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED,
            anchor="w"
        )
        self.lbl_active_ids.pack(fill="x")

        # Right Action Buttons
        act_box = ctk.CTkFrame(top_active_row, fg_color="transparent")
        act_box.pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            act_box,
            text="🏷️ RENAME / TAG SHARD",
            command=self.open_tag_shard_dialog,
            fg_color="#262b35",
            hover_color="#343c4a",
            border_width=1,
            border_color="#4f596b",
            text_color=SC_TEXT_CYAN,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            height=32,
            width=160
        ).pack(side="top", pady=2)

        ctk.CTkButton(
            act_box,
            text="📋 COPY SHARD ID",
            command=self._copy_active_shard_id,
            fg_color=SC_BG_CARD_ALT,
            hover_color="#343c4a",
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight="bold"),
            height=28,
            width=160
        ).pack(side="top", pady=2)

        # Telemetry & Badges Strip
        self.active_badges_row = ctk.CTkFrame(self.card_active_server, fg_color="transparent")
        self.active_badges_row.pack(fill="x", padx=14, pady=(4, 8))

        self.lbl_active_reg = ctk.CTkLabel(
            self.active_badges_row,
            text="REG: --",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_AMBER
        )
        self.lbl_active_reg.pack(side="left", padx=(0, 10))

        self.lbl_active_duration = ctk.CTkLabel(
            self.active_badges_row,
            text="⏱️ CONNECTED: 0m",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_GREEN
        )
        self.lbl_active_duration.pack(side="left", padx=(0, 10))

        self.lbl_active_loc = ctk.CTkLabel(
            self.active_badges_row,
            text="📍 LOC: --",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_CYAN
        )
        self.lbl_active_loc.pack(side="left", padx=(0, 10))

        self.lbl_active_sfps = ctk.CTkLabel(
            self.active_badges_row,
            text="SRV FPS: --",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_MUTED
        )
        self.lbl_active_sfps.pack(side="left", padx=(0, 10))

        self.lbl_active_ping = ctk.CTkLabel(
            self.active_badges_row,
            text="PING: --",
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            text_color=SC_TEXT_MUTED
        )
        self.lbl_active_ping.pack(side="left")

        # Quick Tactical Note input row
        note_row = ctk.CTkFrame(self.card_active_server, fg_color=SC_BG_PANEL, corner_radius=3)
        note_row.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            note_row,
            text="TACTICAL NOTE:",
            font=ctk.CTkFont(family=FONT_MONO, size=9, weight="bold"),
            text_color=SC_TEXT_AMBER
        ).pack(side="left", padx=(8, 6), pady=6)

        self.ent_active_note = ctk.CTkEntry(
            note_row,
            placeholder_text="Log intel for this session (e.g. PvP at Pyro 3 Hathor, mined 32 SCU Caronite, griefers at OM-1)...",
            font=ctk.CTkFont(family=FONT_TECH, size=11),
            fg_color=SC_BG_CARD,
            border_color=SC_BORDER_DIM,
            height=30
        )
        self.ent_active_note.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        self.ent_active_note.bind("<Return>", lambda e: self._save_active_note())

        ctk.CTkButton(
            note_row,
            text="+ SAVE NOTE",
            command=self._save_active_note,
            fg_color="#18231c",
            hover_color="#223227",
            border_width=1,
            border_color="#2f573c",
            text_color="#48bb78",
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight="bold"),
            height=30,
            width=110
        ).pack(side="right", padx=(4, 8), pady=6)

        # 3. Search & Region Filter Bar
        filter_bar = ctk.CTkFrame(parent, fg_color="transparent")
        filter_bar.pack(fill="x", padx=16, pady=(4, 6))

        self.ent_server_search = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Search server history by codename, shard ID, location, or note keyword...",
            font=ctk.CTkFont(family=FONT_TECH, size=11),
            fg_color=SC_BG_CARD,
            border_color=SC_BORDER_DIM,
            height=32
        )
        self.ent_server_search.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_server_search.bind("<KeyRelease>", self._on_server_search_change)

        self.seg_region = ctk.CTkSegmentedButton(
            filter_bar,
            values=["ALL", "ASIA-EAST", "US", "EU"],
            command=self._on_region_filter_change,
            font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
            selected_color="#38404f",
            selected_hover_color="#414b5c",
            unselected_color=SC_BG_CARD,
            height=32
        )
        self.seg_region.set("ALL")
        self.seg_region.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            filter_bar,
            text="⟳ REFRESH",
            command=self._refresh_server_log_view,
            fg_color=SC_BG_CARD,
            hover_color=SC_BG_CARD_ALT,
            border_width=1,
            border_color=SC_BORDER_DIM,
            text_color=SC_TEXT_CYAN,
            font=ctk.CTkFont(family=FONT_TECH, size=10, weight="bold"),
            width=85,
            height=32
        ).pack(side="right")

        # 4. Scrollable Session Cards Container
        self.scroll_servers = ctk.CTkScrollableFrame(
            parent,
            fg_color=SC_BG_PANEL,
            border_width=1,
            border_color=SC_BORDER_DIM,
            corner_radius=4
        )
        self.scroll_servers.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self._refresh_server_log_view()

    def _save_active_note(self):
        txt = self.ent_active_note.get().strip() if hasattr(self, "ent_active_note") else ""
        if not txt:
            return
        active = self.server_logger.get_active_session()
        if active:
            existing = active.get("notes", "")
            combined = f"{existing} | {txt}" if existing else txt
            self.server_logger.set_session_note(active["id"], combined)
            self.ent_active_note.delete(0, "end")
            self.log_comms("TACTICAL SESSION NOTE LOGGED", level="ok")
            self._refresh_server_log_view()

    def _copy_active_shard_id(self):
        active = self.server_logger.get_active_session()
        sh_id = active.get("full_shard_id", "") if active else self.top_hud.state.get("shard_id", "")
        if sh_id:
            self.root.clipboard_clear()
            self.root.clipboard_append(sh_id)
            self.log_comms(f"COPIED TO CLIPBOARD: {sh_id}", level="ok")

    def _on_server_search_change(self, event=None):
        if hasattr(self, "ent_server_search"):
            self.server_log_filter_text = self.ent_server_search.get().strip()
            self._refresh_server_log_view()

    def _on_region_filter_change(self, value):
        self.server_log_filter_region = value
        self._refresh_server_log_view()

    def _refresh_active_server(self):
        if not hasattr(self, "lbl_active_status"):
            return
        # 1. Update Active Server Card
        active = self.server_logger.get_active_session()
        if hasattr(self, "lbl_active_evidence"):
            state = self.top_hud.state
            available = [key for key in ("server_fps", "ping_ms", "shard_pop", "srv_pop") if state.get(key) is not None]
            status = state.get("health", {}).get("label", "")
            detail = f"{status} · Live measurements: {len(available)}/4" if available else "No fresh performance or population readings · Return tracking remains active"
            self.lbl_active_evidence.configure(text=detail if active else "Waiting for a game session")
        if active:
            self.lbl_active_status.configure(text="CONNECTED · METRICS REQUIRE A LIVE SOURCE", text_color=SC_TEXT_CYAN)
            name = active.get("server_name") or f"SHARD {active.get('shard_id', '--')}"
            self.lbl_active_name.configure(text=name)
            if hasattr(self, "btn_hdr_shard"):
                short_n = name if len(name) <= 16 else name[:14] + ".."
                self.btn_hdr_shard.configure(text=f"🏷️ {short_n}")

            dur = format_duration(active.get("duration_sec", 0))
            self.lbl_active_duration.configure(text=f"⏱️ CONNECTED: {dur}")
            self.lbl_active_ids.configure(
                text=f"SHARD: {active.get('shard_id', '--')}  |  ID: {active.get('full_shard_id', '--')}  |  IP: {active.get('ip_address', '--')}"
            )
            self.lbl_active_reg.configure(text=f"REG: {active.get('region_display', '--')}")
            locs = active.get("locations", [])
            cur_loc = locs[-1].get("name") if locs else (self.top_hud.state.get("location_display") or "--")
            self.lbl_active_loc.configure(text=f"📍 LOC: {cur_loc}")

            sfps = self.top_hud.state.get("server_fps")
            if sfps is not None:
                col = SC_TEXT_GREEN if sfps >= 25 else (SC_TEXT_AMBER if sfps >= 10 else SC_TEXT_RED)
                self.lbl_active_sfps.configure(text=f"SRV FPS: {sfps:.1f}", text_color=col)
            else:
                self.lbl_active_sfps.configure(text="SRV FPS: --", text_color=SC_TEXT_MUTED)

            ping = self.top_hud.state.get("ping_ms")
            if ping is not None:
                col = SC_TEXT_GREEN if ping < 100 else (SC_TEXT_AMBER if ping < 200 else SC_TEXT_RED)
                self.lbl_active_ping.configure(text=f"PING: {ping:.0f}ms", text_color=col)
            else:
                self.lbl_active_ping.configure(text="PING: --", text_color=SC_TEXT_MUTED)

        else:
            self.lbl_active_status.configure(text="NO ACTIVE GAME SESSION", text_color=SC_TEXT_MUTED)
            self.lbl_active_name.configure(text="OFFLINE")
            self.lbl_active_ids.configure(text="SHARD: --  |  ID: --")
            self.lbl_active_duration.configure(text="CONNECTED: --")
            self.lbl_active_reg.configure(text="REG: --")
            self.lbl_active_loc.configure(text="LAST LOC: --")
            self.lbl_active_sfps.configure(text="SRV FPS: --", text_color=SC_TEXT_MUTED)
            self.lbl_active_ping.configure(text="PING: --", text_color=SC_TEXT_MUTED)

    def _refresh_server_log_view(self):
        if not hasattr(self, "scroll_servers"):
            return

        self._refresh_active_server()

        # 2. Render Scrollable Sessions List
        for w in self.scroll_servers.winfo_children():
            w.destroy()

        sessions = self.server_logger.get_sessions(
            filter_text=getattr(self, "server_log_filter_text", ""),
            filter_region=getattr(self, "server_log_filter_region", "ALL")
        )

        if not sessions:
            empty_box = ctk.CTkFrame(self.scroll_servers, fg_color=SC_BG_CARD, corner_radius=4)
            empty_box.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(
                empty_box,
                text="// NO SESSIONS MATCH FILTER CRITERIA",
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                text_color=SC_TEXT_MUTED
            ).pack(pady=20)
            return

        for sess in sessions:
            card = ctk.CTkFrame(
                self.scroll_servers,
                fg_color=SC_BG_CARD if not sess.get("active") else "#262b35",
                border_width=1,
                border_color="#566275" if sess.get("active") else SC_BORDER_DIM,
                corner_radius=4
            )
            card.pack(fill="x", padx=6, pady=4)

            # Top Row: Timestamp, Duration, Shard Name, Region Pill
            r1 = ctk.CTkFrame(card, fg_color="transparent")
            r1.pack(fill="x", padx=12, pady=(10, 4))

            # Status pill & Joined Timestamp
            st_text = "● ACTIVE" if sess.get("active") else "COMPLETED"
            st_col = SC_TEXT_GREEN if sess.get("active") else SC_TEXT_MUTED
            ctk.CTkLabel(
                r1,
                text=st_text,
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                text_color=st_col
            ).pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                r1,
                text=sess.get("joined_at_local", "--"),
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                text_color=SC_TEXT_BRIGHT
            ).pack(side="left", padx=(0, 12))

            # Server Name
            sname = sess.get("server_name") or f"SHARD {sess.get('shard_id', '--')}"
            ctk.CTkLabel(
                r1,
                text=sname,
                font=ctk.CTkFont(family=FONT_TECH, size=14, weight="bold"),
                text_color=SC_TEXT_CYAN
            ).pack(side="left", padx=(0, 12))

            # Shard & Region
            ctk.CTkLabel(
                r1,
                text=f"SHARD {sess.get('shard_id', '--')}",
                font=ctk.CTkFont(family=FONT_MONO, size=10),
                text_color=SC_TEXT_MUTED
            ).pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                r1,
                text=f"[{sess.get('region_display', '--')}]",
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                text_color=SC_TEXT_AMBER
            ).pack(side="left", padx=(0, 8))

            dur_str = format_duration(sess.get("duration_sec", 0))
            ctk.CTkLabel(
                r1,
                text=f"⏱️ {dur_str}",
                font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"),
                text_color=SC_TEXT_GREEN
            ).pack(side="right")

            # Middle Row: Visited Locations & Health Telemetry
            r2 = ctk.CTkFrame(card, fg_color="transparent")
            r2.pack(fill="x", padx=12, pady=(2, 6))

            locs = sess.get("locations", [])
            if locs:
                loc_txt = " ➔ ".join(l.get("name", "") for l in locs)
                ctk.CTkLabel(
                    r2,
                    text=f"📍 LOCATIONS: {loc_txt}",
                    font=ctk.CTkFont(family=FONT_MONO, size=10),
                    text_color="#8ec5fc"
                ).pack(side="left", padx=(0, 14))

            # Telemetry Summary
            tel = sess.get("telemetry", {})
            t_parts = []
            if tel.get("avg_sfps") is not None:
                t_parts.append(f"SRV FPS: ~{tel['avg_sfps']:.1f}")
            if tel.get("avg_ping") is not None:
                t_parts.append(f"PING: ~{tel['avg_ping']}ms")
            if tel.get("restarts") is not None and tel["restarts"] > 0:
                t_parts.append(f"RST: {tel['restarts']}")
            if t_parts and not (tel.get("sfps_samples") or tel.get("ping_samples")):
                t_parts.insert(0, "LEGACY / UNVERIFIED")
            if t_parts:
                ctk.CTkLabel(
                    r2,
                    text="  |  ".join(t_parts),
                    font=ctk.CTkFont(family=FONT_MONO, size=9),
                    text_color=SC_TEXT_MUTED
                ).pack(side="left")

            # Action Buttons Row
            btn_sub = ctk.CTkFrame(r2, fg_color="transparent")
            btn_sub.pack(side="right")

            ctk.CTkButton(
                btn_sub,
                text="✏️ NOTE",
                width=65,
                height=22,
                font=ctk.CTkFont(family=FONT_TECH, size=9, weight="bold"),
                fg_color=SC_BG_PANEL,
                hover_color=SC_BG_CARD_ALT,
                border_width=1,
                border_color=SC_BORDER_DIM,
                command=lambda sid=sess["id"]: self.open_edit_note_dialog(sid)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_sub,
                text="🏷️ RENAME",
                width=75,
                height=22,
                font=ctk.CTkFont(family=FONT_TECH, size=9, weight="bold"),
                fg_color=SC_BG_PANEL,
                hover_color=SC_BG_CARD_ALT,
                border_width=1,
                border_color=SC_BORDER_DIM,
                command=lambda sh=sess.get("shard_id"), rg=sess.get("region_raw"), nm=sess.get("server_name"), full=sess.get("full_shard_id"): self.open_tag_shard_dialog(sh, rg, nm, full)
            ).pack(side="left", padx=2)

            # Tactical Notes block (if present)
            if sess.get("notes"):
                nb = ctk.CTkFrame(card, fg_color="#1a1403", border_width=1, border_color="#664400", corner_radius=3)
                nb.pack(fill="x", padx=12, pady=(0, 8))
                ctk.CTkLabel(
                    nb,
                    text=f"💬 {sess['notes']}",
                    font=ctk.CTkFont(family=FONT_TECH, size=11),
                    text_color=SC_TEXT_AMBER,
                    anchor="w",
                    justify="left"
                ).pack(fill="x", padx=8, pady=4)

    def open_shard_reminder_dialog(self):
        full_id = self.top_hud.state.get("full_shard_id")
        if not full_id:
            self.log_comms("JOIN A SHARD BEFORE ADDING A REMINDER", level="warn")
            return
        top = self._spawn_centered_toplevel("SHARD REMINDER", 500, 330)
        ctk.CTkLabel(top, text="REMIND ME ABOUT THIS SHARD", text_color=SC_TEXT_CYAN,
                    font=ctk.CTkFont(family=FONT_TECH, size=17, weight="bold")).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(top, text=self.top_hud.state.get("callsign", full_id), text_color=SC_TEXT_BRIGHT).pack(anchor="w", padx=20)
        ctk.CTkLabel(top, text="A personal reminder, not a detected game cooldown.",
                    text_color=SC_TEXT_MUTED).pack(anchor="w", padx=20, pady=(4, 12))
        label = ctk.CTkEntry(top, placeholder_text="Component, location, or reason to return")
        label.pack(fill="x", padx=20, pady=5)
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text="Minutes (1–1440):").pack(side="left")
        duration = ctk.CTkEntry(row, width=100)
        duration.insert(0, "60")
        duration.pack(side="left", padx=10)
        feedback = ctk.CTkLabel(top, text="", text_color=SC_TEXT_RED)
        feedback.pack(anchor="w", padx=20)

        def save():
            if self.top_hud.state.get("full_shard_id") != full_id:
                feedback.configure(text="The active shard changed. Reopen this dialog.")
                return
            try:
                minutes = int(duration.get())
                reminder = self.top_hud.shard_tracker.mark_cooldown(label.get(), minutes)
            except (ValueError, OSError) as exc:
                feedback.configure(text=str(exc))
                return
            active = self.server_logger.get_active_session()
            if active:
                from telemetry_core import utc_iso
                note = f"[Reminder] {reminder['label']} · until {format_duration(minutes * 60)} after marking ({utc_iso(reminder['recorded_at'])})"
                prior = active.get("notes", "")
                self.server_logger.set_session_note(active["id"], (prior + "\n" + note).strip())
            self.top_hud.update_from_image_and_logs()
            self._refresh_server_log_view()
            self.log_comms(f"SHARD REMINDER SET: {reminder['label']} ({minutes} MIN)", level="ok")
            top.destroy()

        ctk.CTkButton(top, text="SAVE REMINDER", command=save, fg_color="#414b5c").pack(anchor="e", padx=20, pady=10)

    def open_tag_shard_dialog(self, default_shard_id=None, default_region=None, default_name=None, default_full_id=None):
        active = self.server_logger.get_active_session()
        shard_id = default_shard_id or (active.get("shard_id") if active else self.top_hud.state.get("shard_id", "--"))
        region = default_region or (active.get("region_raw") if active else self.top_hud.state.get("region_raw", ""))
        cur_name = default_name or (active.get("server_name") if active else self.top_hud.state.get("callsign", ""))
        full_id = default_full_id or self.top_hud.state.get("full_shard_id")
        if cur_name and cur_name.startswith("SHARD "):
            cur_name = ""

        top = self._spawn_centered_toplevel("TAG / RENAME SHARD", 480, 260)

        ctk.CTkLabel(
            top,
            text="// TAG / RENAME SERVER SHARD",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            text_color=SC_TEXT_CYAN
        ).pack(anchor="w", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            top,
            text=f"TARGET: SHARD {shard_id}  |  REGION: {(region or 'UNKNOWN').upper()}",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            top,
            text="Enter CIG's two-word queue codename (e.g. 'Innovative Technology')\nor a tactical callsign (e.g. 'Pyro PvP Haven'):",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_BRIGHT,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 8))

        ent = ctk.CTkEntry(
            top,
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            height=38,
            fg_color=SC_BG_CARD,
            border_color=SC_BORDER_CYAN,
            text_color=SC_TEXT_CYAN
        )
        ent.pack(fill="x", padx=20, pady=(0, 16))
        if cur_name:
            ent.insert(0, cur_name)
        ent.focus_set()

        def _save():
            val = ent.get().strip().upper()
            if val:
                updated = self.top_hud.set_custom_shard_name(shard_id, region, val, full_shard_id=full_id)
                if not updated:
                    self.log_comms("SHARD IDENTITY IS AMBIGUOUS; NAME WAS NOT CHANGED", level="warn")
                    return
                if hasattr(self, "btn_hdr_shard"):
                    short_n = val if len(val) <= 16 else val[:14] + ".."
                    self.btn_hdr_shard.configure(text=f"🏷️ {short_n}")
                self.log_comms(f"SHARD {shard_id} TAGGED AS '{val}'", level="ok")
                if hasattr(self, "_refresh_server_log_view"):
                    self._refresh_server_log_view()
            top.destroy()

        ent.bind("<Return>", lambda e: _save())

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="CANCEL",
            width=100,
            height=34,
            fg_color=SC_BG_CARD,
            hover_color=SC_BG_CARD_ALT,
            text_color=SC_TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=top.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="SAVE & UPDATE HUD",
            width=180,
            height=34,
            fg_color="#323a48",
            hover_color="#414b5c",
            border_width=1,
            border_color="#6c7c94",
            text_color=SC_TEXT_BRIGHT,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=_save
        ).pack(side="right")

    def open_set_medical_imprint_dialog(self):
        cur_med = self.cfg.get("medical_imprint", "UNKNOWN")
        top = self._spawn_centered_toplevel("RESPAWN NOTE (MANUAL)", 480, 290)

        ctk.CTkLabel(
            top,
            text="// RESPAWN NOTE — MANUAL ENTRY",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            text_color="#16a34a"
        ).pack(anchor="w", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            top,
            text=f"YOUR SAVED NOTE: {cur_med}",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            top,
            text="Write down the hospital or clinic you last chose.\nThis note does not sync with the game or verify your imprint.",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_BRIGHT,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 8))

        ent = ctk.CTkEntry(
            top,
            font=ctk.CTkFont(family=FONT_TECH, size=13, weight="bold"),
            height=38,
            fg_color=SC_BG_CARD,
            border_color="#16a34a",
            text_color="#16a34a"
        )
        ent.pack(fill="x", padx=20, pady=(0, 16))
        ent.insert(0, cur_med if cur_med != "UNKNOWN" else "")
        ent.focus_set()

        def _save():
            val = ent.get().strip().upper()
            if val:
                self.cfg["medical_imprint"] = val
                save_config(self.cfg)
                self.log_comms(f"MANUAL RESPAWN NOTE SAVED: '{val}'", level="ok")
            top.destroy()

        ent.bind("<Return>", lambda e: _save())

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="CANCEL",
            command=top.destroy,
            fg_color=SC_BG_CARD,
            hover_color=SC_BG_CARD_ALT,
            text_color=SC_TEXT_MUTED,
            border_width=1,
            border_color=SC_BORDER_DIM,
            width=100,
            height=34,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="SAVE NOTE",
            command=_save,
            fg_color="#18231c",
            hover_color="#223227",
            text_color="#48bb78",
            border_width=1,
            border_color="#2f573c",
            width=180,
            height=34,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold")
        ).pack(side="right")

    def open_edit_note_dialog(self, session_id):
        sess = next((s for s in self.server_logger.sessions if s.get("id") == session_id), None)
        if not sess:
            return

        top = self._spawn_centered_toplevel("TACTICAL SESSION NOTE", 520, 280)
        ctk.CTkLabel(
            top,
            text="// EDIT TACTICAL SESSION NOTE",
            font=ctk.CTkFont(family=FONT_TECH, size=15, weight="bold"),
            text_color=SC_TEXT_AMBER
        ).pack(anchor="w", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            top,
            text=f"SERVER: {sess.get('server_name', 'SHARD ' + sess.get('shard_id', ''))}  |  JOINED: {sess.get('joined_at_local', '--')}",
            font=ctk.CTkFont(family=FONT_MONO, size=10),
            text_color=SC_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 12))

        txt = ctk.CTkTextbox(
            top,
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            height=95,
            fg_color=SC_BG_CARD,
            border_color=SC_BORDER_DIM,
            text_color=SC_TEXT_BRIGHT
        )
        txt.pack(fill="x", padx=20, pady=(0, 16))
        txt.insert("1.0", sess.get("notes", ""))
        txt.focus_set()

        def _save():
            val = txt.get("1.0", "end-1c").strip()
            self.server_logger.set_session_note(session_id, val)
            self.log_comms(f"TACTICAL NOTE SAVED FOR {sess.get('server_name')}", level="ok")
            if hasattr(self, "_refresh_server_log_view"):
                self._refresh_server_log_view()
            top.destroy()

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="CANCEL",
            width=100,
            height=34,
            fg_color=SC_BG_CARD,
            hover_color=SC_BG_CARD_ALT,
            text_color=SC_TEXT_MUTED,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=top.destroy
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="SAVE NOTE",
            width=150,
            height=34,
            fg_color="#664400",
            hover_color="#805500",
            text_color=SC_TEXT_AMBER,
            font=ctk.CTkFont(family=FONT_TECH, size=11, weight="bold"),
            command=_save
        ).pack(side="right")

    def _on_shard_name_autodetected(self, found_name):
        sh_id = self.top_hud.state.get("shard_id", "--")
        reg = self.top_hud.state.get("region_raw", "")
        self.top_hud.set_custom_shard_name(sh_id, reg, found_name, source="loading_screen_ocr")
        if hasattr(self, "btn_hdr_shard"):
            short_n = found_name if len(found_name) <= 16 else found_name[:14] + ".."
            self.btn_hdr_shard.configure(text=f"🏷️ {short_n}")
        self.log_comms(f"CIG SHARD DETECTED // AUTO-NAMED '{found_name}'", level="ok")
        if hasattr(self, "_refresh_server_log_view"):
            self._refresh_server_log_view()

    # =========================================================================
    # BACKGROUND SCANNER & TELEMETRY LOOP (ZERO-LAG / BELOW-NORMAL PRIORITY)
    # =========================================================================

    def _read_terminal_image(self, image, terminal_gate=False):
        from screen_readers import read_image, refinery_orders, fabricator_candidates
        observed_at, station_hint = time.time(), self.terminal_station
        # The native reader understands actual terminal geometry. Preserve the
        # existing fabricator reader and conservative fallback for other layouts.
        from native_mining import native_refinery_orders
        try:
            result=self.detector.get_native_client(terminal=True).request_image(image,marker=False,refinery=True,
                        session=self.top_hud.state.get('session_token') or '')
            orders=native_refinery_orders(result,station_hint)
            if orders:return dict(observed_at=observed_at,orders=orders,blueprints=[])
        except Exception:
            logging.exception('Native terminal reader unavailable; using terminal OCR fallback')
        boxes = read_image(image, terminal_gate=terminal_gate)
        return dict(observed_at=observed_at, orders=refinery_orders(boxes, station_hint),
                    blueprints=fabricator_candidates(boxes))

    def _poll_terminal_screens(self, now):
        if not self.terminal_tracking or now - self.last_terminal_scan < 6:
            return
        self.last_terminal_scan = now
        if not is_star_citizen_foreground():
            return
        if not self.terminal_job_lock.acquire(blocking=False):
            return
        def worker():
            try:
                # Terminal reads use a separate worker, so its request lock does
                # not block mining marker reads. Both workers run below normal.
                image = self.detector.grab_full_game_monitor_pil()
                reading = self._read_terminal_image(image, terminal_gate=True)
                self.ui_events.put(('terminal_scan', reading, None))
            except Exception as exc:
                logging.exception('Terminal screen reader failed')
                self.ui_events.put(('terminal_scan', dict(error=str(exc), orders=[], blueprints=[]), None))
            finally:
                self.terminal_job_lock.release()
        threading.Thread(target=worker, daemon=True).start()

    def _apply_terminal_reading(self, reading, manual=False):
        if manual:
            self.btn_direct_snap.configure(text='[ SCAN REFINERY TERMINAL ]', state='normal')
        if reading.get('error'):
            self.terminal_panel.status.configure(text='Terminal reader: ' + reading['error'])
            return
        outcomes = []
        for order in reading['orders']:
            outcome = self.refinery_orders.observe(order, now=reading.get('observed_at'))
            outcomes.append(outcome)
            if outcome == 'completed':
                self.log_comms(f"REFINERY ORDER {order['number']} COMPLETED AT {order['station']}; MATERIALS AND QUALITIES LOGGED.", level='ok')
        candidates = reading['blueprints']
        self.fabricator_inbox.add(candidates)
        if candidates and hasattr(self, 'blueprint_page'):
            self.blueprint_page.add_candidates(candidates)
        if outcomes:
            self.terminal_panel.status.configure(text='Work orders: ' + ', '.join(outcomes).replace('_', ' ') + '. See Work orders for stock and qualities.')
            if any(o in ('completed', 'materials_updated') for o in outcomes) and hasattr(self, 'blueprint_page'):
                self.blueprint_page.refresh()
        elif candidates:
            self.terminal_panel.status.configure(text=f'{len(self.fabricator_pending)} fabricator names ready for ownership review in Blueprint Library.')
        elif manual:
            self.terminal_panel.status.configure(text='No readable order panel. Show full order number, processing/completed state, QUALITY and YIELD columns. Set the refinery station above if needed.')

    def _scanner_loop(self):
        # Attach background thread to user's visible 'Default' desktop and set THREAD_PRIORITY_LOWEST (-2)
        try:
            _u32 = ctypes.windll.user32
            _h_desk = _u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if _h_desk:
                _u32.SetThreadDesktop(_h_desk)
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), -2)
        except Exception:
            pass

        while self.is_running:
            now = time.time()

            # Loading screen shard codename auto-detection
            if getattr(self.top_hud.log_reader, "is_loading_screen", False) and (now - self.last_loading_ocr_scan) >= 1.5:
                self.last_loading_ocr_scan = now
                try:
                    cur_cs = self.top_hud.state.get("callsign", "")
                    if not cur_cs or cur_cs.startswith("SHARD ") or cur_cs == "AWAITING TELEMETRY":
                        found_name = self.detector.scan_loading_screen_for_shard_name()
                        if found_name:
                            self.ui_events.put(("shard_name", found_name, self.top_hud.state.get("session_token")))
                except Exception:
                    pass

            self._poll_terminal_screens(now)

            if not self.is_scanning:
                time.sleep(0.5)
                continue

            try:
                scan_token = self.top_hud.state.get('session_token')
                observed_at = time.time()
                self.detector.set_native_context(scan_token,self.native_fit)
                match, sig_num, _ = self.detector.scan_screen()
                native=self.detector.latest_native_result
                if native and native.get('observed_at'):
                    observed_at=native['observed_at']
                    self.ui_events.put(('native_scan',native,scan_token))
                message=self.detector.native_error or ('Reader loaded · waiting for Star Citizen in the foreground.' if native and native.get('inactive') else 'Native marker, panel and composition readers active.')
                if message!=self.native_reader_status:
                    self.ui_events.put(('native_status',message,None))
                if scan_token!=self.top_hud.state.get('session_token') or not 0<=time.time()-observed_at<=5:
                    match,sig_num=None,None
                now = time.time()
                if match and sig_num:
                    self.last_detected_sig = sig_num
                    self.last_match = match
                    self.last_match_time = now
                    if sig_num != self.last_spoken_sig:
                        self.last_spoken_sig = sig_num
                        self.voice.speak(match["speech"], cooldown=1.5)
                    self.root.after(0, self._on_signature_detected_mainthread, match, sig_num, scan_token, observed_at)
                else:
                    if self.last_spoken_sig != 0 and (now - self.last_match_time) > 5.0:
                        self.last_spoken_sig = 0
            except Exception as exc:
                logging.exception('Mining scanner failed')
                self.ui_events.put(('native_status','Mining reader error: '+str(exc),None))

            interval = max(0.65, self.cfg.get("poll_interval_ms", 650) / 1000.0)
            time.sleep(interval)

    def _hud_capture_loop(self):
        """Optional pixel source, separate from mining OCR and never touching Tk."""
        last_error = None
        failed_hwnd = None
        capture = WindowTelemetryCapture(lambda: self.top_hud.state.get("session_token"))
        try:
            while not self.telemetry_stop.is_set():
                try:
                    enabled = self.cfg.get("telemetry_capture_enabled", True)
                    hwnd = game_window_handle() if enabled else None
                    frame = None
                    if hwnd:
                        if (capture.hwnd != hwnd or capture.finished) and failed_hwnd != hwnd:
                            try:
                                capture.start(hwnd)
                                failed_hwnd = None
                            except Exception:
                                failed_hwnd = hwnd
                                capture.stop()
                                logging.exception("Window telemetry capture unavailable; using foreground desktop capture")
                        if capture.hwnd == hwnd:
                            frame = capture.take_latest()
                        elif is_star_citizen_foreground():
                            at, token = time.time(), self.top_hud.state.get("session_token")
                            frame = (self.detector.grab_displayinfo_pil(self.top_hud.get_capture_rect()), at, token)
                    else:
                        if capture.hwnd is not None:
                            capture.stop()
                        failed_hwnd = None
                    if frame and frame[2]:
                        shot, at, token = frame
                        result = self.top_hud.parse_captured_image_background(shot, token, observed_at=at)
                        try:
                            self.telemetry_queue.put_nowait(result)
                        except queue.Full:
                            try:
                                self.telemetry_queue.get_nowait()
                            except queue.Empty:
                                pass
                            self.telemetry_queue.put_nowait(result)
                    last_error = None
                except Exception as exc:
                    if str(exc) != last_error:
                        logging.exception("Telemetry capture failed")
                        last_error = str(exc)
                self.telemetry_stop.wait(max(0.75, self.cfg.get("top_hud_interval_ms", 750) / 1000))
        finally:
            capture.stop()

    def _on_signature_detected_mainthread(self, match, sig_num, session_token=None, observed_at=None):
        if observed_at is not None and (not session_token or session_token!=self.top_hud.state.get('session_token')
                                       or not 0<=time.time()-observed_at<=5):
            return
        self._present_mining_result(match, sig_num, observed_at=observed_at)
        self._update_gui_match(match, sig_num)

    def _apply_native_mining_reading(self, result, token):
        at=result.get('observed_at')
        if not token or token!=self.top_hud.state.get('session_token') or not isinstance(at,(int,float)) or not 0<=time.time()-at<=5:
            return
        panel=result.get('panel') or {}
        if result.get('_fit')!=self.native_fit:
            result=dict(result)
            result.pop('advice',None)
        if panel.get('settled') and panel.get('stats'):
            self.native_rock=dict(panel=panel,advice=result.get('advice'),observed_at=at,session_token=token)
            self.top_hud.update_rock(result,at)
        fit=result.get('loadout') or {}
        if fit.get('complete'):
            self.native_detected_fit=dict(fit,observed_at=at,session_token=token)

    def _present_mining_result(self, match, signature, manual=False, observed_at=None):
        if hasattr(self,'top_hud'):
            options = dict(manual=manual)
            if observed_at is not None:
                options['observed_at'] = observed_at
            self.top_hud.update_mining(match,signature,**options)
            if self.top_hud.layout!='ribbon':
                return
        self.overlay.show_result(match,signature)

    def _telemetry_tick(self):
        if not self.is_running:
            return

        # A single main-thread owner tails the game log and merges observations.
        # Visibility is a presentation preference, not a collection switch.
        latest = None
        while True:
            try:
                latest = self.telemetry_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.top_hud.update_from_image_and_logs(latest)
            while not self.ui_events.empty():
                kind, value, token = self.ui_events.get_nowait()
                if kind in ('terminal_scan', 'terminal_manual'):
                    self._apply_terminal_reading(value, manual=(kind == 'terminal_manual'))
                elif kind == 'fabricator_scan':
                    if hasattr(self, 'blueprint_page'):
                        self.blueprint_page.scan_finished(*value)
                elif kind == 'native_scan':
                    self._apply_native_mining_reading(value,token)
                elif kind == 'native_status':
                    self.native_reader_status=value
                elif kind == "shard_name" and token and token == self.top_hud.state.get("session_token"):
                    self._on_shard_name_autodetected(value)
            self._refresh_active_server()
        except Exception:
            logging.exception("Telemetry update failed")

        if hasattr(self, "btn_hdr_shard"):
            cs = self.top_hud.state.get("callsign", "TAG SHARD")
            short_cs = cs if len(cs) <= 16 else cs[:14] + ".."
            if getattr(self, "_last_hdr_shard_txt", None) != short_cs:
                self._last_hdr_shard_txt = short_cs
                self.btn_hdr_shard.configure(text=f"🏷️ {short_cs}")

        try:
            self.overlay.check_idle()
        except Exception:
            pass

        sc_focused = is_star_citizen_foreground()
        if not sc_focused:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            if hasattr(self, "lbl_clock") and getattr(self, "_last_clock_str", None) != now_str:
                self._last_clock_str = now_str
                self.lbl_clock.configure(text=f"LOCAL TELEMETRY // {now_str}")
            if self.is_scanning:
                self._draw_mini_radar_scope()

        self.root.after(500, self._telemetry_tick)

    def _draw_mini_radar_scope(self):
        if not hasattr(self, "mini_radar_canvas"):
            return
        c = self.mini_radar_canvas
        c.delete("all")
        w, h = 195, 130
        cx, cy = w // 2, h // 2
        r = 48

        # Grid lines
        c.create_line(0, cy, w, cy, fill="#161920")
        c.create_line(cx, 0, cx, h, fill="#161920")
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#262d3a", width=1)
        c.create_oval(cx - 24, cy - 24, cx + 24, cy + 24, outline="#1c2027", width=1)

        if self.is_scanning:
            self.radar_sweep_angle = (self.radar_sweep_angle + 12) % 360
            rad = math.radians(self.radar_sweep_angle)
            sx = cx + int(r * math.cos(rad))
            sy = cy + int(r * math.sin(rad))
            c.create_line(cx, cy, sx, sy, fill=SC_TEXT_CYAN, width=2)

        # If recent match within 5 seconds, highlight target blip
        if self.last_match and (time.time() - self.last_match_time) < 5.0:
            c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=SC_TEXT_AMBER, outline=SC_TEXT_BRIGHT)
            c.create_text(8, 12, text=f"RS {self.last_detected_sig:,}", anchor="w", fill=SC_TEXT_AMBER, font=(FONT_MONO, 8, "bold"))
        else:
            c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=SC_TEXT_CYAN, outline="")
            state_txt = "SCANNING" if self.is_scanning else "PAUSED"
            c.create_text(8, 12, text=state_txt, anchor="w", fill=SC_TEXT_CYAN if self.is_scanning else SC_TEXT_RED, font=(FONT_MONO, 8, "bold"))

        c.create_text(w - 8, 12, text=f"MON {self.cfg.get('game_monitor', 1)}", anchor="e", fill=SC_TEXT_MUTED, font=(FONT_MONO, 8, "bold"))

    def _update_gui_match(self, match, sig_num):
        # HUD scanning also works before the optional signature-tools page exists.
        if not hasattr(self,'lbl_live_title'):
            return
        self.lbl_live_title.configure(text=match["title"].upper(), text_color=SC_TEXT_CYAN)
        sub_text = f"RS {sig_num:,} // {match_summary(match)}\n{match['details']}"
        self.lbl_live_sub.configure(text=sub_text, text_color=SC_TEXT_BRIGHT)
        self.lbl_live_sub.configure(wraplength=380, justify="left")

        self.lbl_rail_sig.configure(text=match["title"].upper(), text_color=SC_TEXT_AMBER)
        self.lbl_rail_sub.configure(text=f"RS: {sig_num:,} // {len(match['candidates'])} MATCH(ES)", text_color=SC_TEXT_CYAN)

        self._draw_large_reticle(match, sig_num)

    # =========================================================================
    # USER CONTROLS & CALLBACKS
    # =========================================================================
    def on_manual_test(self):
        txt = self.entry_test_sig.get().strip().replace(",", "")
        if not txt.isdigit():
            self.log_comms("ENTER A NUMERIC RS SIGNATURE TO DECODE.", level="warn")
            return
        sig = int(txt)
        match = parse_signature(sig)
        if match:
            self.last_detected_sig = sig
            self.last_match = match
            self.last_match_time = time.time()
            self._update_gui_match(match, sig)
            self.voice.speak(match["speech"], cooldown=0, allow_when_game_closed=True)
            self._present_mining_result(match, sig, manual=True)
            self.log_comms(f"SIGNATURE DECODED: {sig:,} RS -> {match['details']} ({match_summary(match)})", level="ok")
        else:
            self.lbl_live_title.configure(text=f"UNCLASSIFIED RS: {sig:,}", text_color=SC_TEXT_RED)
            self.lbl_live_sub.configure(text="UNRESOLVED BY SINGLE-FIELD SC 4.10 TABLES; MIXED SIGNALS NOT YET SUPPORTED", text_color=SC_TEXT_RED, wraplength=380)
            self._draw_large_reticle(None, None)
            self.log_comms(f"RS {sig:,} DOES NOT MATCH KNOWN DEPOSIT MULTIPLIERS.", level="warn")

    def fill_test_sig(self, sig):
        self.entry_test_sig.delete(0, "end")
        self.entry_test_sig.insert(0, str(sig))
        self.on_manual_test()

    def toggle_voice_mute(self):
        cur_en = bool(self.cfg.get("voice_enabled", True))
        new_en = not cur_en
        self.cfg["voice_enabled"] = new_en
        self.voice.set_enabled(new_en)
        cur_vol = int(self.cfg.get("voice_volume", 80))

        if hasattr(self, "btn_hdr_mute"):
            if new_en and cur_vol > 0:
                self.btn_hdr_mute.configure(
                    text=f"🔊 {cur_vol}%",
                    fg_color="#262b35",
                    hover_color="#343c4a",
                    text_color=SC_TEXT_CYAN,
                    border_color="#4f596b"
                )
            else:
                self.btn_hdr_mute.configure(
                    text="🔇 MUTED",
                    fg_color="#2a1619",
                    hover_color="#381d22",
                    text_color=SC_TEXT_RED,
                    border_color="#5a2930"
                )

        if hasattr(self, "sw_voice"):
            if new_en:
                self.sw_voice.select()
            else:
                self.sw_voice.deselect()

        save_config(self.cfg)
        status_str = f"UNMUTED ({cur_vol}%)" if new_en else "MUTED"
        self.log_comms(f"VOICE AUDIO {status_str}.", level="ok" if new_en else "warn")

    def on_hdr_volume_change(self, val):
        vol = max(0, min(100, int(val)))
        self.cfg["voice_volume"] = vol
        self.voice.set_volume(vol)

        cur_en = bool(self.cfg.get("voice_enabled", True))
        if hasattr(self, "btn_hdr_mute"):
            if cur_en and vol > 0:
                self.btn_hdr_mute.configure(
                    text=f"🔊 {vol}%",
                    fg_color="#262b35",
                    hover_color="#343c4a",
                    text_color=SC_TEXT_CYAN,
                    border_color="#4f596b"
                )
            else:
                self.btn_hdr_mute.configure(
                    text="🔇 MUTED",
                    fg_color="#2a1619",
                    hover_color="#381d22",
                    text_color=SC_TEXT_RED,
                    border_color="#5a2930"
                )

        if hasattr(self, "slider_vol"):
            try:
                self.slider_vol.set(vol)
            except Exception:
                pass

        save_config(self.cfg)

    def on_voice_toggle(self):
        en = bool(self.sw_voice.get())
        self.cfg["voice_enabled"] = en
        self.voice.set_enabled(en)
        cur_vol = int(self.cfg.get("voice_volume", 80))

        if hasattr(self, "btn_hdr_mute"):
            if en and cur_vol > 0:
                self.btn_hdr_mute.configure(
                    text=f"🔊 {cur_vol}%",
                    fg_color="#262b35",
                    hover_color="#343c4a",
                    text_color=SC_TEXT_CYAN,
                    border_color="#4f596b"
                )
            else:
                self.btn_hdr_mute.configure(
                    text="🔇 MUTED",
                    fg_color="#2a1619",
                    hover_color="#381d22",
                    text_color=SC_TEXT_RED,
                    border_color="#5a2930"
                )

        save_config(self.cfg)
        self.log_comms(f"VOICE CALLOUTS {'ENABLED' if en else 'MUTED'}.", level="info")

    def on_chime_toggle(self):
        en = bool(self.sw_chime.get())
        self.cfg["voice_chime"] = en
        self.voice.set_chime(en)
        save_config(self.cfg)
        self.log_comms(f"COCKPIT HARMONIC PRE-CHIME {'ENABLED' if en else 'DISABLED'}.", level="info")

    def on_voice_profile_change(self, selected_label):
        prof_key = self._profile_label_to_key.get(selected_label, "origin")
        self.cfg["voice_profile"] = prof_key
        self.voice.set_profile(prof_key)
        save_config(self.cfg)
        self.voice.speak(f"{prof_key.capitalize()} ship computer online.", cooldown=0, allow_when_game_closed=True)
        self.log_comms(f"SHIP COMPUTER VOICE PROFILE SET TO: {selected_label}", level="ok")

    def on_volume_change(self, val):
        vol = max(0, min(100, int(val)))
        self.cfg["voice_volume"] = vol
        self.voice.set_volume(vol)

        cur_en = bool(self.cfg.get("voice_enabled", True))
        if hasattr(self, "btn_hdr_mute"):
            if cur_en and vol > 0:
                self.btn_hdr_mute.configure(
                    text=f"🔊 {vol}%",
                    fg_color="#262b35",
                    hover_color="#343c4a",
                    text_color=SC_TEXT_CYAN,
                    border_color="#4f596b"
                )
            else:
                self.btn_hdr_mute.configure(
                    text="🔇 MUTED",
                    fg_color="#2a1619",
                    hover_color="#381d22",
                    text_color=SC_TEXT_RED,
                    border_color="#5a2930"
                )

        if hasattr(self, "slider_hdr_vol"):
            try:
                self.slider_hdr_vol.set(vol)
            except Exception:
                pass

        save_config(self.cfg)

    def on_rate_change(self, val):
        self.cfg["voice_rate"] = int(val)
        self.voice.set_rate(int(val))

    def on_overlay_toggle(self):
        self.set_mining_hud_enabled(bool(self.sw_overlay.get()))

    def set_mining_hud_enabled(self, en):
        en = bool(en)
        self.cfg["overlay_enabled"] = en
        self.sync_mining_overlay_visibility()
        if hasattr(self,'sw_overlay'):
            self.sw_overlay.select() if en else self.sw_overlay.deselect()
        save_config(self.cfg)
        self.log_comms(f"MINING HUD {'ENABLED' if en else 'HIDDEN'}.", level="info")

    def sync_mining_overlay_visibility(self):
        self.top_hud.set_mining_enabled(self.cfg.get('overlay_enabled',False))
        visible = self.top_hud.mining_enabled and self.top_hud.layout=='ribbon'
        if self.overlay.is_visible != visible:
            self.overlay.set_visible(visible)

    def _hud_preferences_changed(self, changes):
        self.cfg.update(changes)
        save_config(self.cfg)
        if 'hud_layout' in changes:
            self.sync_mining_overlay_visibility()

    def on_top_hud_toggle(self, enabled=None):
        en = bool(self.sw_top_hud.get()) if enabled is None else bool(enabled)
        self.cfg["top_hud_enabled"] = en
        self.top_hud.set_enabled(en)
        if hasattr(self, "sw_top_hud"):
            self.sw_top_hud.select() if en else self.sw_top_hud.deselect()
        save_config(self.cfg)
        self.log_comms(f"HUD SESSION DETAILS {'ENABLED' if en else 'HIDDEN'}.", level="ok" if en else "info")


    def on_opacity_change(self, val):
        self.cfg["overlay_opacity"] = round(float(val), 2)
        self.overlay.set_opacity(val)
        self.top_hud.set_opacity(val)

    def set_overlay_preset(self, x, y):
        self.cfg["overlay_x"] = int(x)
        self.cfg["overlay_y"] = int(y)
        self.overlay.set_position(x, y)
        save_config(self.cfg)
        self.log_comms(f"HUD OVERLAY ANCHORED TO ({x}, {y}) ON MONITOR {self.cfg.get('game_monitor', 1)}.", level="info")

    def toggle_scanning(self):
        self.is_scanning = not self.is_scanning
        if self.is_scanning:
            self.btn_toggle_scan.configure(
                text="● RADAR: ONLINE",
                fg_color="#072b22",
                border_color=SC_TEXT_GREEN,
                text_color=SC_TEXT_GREEN
            )
            self.log_comms("RETICLE RADAR SCANNER RESUMED.", level="ok")
        else:
            self.btn_toggle_scan.configure(
                text="○ RADAR: STANDBY",
                fg_color="#2a0f18",
                border_color=SC_TEXT_RED,
                text_color=SC_TEXT_RED
            )
            self.log_comms("RETICLE RADAR SCANNER PAUSED.", level="warn")

    def save_all_settings(self):
        save_config(self.cfg)
        self.voice.speak("Configuration saved", cooldown=0, allow_when_game_closed=True)
        self.log_comms("SYSTEM CONFIGURATION SAVED TO DISK.", level="ok")

    # =========================================================================
    # SYSTEM TRAY INTEGRATION
    # =========================================================================
    def _init_tray(self):
        from auto_launch import shortcut_path
        img = Image.new("RGBA", (64, 64), (15, 17, 21, 255))
        d = ImageDraw.Draw(img)
        d.polygon([(32, 4), (58, 18), (58, 46), (32, 60), (6, 46), (6, 18)], outline=(101, 115, 136, 255), fill=(32, 36, 46, 255))
        d.ellipse((22, 22, 42, 42), outline=(217, 155, 67, 255), fill=(86, 98, 117, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Open SynthScan MFD", self.show_from_tray, default=True),
            pystray.MenuItem("Toggle Voice Mute", lambda icon, item: self.root.after(0, self.toggle_voice_mute)),
            pystray.MenuItem("Snap UI to Monitor 2", lambda icon, item: self.root.after(0, lambda: self._center_on_monitor(2 if len(self.monitors) >= 2 else 1))),
            pystray.MenuItem("Snap UI to Monitor 1", lambda icon, item: self.root.after(0, lambda: self._center_on_monitor(1))),
            pystray.MenuItem("Toggle HUD session details", lambda icon, item: self.root.after(0, lambda: self.on_top_hud_toggle(not self.top_hud.enabled))),
            pystray.MenuItem("Edit / lock HUD position", lambda icon, item: self.root.after(0, lambda:self.top_hud.set_editing(not self.top_hud.editing)),
                             checked=lambda item:self.top_hud.editing),
            pystray.MenuItem("Compact classic ribbon", lambda icon, item: self.root.after(0, self.toggle_compact_hud),
                             checked=lambda item: self.top_hud.compact),
            pystray.MenuItem("Auto-start with Star Citizen", lambda icon, item: self.root.after(0, self.toggle_game_autolaunch),
                             checked=lambda item: shortcut_path().exists()),
            pystray.MenuItem("Toggle Radar Scanner", lambda icon, item: self.root.after(0, self.toggle_scanning)),
            pystray.MenuItem("Exit SynthScan", self.exit_app)
        )
        self.tray = pystray.Icon("SynthScan", img, "SynthScan // Star Citizen MFD", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def hide_to_tray(self):
        save_config(self.cfg)
        self.root.withdraw()

    def show_from_tray(self, icon=None, item=None):
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        try:
            # CTk can report its initial 200px size while a startup window is
            # withdrawn. Reapply the saved logical geometry before first show.
            self._apply_initial_window_geometry()
            self.root.deiconify()
            self.root.state('normal')
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def exit_app(self, icon=None, item=None):
        self.is_running = False
        self.telemetry_stop.set()
        self.bp_manager.stop_watcher()
        self.patch_watcher.stop()
        self.top_hud.close()
        self.detector.close()
        save_config(self.cfg)
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.after(0, self.root.quit)
        sys.exit(0)


if __name__ == "__main__":
    try:
        app = SynthScanApp(start_hidden="--autostart" in sys.argv)

        def check_show_request():
            if _show_request.wait():
                app._restore_window()
            if app.is_running:
                app.root.after(500, check_show_request)

        app.root.after(500, check_show_request)
        app.root.mainloop()
    except SystemExit:
        raise
    except Exception:
        logging.exception("SynthScan startup failed")
        raise
    finally:
        _show_request.close()
        _app_lock.close()
