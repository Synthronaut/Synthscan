"""Short passive HUD notices; flip-down shutter notification for friend/org shard arrivals."""
import math
import time

SHUTTER_WIDTH = 480
SHUTTER_HEIGHT = 42
OPEN_DURATION = 0.20
CLOSE_DURATION = 0.16
DISPLAY_DURATION = 10.0


class NoticeGate:
    def __init__(self, started_at):
        self.started_at = started_at
        self.seen = set()

    def consume(self, snapshot, owner, session_token, enabled, now):
        if snapshot.get('owner_pid') != owner or not 0 <= now - snapshot.get('written_at', 0) < 60:
            return []
        result = []
        for event in snapshot.get('events', []):
            identifier = event.get('id')
            at = event.get('at', 0)
            if not identifier or identifier in self.seen:
                continue
            self.seen.add(identifier)
            if not enabled or not isinstance(at, (float, int)) or not math.isfinite(at) or at < self.started_at or not 0 <= now - at < 60:
                continue
            if event.get('kind') == 'player_join' and (not session_token or event.get('session_token') != session_token):
                continue
            if event.get('kind') in ('player_join', 'buyer_match'):
                result.append(event)
        if len(self.seen) > 2000:
            self.seen = {e.get('id') for e in snapshot.get('events', []) if e.get('id')}
        return result


def _event_category(event):
    cat = str(event.get('category', '')).lower()
    if cat in ('friend', 'org', 'enemy_org', 'tagged'):
        return cat
    title = str(event.get('title', '')).lower()
    detail = str(event.get('detail', '')).lower()
    if 'enemy org' in title or 'enemy org' in detail:
        return 'enemy_org'
    if 'friend joined' in title or 'friend on shard' in detail or 'friend' in title:
        return 'friend'
    if 'org member' in title or 'org' in title:
        return 'org'
    return 'tagged'


