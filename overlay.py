"""
SynthScan - Star Citizen Helmet / MFD HUD Overlay
Displays real-time radar signature telemetry directly over Star Citizen on the Game Monitor.
Uses tk.Toplevel attached to the main application root (preventing dual-Tk event loop bugs).
Click-through, frameless, and always-on-top.
"""

import tkinter as tk
import ctypes
import time
from config import get_monitor_by_id


class HUDOverlay:
    WIDTH = 340
    HEIGHT = 106

    def __init__(self, master, x=40, y=60, opacity=0.88, visible=True, game_monitor=1):
        self.master = master
        self.x = int(x)
        self.y = int(y)
        self.opacity = float(opacity)
        self.is_visible = bool(visible)
        self.game_monitor = int(game_monitor)
        self.last_update = 0
        self.win = None
        self.canvas = None
        self._init_window()

    def _compute_screen_xy(self):
        mon = get_monitor_by_id(self.game_monitor)
        return mon["left"] + self.x, mon["top"] + self.y

    def _init_window(self):
        self.win = tk.Toplevel(self.master)
        self.win.title("SynthScan MFD Overlay")
        self.win.overrideredirect(True)
        self.win.wm_attributes("-topmost", True)
        self.win.wm_attributes("-alpha", self.opacity)
        sx, sy = self._compute_screen_xy()
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{sx}+{sy}")
        self.win.configure(bg="#0f1115")

        self.canvas = tk.Canvas(
            self.win,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="#14171d",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._draw_hud(
            accent="#d0d7e2",
            badge="STANDBY // RETICLE LINK",
            title="AWAITING RADAR PING",
            details="AIM SHIP CROSSHAIR AT PING MARKER",
            conf=0
        )

        self.win.update_idletasks()
        self._make_clickthrough()

        if not self.is_visible:
            self.win.withdraw()

    def _make_clickthrough(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            if not hwnd:
                hwnd = self.win.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        except Exception:
            pass

    def _draw_hud(self, accent, badge, title, details, conf=0):
        c = self.canvas
        c.delete("all")
        w, h = self.WIDTH, self.HEIGHT

        # Subtle HUD grid lines
        c.create_rectangle(2, 2, w - 2, h - 2, fill="#181b22", outline="#2c323e", width=1)
        c.create_line(2, 26, w - 2, 26, fill="#262b35", width=1)

        # Star Citizen MFD Corner Brackets
        blen = 14
        # Top-Left
        c.create_line(2, 2, 2 + blen, 2, fill=accent, width=2)
        c.create_line(2, 2, 2, 2 + blen, fill=accent, width=2)
        # Top-Right
        c.create_line(w - 2 - blen, 2, w - 2, 2, fill=accent, width=2)
        c.create_line(w - 2, 2, w - 2, 2 + blen, fill=accent, width=2)
        # Bottom-Left
        c.create_line(2, h - 2 - blen, 2, h - 2, fill=accent, width=2)
        c.create_line(2, h - 2, 2 + blen, h - 2, fill=accent, width=2)
        # Bottom-Right
        c.create_line(w - 2 - blen, h - 2, w - 2, h - 2, fill=accent, width=2)
        c.create_line(w - 2, h - 2 - blen, w - 2, h - 2, fill=accent, width=2)

        # Left vertical telemetry bar
        c.create_rectangle(6, 32, 9, h - 10, fill=accent, outline="")

        # Header Telemetry Tag
        c.create_text(
            12, 14,
            text=f"// {badge}",
            anchor="w",
            fill=accent,
            font=("Bahnschrift", 8, "bold")
        )
        c.create_text(
            w - 12, 14,
            text="MFD.RADAR.01",
            anchor="e",
            fill="#7e889b",
            font=("Consolas", 8, "bold")
        )

        # Main Target Title
        c.create_text(
            18, 46,
            text=title.upper(),
            anchor="w",
            fill="#f8fafc",
            font=("Bahnschrift", 14, "bold")
        )

        # Subtitle (RS Signature & Base)
        c.create_text(
            18, 70,
            text=details,
            anchor="w",
            fill=accent if conf > 0 else "#7e889b",
            font=("Consolas", 9, "bold")
        )

        # Confidence / Signal Lock Bar at bottom
        bar_x1, bar_y1, bar_x2, bar_y2 = 18, 86, w - 16, 92
        c.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, fill="#12151b", outline="#2c323e")
        if conf > 0:
            fill_w = int((bar_x2 - bar_x1) * max(0.0, min(1.0, conf / 100.0)))
            if fill_w > 0:
                c.create_rectangle(bar_x1, bar_y1, bar_x1 + fill_w, bar_y2, fill=accent, outline="")

    def show_result(self, match_info, sig_value):
        if not self.is_visible:
            return
        self.last_update = time.time()
        try:
            self.win.deiconify()
        except Exception:
            pass

        colors = {
            "ship_mining": ("#d0d7e2", "MINERAL SIGNATURE // SC 4.10"),
            "roc": ("#48bb78", "ROC FIELD // ORE UNKNOWN"),
            "hand": ("#48bb78", "HAND MINING // ORE UNKNOWN"),
            "salvage": ("#d99b43", "CONTEXT NEEDED"),
            "ambiguous": ("#d99b43", "AMBIGUOUS // CHECK CANDIDATES"),
            "asteroid": ("#d0d7e2", "ASTEROID CLUSTER"),
            "surface":  ("#d99b43", "SURFACE DEPOSIT"),
            "gemstone": ("#48bb78", "GEMSTONE NODE"),
            "derelict": ("#e05260", "SALVAGE // WRECK")
        }
        accent, badge = colors.get(match_info.get("type", ""), ("#d0d7e2", "SIGNATURE LOCK"))
        conf = round(match_info.get("ocr_confidence", 0) * 100)
        details_txt = f"RS {sig_value:,} // EXACT TABLE MATCH"
        if match_info.get("ocr_confidence") is not None:
            details_txt += f" // OCR {conf}%"
        title = match_info.get("title", "UNKNOWN")
        if match_info.get("ambiguous"):
            # Keep the existing compact overlay; list all alternatives in-app.
            short = {"roc": "ROC", "hand": "Hand", "salvage": "Salvage/harvest"}
            labels = [f"{row['count']}x {short.get(row['category'], row['name'])}" for row in match_info["candidates"]]
            details_txt = f"RS {sig_value:,} // " + " | ".join(labels[:2])
            if len(labels) > 2:
                details_txt += f" (+{len(labels)-2})"

        self._draw_hud(
            accent=accent,
            badge=badge,
            title=title,
            details=details_txt,
            conf=conf
        )

    def clear(self):
        self._draw_hud(
            accent="#00b8d4",
            badge="STANDBY // RETICLE LINK",
            title="READY - WAITING FOR PING",
            details="AIM SHIP CROSSHAIR AT PING MARKER",
            conf=0
        )

    def set_game_monitor(self, mon_id):
        self.game_monitor = int(mon_id)
        self.set_position(self.x, self.y)

    def set_position(self, x, y):
        self.x = int(x)
        self.y = int(y)
        sx, sy = self._compute_screen_xy()
        try:
            self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{sx}+{sy}")
        except Exception:
            pass

    def set_opacity(self, opacity):
        self.opacity = float(opacity)
        try:
            self.win.wm_attributes("-alpha", self.opacity)
        except Exception:
            pass

    def set_visible(self, visible):
        self.is_visible = bool(visible)
        try:
            if self.is_visible:
                self.win.deiconify()
            else:
                self.win.withdraw()
        except Exception:
            pass

    def check_idle(self):
        if self.last_update > 0 and (time.time() - self.last_update) > 5.0:
            self.clear()
            self.last_update = 0
