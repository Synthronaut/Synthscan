"""Main-thread HUD controller. Workers return observations, never mutate its state."""
import ctypes
from pathlib import Path
import time
import tkinter as tk
import tkinter.font as tkfont

from config import get_monitor_by_id, load_config, save_config
from displayinfo_reader import translate_location, translate_region
from validated_displayinfo import ValidatedDisplayInfoReader
from hud_appearance import render_original_bar
from network_source import read_network_ping
from frame_source import read_client_fps
from hud_layout import preferences, placed_rect, position_from_point, panel_rows, bounded
from hud_panel import paint_panel, panel_size
from telemetry_core import EvidenceHealth, IncrementalGameLog, MetricStore, ShardHistory, SHARD_RE, METRIC_LIMITS

BASE_DIR = Path(__file__).resolve().parent


def game_window_rect():
    """Physical coordinates; do not clamp away monitors with negative origins."""
    from ctypes import wintypes
    user = ctypes.windll.user32
    user.FindWindowW.restype = wintypes.HWND
    hwnd = user.FindWindowW("CryENGINE", None)
    if not hwnd or not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right - rect.left < 400 or rect.bottom - rect.top < 300:
        return None
    return {"left": rect.left, "top": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}


class TopTelemetryHUD:
    BAR_HEIGHT = 28

    def __init__(self, master, game_monitor=1, enabled=True, opacity=0.70, server_logger=None,
                 game_log_path=None, history_path=None):
        self.master = master
        self.game_monitor = int(game_monitor)
        self.enabled = enabled
        self.opacity = opacity
        self.server_logger = server_logger
        self.cfg = load_config()
        self.layout_options = preferences(self.cfg)
        self.layout = self.layout_options['layout']
        self.scale = self.layout_options['scale']
        self.position = {k:self.layout_options[k] for k in ('x','y')}
        self.editing = False
        self.mining = None
        self.rock = None
        self.mining_enabled = bool(self.cfg.get('overlay_enabled', False))
        self.on_preferences_changed = None
        self._drag_origin = None
        self._redraw_job = None
        self.compact = bool(self.cfg.get("top_hud_compact", True))
        self.BAR_HEIGHT = 24 if self.compact else 28
        self._content_width = None
        self.medical_imprint = self.cfg.get("medical_imprint", "UNKNOWN")
        self.bitmap_reader = ValidatedDisplayInfoReader()
        self.log_reader = IncrementalGameLog(**({"log_path": game_log_path} if game_log_path else {}), translate_location=translate_location)
        self.shard_tracker = ShardHistory(history_path or BASE_DIR / "shard_history.json")
        self.metric_store = MetricStore(ttl=5)
        self.health_evaluator = EvidenceHealth()
        self.on_health_alert_cb = None
        self.state = {}
        self._server_identity = None
        self._last_rendered_key = None
        self.bar_win = None
        self.bar_canvas = None
        self.font = tkfont.Font(root=master, family="Consolas", size=9, weight="bold")
        self.update_from_image_and_logs(redraw=False)
        self._init_windows()

    def _init_windows(self):
        self.bar_win = tk.Toplevel(self.master)
        self.bar_win.title("SynthScan Top Telemetry HUD")
        self.bar_win.overrideredirect(True)
        self.bar_win.wm_attributes("-topmost", True)
        self.bar_win.wm_attributes("-alpha", self.opacity)
        self.bar_win.configure(bg="#070a0f")
        self.bar_canvas = tk.Canvas(self.bar_win, height=self.BAR_HEIGHT, bg="#070a0f", highlightthickness=0, bd=0)
        self.bar_canvas.pack(fill=tk.BOTH, expand=True)
        self.bar_canvas.bind('<ButtonPress-1>', self._drag_start)
        self.bar_canvas.bind('<B1-Motion>', self._drag_move)
        self.bar_canvas.bind('<ButtonRelease-1>', self._drag_end)
        self.bar_canvas.bind('<Button-3>', lambda event: self.set_editing(False) if self.editing else None)
        self.bar_canvas.bind('<Configure>',self._canvas_resized)
        self._place_bar()
        self.bar_win.update_idletasks()
        self._apply_input_mode()
        self._sync_visibility()
        self.render_bar()

    def _place_bar(self):
        monitor = get_monitor_by_id(self.game_monitor)
        rect = game_window_rect() or monitor
        if self.layout=='panel':
            rows = self.presentation_rows()
            base_width,base_height = panel_size(rows)
            self._render_scale = min(self.scale,max(1,rect['width']-24)/base_width,max(1,rect['height']-16)/base_height)
            desired,height = panel_size(rows,self._render_scale)
        else:
            desired = self._content_width if self.compact and self._content_width else 1680
            height = 24 if self.compact else 28
        placed = placed_rect(rect,min(desired,max(1,rect['width']-24)),height,self.position)
        self.bar_width, self.BAR_HEIGHT = placed['width'], placed['height']
        geometry = f"{self.bar_width}x{self.BAR_HEIGHT}{placed['left']:+d}{placed['top']:+d}"
        if getattr(self, "_last_geometry", None) != geometry:
            self._last_geometry = geometry
            # Tk's negative geometry offsets mean "from the right/bottom".
            # Native absolute placement correctly handles monitors left of zero.
            self.bar_win.geometry(f'{self.bar_width}x{self.BAR_HEIGHT}')
            self.bar_win.update_idletasks()
            user = ctypes.windll.user32
            from ctypes import wintypes
            user.GetParent.argtypes = [wintypes.HWND]
            user.GetParent.restype = wintypes.HWND
            hwnd = user.GetParent(self.bar_win.winfo_id()) or self.bar_win.winfo_id()
            user.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
            user.SetWindowPos(hwnd,None,placed['left'],placed['top'],self.bar_width,self.BAR_HEIGHT,0x14)
            self.bar_canvas.configure(width=self.bar_width,height=self.BAR_HEIGHT)
            self._last_rendered_key = None

    def _sync_visibility(self):
        if not self.bar_win:
            return
        game = game_window_rect() is not None
        active_mining = any(r['role']=='section' for r in self.presentation_rows(session=False))
        visible = self.editing or (game and (self.enabled or (self.layout=='panel' and active_mining)))
        if visible != getattr(self, "_visible", None):
            self._visible = visible
            if visible:
                self.bar_win.deiconify()
                self.bar_win.lift()
            else:
                self.bar_win.withdraw()
        if visible:
            self._place_bar()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self._sync_visibility()
        self.render_bar()

    def set_game_monitor(self, mon_id):
        self.game_monitor = int(mon_id)
        self._place_bar()
        self.render_bar()

    def get_capture_rect(self):
        rect = game_window_rect() or get_monitor_by_id(self.game_monitor)
        width = min(1400, rect["width"])
        return {"left": rect["left"] + rect["width"] - width, "top": rect["top"],
                "width": width, "height": min(380, rect["height"])}

    def parse_captured_image_background(self, image, session_token=None, observed_at=None):
        """Optional debug-text decoder; called only by the dedicated capture worker."""
        previous = self.bitmap_reader.parse_image(None)
        previous["shard_id"] = self.state.get("shard_id", "--")
        parsed = self.bitmap_reader.parse_image(image, previous)
        # Recognition validates fields individually after checking row geometry.
        # An obscured server name/restart count must not erase a readable ping.
        validated = parsed.pop("_validated_fields", ())
        for key in METRIC_LIMITS:
            if key not in validated:
                parsed[key] = None
        if "server_name" not in validated:
            parsed["server_name"] = parsed["srv_id"] = "--"
        shard, local = parsed.get("shard_pop"), parsed.get("srv_pop")
        if shard is not None and local is not None and not 0 <= local <= shard <= 100000:
            parsed["shard_pop"] = parsed["srv_pop"] = None
        parsed["_session_token"] = session_token
        parsed["_observed_at"] = time.time() if observed_at is None else observed_at
        return parsed

    def _apply_log_events(self, events):
        if not self.server_logger:
            return
        for event in events:
            if event["type"] == "left":
                self.server_logger.end_session(event["at"], event.get("reason", "disconnected"))
            elif event["type"] == "joined":
                match = SHARD_RE.fullmatch(event["full_shard_id"])
                self.server_logger.start_new_session(*match.groups(), joined_at=event["at"], ip=event.get("ip", ""))
            elif event["type"] == "location":
                self.server_logger.record_location(event["name"], observed_at=event["at"])

    def update_from_image_and_logs(self, parsed_state=None, redraw=True, game_running=None):
        if game_running is None:
            from app_lifecycle import game_process_ids
            game_running = bool(game_process_ids())
        now = time.time()
        if game_running:
            self.log_reader.poll()
        else:
            stopped = self.log_reader.connection_status != "game_closed"
            self.log_reader.reset("game_closed")
            self.log_reader.drain_events()
            if stopped:
                self.log_reader.rewind()
        self._apply_log_events(self.log_reader.drain_events())
        reader = self.log_reader
        token = reader.session_token if game_running and reader.connected else None
        if token != self.metric_store.session:
            self._server_identity = None
            self.mining = None
            self.rock = None
        self.metric_store.set_session(token)
        if not token:
            self._server_identity = None
            self.shard_tracker.leave_current()
            if self.server_logger:
                self.server_logger.end_session(reason="disconnected")
        else:
            for key, observation in reader.observations.items():
                self.metric_store.ingest({key: observation.value}, observation.source, observation.observed_at, token)
            if (parsed_state and parsed_state.get("_session_token") == token
                    and -1 <= now - parsed_state["_observed_at"] <= 5
                    and (self._server_identity is None or parsed_state["_observed_at"] >= self._server_identity[1])):
                name = parsed_state.get("server_name")
                if self._server_identity and name not in (None, "--", self._server_identity[0]):
                    # An authority/server transition can happen inside one shard.
                    # Do not carry the former node's FPS or population forward.
                    self.metric_store.observations.clear()
                    reader.observations.clear()
                    self.health_evaluator.stall_start_ts = None
                self.metric_store.ingest(parsed_state, "displayinfo_capture", parsed_state["_observed_at"], token)
                if parsed_state.get("server_name") not in (None, "--"):
                    self._server_identity = (parsed_state["server_name"], parsed_state["_observed_at"])
            network = read_network_ping(reader, now)
            if network:
                self.metric_store.ingest({'ping_ms': network['ping_ms']}, network['source'], network['observed_at'], token)
        frames = read_client_fps(now) if game_running else None
        if frames and token:
            self.metric_store.ingest({'client_fps': frames['client_fps']}, frames['source'], frames['observed_at'], token)
        values, metadata = self.metric_store.snapshot(now)
        # Local frame measurements remain meaningful in menus without a PU join.
        if frames and not token:
            values['client_fps'] = frames['client_fps']
            metadata['client_fps'] = {'source': frames['source'], 'observed_at': frames['observed_at'],
                                    'age_seconds': max(0, now-frames['observed_at']), 'status': 'observed'}
        shard_id = reader.shard_id if token else "--"
        full_id = reader.full_shard_id if token else ""
        name = self.shard_tracker.get_known_name(reader.region_raw, shard_id, full_id) if token else None
        # Record this join before resolving a label supplied later by queue OCR.
        hop, seen = self.shard_tracker.observe_shard(reader.region_raw, shard_id, full_shard_id=full_id, join_token=token)
        name = self.shard_tracker.get_known_name(reader.region_raw, shard_id, full_id) if token else None
        server_name = self._server_identity[0] if self._server_identity and now - self._server_identity[1] <= 5 else "--"
        health = self.health_evaluator.evaluate(
            sfps=values["server_fps"], ping_ms=values["ping_ms"], restarts=values["restarts"],
            bwin=values["bwin_kbps"], loss_pct=values["loss_pct"], is_in_server=bool(token),
            connection_status=reader.connection_status,
        )
        self.state = {**values, "metric_meta": metadata, "session_token": token, "full_shard_id": full_id,
                      "shard_id": shard_id, "region_raw": reader.region_raw,
                      "region_display": translate_region(reader.region_raw) if token else "--",
                      "callsign": name or (f"SHARD {shard_id}" if token else "MAIN MENU"),
                      "server_name": server_name, "srv_id": server_name.removeprefix("GAME-") if server_name != "--" else "--",
                      "location_display": reader.location_hint or "--", "location_observed_at": reader.location_observed_at,
                      "medical_imprint": self.medical_imprint, "hop_status": hop, "region_shards_seen": seen,
                      "is_loading_screen": reader.is_loading_screen, "connection_status": reader.connection_status,
                      "health": health, "cooldowns": self.shard_tracker.active_cooldowns(full_id) if token else []}
        self.state["storage_warning"] = self.shard_tracker.read_only or bool(self.server_logger and self.server_logger.read_only)
        if self.server_logger and token:
            self.server_logger.record_telemetry_sample(values["server_fps"], values["ping_ms"], values["restarts"], metadata=metadata)
        if health["should_voice"] and self.on_health_alert_cb:
            self.on_health_alert_cb(health["voice_msg"])
        if redraw:
            self._sync_visibility()
            self.render_bar()

    def set_medical_imprint(self, loc_name):
        if loc_name.strip():
            self.medical_imprint = loc_name.strip().upper()
            cfg = load_config()
            cfg["medical_imprint"] = self.medical_imprint
            save_config(cfg)
            self.state["medical_imprint"] = self.medical_imprint
            self.render_bar()

    def set_custom_shard_name(self, shard_id, region_code, new_name, source="manual", full_shard_id=None):
        full_id = full_shard_id or self.state.get("full_shard_id")
        if not full_id or full_id not in self.shard_tracker.shards:
            return False
        entry = self.shard_tracker.shards[full_id]
        if entry.get("region_raw") != region_code.lower() or str(entry.get("shard_id")).lstrip("0") != str(shard_id).lstrip("0"):
            return False
        self.shard_tracker.set_shard_name(region_code, shard_id, new_name, full_id, source)
        if self.server_logger:
            self.server_logger.set_shard_name(shard_id, region_code, new_name, full_shard_id=full_id)
        if full_id == self.state.get("full_shard_id"):
            self.state["callsign"] = new_name.strip().upper()
        self.render_bar()
        return True

    def render_bar(self):
        if getattr(self,'layout','ribbon')=='panel':
            rows = self.presentation_rows()
            self._place_bar()
            key = (self._render_scale,tuple((r['role'],r['text']) for r in rows))
            if key != self._last_rendered_key:
                paint_panel(self.bar_canvas,rows,self._render_scale)
                self._last_rendered_key = key
            return
        render_original_bar(self)
        if self.compact and self.bar_win:
            previous = self.bar_width
            self._place_bar()
            if self.bar_width != previous:
                render_original_bar(self)

    def set_compact(self, enabled):
        self.compact = bool(enabled)
        self.BAR_HEIGHT = 24 if self.compact else 28
        self._content_width = None
        self._last_rendered_key = None
        self.bar_canvas.configure(height=self.BAR_HEIGHT)
        self._place_bar()
        self.render_bar()

    def presentation_rows(self, session=None):
        return panel_rows(self.state,self.mining,session=self.enabled if session is None else session,
                          mining_enabled=self.mining_enabled,now=time.time(),editing=self.editing,rock=getattr(self,'rock',None))

    def update_rock(self, result, observed_at):
        panel=result.get('panel') or {}
        if panel.get('settled') and panel.get('stats'):
            self.rock=dict(panel=panel,advice=result.get('advice'),observed_at=observed_at,session_token=self.state.get('session_token'))
            self._sync_visibility()
            self.render_bar()

    def _canvas_resized(self,event):
        self._last_rendered_key = None
        if self._redraw_job:
            self.bar_canvas.after_cancel(self._redraw_job)
        def redraw():
            self._redraw_job = None
            self.render_bar()
        self._redraw_job = self.bar_canvas.after_idle(redraw)

    def update_mining(self, match, signature, *, manual=False, observed_at=None):
        self.mining = dict(match=dict(match),signature=int(signature),observed_at=time.time() if observed_at is None else observed_at,
                           session_token=self.state.get('session_token'),manual=manual)
        self._sync_visibility()
        self.render_bar()

    def set_mining_enabled(self, enabled):
        self.mining_enabled = bool(enabled)
        self._sync_visibility()
        self.render_bar()

    def _save_preferences(self, changes):
        self.cfg.update(changes)
        if self.on_preferences_changed:
            self.on_preferences_changed(changes)
        else:
            current = load_config()
            current.update(changes)
            save_config(current)

    def set_layout(self, layout):
        self.layout = 'ribbon' if layout=='ribbon' else 'panel'
        self._last_rendered_key = None
        self._content_width = None
        self._sync_visibility()
        self.render_bar()
        self._save_preferences(dict(hud_layout=self.layout))

    def set_scale(self, value):
        self.scale = bounded(value,1,.75,1.75)
        self._last_rendered_key = None
        self.render_bar()
        self._save_preferences(dict(hud_scale=self.scale))

    def set_opacity(self, value):
        self.opacity = bounded(value,.7,.25,1)
        self.bar_win.wm_attributes('-alpha',self.opacity)
        self._save_preferences(dict(top_hud_opacity=self.opacity))

    def set_anchor(self, x, y):
        self.position = dict(x=bounded(x,.5,0,1),y=bounded(y,0,0,1))
        self._place_bar()
        self._save_preferences(dict(hud_position=dict(self.position)))

    def _apply_input_mode(self):
        user = ctypes.windll.user32
        from ctypes import wintypes
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.GetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int]
        user.GetWindowLongW.restype = ctypes.c_long
        user.SetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int,ctypes.c_long]
        user.SetWindowDisplayAffinity.argtypes = [wintypes.HWND,wintypes.DWORD]
        hwnd = user.GetParent(self.bar_win.winfo_id()) or self.bar_win.winfo_id()
        style = user.GetWindowLongW(hwnd,-20) | 0x80000 | 0x80 | 0x08000000
        style = style & ~0x20 if self.editing else style | 0x20
        user.SetWindowLongW(hwnd,-20,style)
        user.SetWindowDisplayAffinity(hwnd,0x11)

    def set_editing(self, enabled):
        self.editing = bool(enabled)
        if not self.editing:
            if self._drag_origin:
                self._save_preferences(dict(hud_position=dict(self.position)))
            self._drag_origin = None
        self._apply_input_mode()
        self.bar_canvas.configure(cursor='fleur' if self.editing else '')
        self._last_rendered_key = None
        self._sync_visibility()
        self.render_bar()

    def _drag_start(self, event):
        if self.editing:
            self._drag_origin = (event.x_root,event.y_root,self.bar_win.winfo_x(),self.bar_win.winfo_y())

    def _drag_move(self, event):
        if self.editing and self._drag_origin:
            ex,ey,x,y = self._drag_origin
            bounds = game_window_rect() or get_monitor_by_id(self.game_monitor)
            self.position = position_from_point(bounds,self.bar_width,self.BAR_HEIGHT,x+event.x_root-ex,y+event.y_root-ey)
            self._place_bar()

    def _drag_end(self, event):
        if self.editing and self._drag_origin:
            self._drag_move(event)
            self._drag_origin = None
            self._save_preferences(dict(hud_position=dict(self.position)))

    def close(self):
        if getattr(self,'_redraw_job',None):
            self.bar_canvas.after_cancel(self._redraw_job)
            self._redraw_job = None
        self.shard_tracker.leave_current()
        if self.server_logger:
            # Closing this companion does not imply that the game disconnected.
            self.server_logger.flush()