class CompanionToast:
    def __init__(self, root, bounds):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes as w

        self.root = root
        self.bounds = bounds
        self.until = 0.0
        self.events = []
        self.shown = 0

        # Animation state: 'closed', 'opening', 'open', 'closing'
        self.anim_state = 'closed'
        self.anim_start = 0.0
        self.current_height = 0
        self.anim_timer = None

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.title('SynthScan HUD Shutter')
        self.win.overrideredirect(True)
        self.win.wm_attributes('-topmost', True)
        self.win.wm_attributes('-alpha', 0.96)

        self.canvas = tk.Canvas(
            self.win,
            width=SHUTTER_WIDTH,
            height=SHUTTER_HEIGHT,
            bg='#090d14',
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)

        self.win.update_idletasks()
        api = ctypes.windll.user32
        api.GetParent.argtypes = [w.HWND]
        api.GetParent.restype = w.HWND
        self.hwnd = api.GetParent(self.win.winfo_id()) or self.win.winfo_id()

        api.SetWindowLongW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_long]
        api.GetWindowLongW.argtypes = [w.HWND, ctypes.c_int]
        api.GetWindowLongW.restype = ctypes.c_long
        # WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
        api.SetWindowLongW(self.hwnd, -20, api.GetWindowLongW(self.hwnd, -20) | 0x80000 | 0x80 | 0x08000000 | 0x20)

        api.SetWindowDisplayAffinity.argtypes = [w.HWND, w.DWORD]
        api.SetWindowDisplayAffinity(self.hwnd, 0x11)

    def _render_shutter(self, height):
        if not self.events or height <= 0:
            return
        event = self.events[0]
        cat = _event_category(event)

        styles = {
            'friend': {
                'accent': '#2DE17A',
                'bg': '#0a1410',
                'border': '#1d482d',
                'pill_bg': '#0f2f1c',
                'pill_fg': '#2DE17A',
                'label': 'FRIEND'
            },
            'org': {
                'accent': '#FF9128',
                'bg': '#151009',
                'border': '#4d2b0e',
                'pill_bg': '#361c07',
                'pill_fg': '#FF9128',
                'label': 'ORG'
            },
            'enemy_org': {
                'accent': '#FF4444',
                'bg': '#16090c',
                'border': '#4d1217',
                'pill_bg': '#380c12',
                'pill_fg': '#FF4444',
                'label': 'ENEMY ORG'
            },
            'tagged': {
                'accent': '#62ccff',
                'bg': '#0a1018',
                'border': '#153247',
                'pill_bg': '#0d2538',
                'pill_fg': '#62ccff',
                'label': 'TAGGED'
            }
        }
        st = styles.get(cat, styles['tagged'])
        canvas = self.canvas
        canvas.delete('all')

        # Shutter background
        canvas.create_rectangle(0, 0, SHUTTER_WIDTH, height, fill=st['bg'], outline=st['border'], width=1)

        # Decorative shutter slat effect when opening
        if height > 8:
            slat_step = 10
            for y_line in range(slat_step, height - 4, slat_step):
                canvas.create_line(2, y_line, SHUTTER_WIDTH - 2, y_line, fill='#111822', width=1)

        # Glowing accent bottom bar
        if height >= 4:
            canvas.create_line(0, height - 2, SHUTTER_WIDTH, height - 2, fill=st['accent'], width=2)
            canvas.create_line(0, height - 1, SHUTTER_WIDTH, height - 1, fill=st['accent'], width=1)

        # Only draw text and pill if height is sufficient (> 22px)
        if height >= 24:
            # Pill badge on left
            pill_label = st['label']
            pill_w = 78 if cat == 'enemy_org' else 56 if cat == 'friend' else 44
            pill_x1, pill_y1 = 14, (height - 22) // 2
            pill_x2, pill_y2 = pill_x1 + pill_w, pill_y1 + 22
            canvas.create_rectangle(pill_x1, pill_y1, pill_x2, pill_y2, fill=st['pill_bg'], outline=st['accent'], width=1)
            canvas.create_text((pill_x1 + pill_x2) // 2, (pill_y1 + pill_y2) // 2, text=pill_label, fill=st['pill_fg'], font=('Segoe UI', -10, 'bold'))

            # Main text
            title = event.get('title', '')
            if len(self.events) > 1:
                title += f'  (+{len(self.events)-1} more)'
            text_x = pill_x2 + 14
            canvas.create_text(text_x, height // 2, anchor='w', text=title[:60], fill='#f8fafc', font=('Segoe UI', -12, 'bold'))

    def _apply_geometry(self, height, anchor_geometry=None):
        rect = self.bounds() if callable(self.bounds) else None
        if not rect and anchor_geometry and len(anchor_geometry) >= 4:
            rect = {'left': anchor_geometry[0], 'top': anchor_geometry[1], 'width': anchor_geometry[2], 'height': anchor_geometry[3]}
        if not rect:
            return False

        width = min(SHUTTER_WIDTH, max(260, rect.get('width', 1920) - 48))
        if anchor_geometry and len(anchor_geometry) >= 4 and anchor_geometry[2] > 0:
            left = anchor_geometry[0] + (anchor_geometry[2] - width) // 2
            top = anchor_geometry[1] + anchor_geometry[3] + 1
        else:
            left = rect['left'] + (rect.get('width', 1920) - width) // 2
            top = rect['top'] + 36

        self.win.geometry(f'{width}x{height}')
        import ctypes
        from ctypes import wintypes as w
        api = ctypes.windll.user32
        api.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
        api.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), int(left), int(top), int(width), int(height), 0x10 | 0x40)
        return True

    def _anim_step(self, anchor_geometry=None):
        now = time.time()
        if self.anim_state == 'opening':
            dt = now - self.anim_start
            p = min(1.0, dt / OPEN_DURATION) if OPEN_DURATION > 0 else 1.0
            ease = 1.0 - (1.0 - p) ** 3
            self.current_height = max(4, int(SHUTTER_HEIGHT * ease))
            self._render_shutter(self.current_height)
            self._apply_geometry(self.current_height, anchor_geometry)
            if p >= 1.0:
                self.anim_state = 'open'
                self.current_height = SHUTTER_HEIGHT
            else:
                self.anim_timer = self.root.after(16, lambda: self._anim_step(anchor_geometry))
        elif self.anim_state == 'closing':
            dt = now - self.anim_start
            p = min(1.0, dt / CLOSE_DURATION) if CLOSE_DURATION > 0 else 1.0
            ease = p * p
            self.current_height = max(0, int(SHUTTER_HEIGHT * (1.0 - ease)))
            if self.current_height <= 4 or p >= 1.0:
                self.anim_state = 'closed'
                self.win.withdraw()
            else:
                self._render_shutter(self.current_height)
                self._apply_geometry(self.current_height, anchor_geometry)
                self.anim_timer = self.root.after(16, lambda: self._anim_step(anchor_geometry))

    def update(self, events, enabled, now=None, session_token=None, anchor_geometry=None):
        now = time.time() if now is None else now
        if events:
            self.events = events
            self.until = now + DISPLAY_DURATION
            self.shown += 1
            if self.anim_state in ('closed', 'closing'):
                self.anim_state = 'opening'
                self.anim_start = now
                self.current_height = 4
                self.win.deiconify()
                self._render_shutter(self.current_height)
                self._apply_geometry(self.current_height, anchor_geometry)
                self._anim_step(anchor_geometry)
            elif self.anim_state == 'open':
                self._render_shutter(SHUTTER_HEIGHT)
                self._apply_geometry(SHUTTER_HEIGHT, anchor_geometry)

        # Check dismissal conditions
        dismiss = (
            not enabled
            or now >= self.until
            or any(e.get('kind') == 'player_join' and e.get('session_token') != session_token for e in self.events)
        )
        if dismiss:
            if self.anim_state in ('open', 'opening'):
                self.anim_state = 'closing'
                self.anim_start = now
                self._anim_step(anchor_geometry)
            elif self.anim_state == 'closed':
                self.win.withdraw()
            return

        if self.anim_state == 'open':
            self._apply_geometry(SHUTTER_HEIGHT, anchor_geometry)
