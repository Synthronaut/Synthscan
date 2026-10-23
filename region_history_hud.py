"""Small no-activate region dropdown, reading existing session history only."""
from datetime import datetime, timedelta, timezone
import re
import time
from telemetry_core import timestamp

TAIPEI = timezone(timedelta(hours=8))


def recent_visits(snapshot, limit=8):
    rows = []
    for session in snapshot.get('sessions', []):
        joined = timestamp(session.get('joined_at'))
        if joined is None:
            continue
        left = timestamp(session.get('left_at'))
        current = bool(snapshot.get('session_token') and session.get('active') and
                       session.get('full_shard_id') == snapshot.get('full_shard_id'))
        def date(at):
            return datetime.fromtimestamp(at, TAIPEI).strftime('%Y-%m-%d %H:%M:%S')
        rows.append(dict(joined=joined, region=session.get('region_display') or session.get('region_raw') or '--',
                         server=session.get('server_name') or ('Shard ' + str(session.get('shard_id', '--'))),
                         full=session.get('full_shard_id', ''), current=current,
                         times=f"{date(joined)} → {date(left) if left is not None else ('now' if current else 'end unrecorded')}"))
    return sorted(rows, key=lambda r: r['joined'], reverse=True)[:limit]


class RegionHistory:
    def __init__(self, root):
        import tkinter as tk
        self.root=root; self.visible=False; self.open=False; self.snapshot={}; self.geometry=None
        self.window=tk.Toplevel(root);self.window.withdraw();self.window.overrideredirect(True)
        self.window.title('SynthScan region history');self.window.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.window,bg='#070a0f',highlightthickness=0,bd=0,cursor='hand2')
        self.canvas.pack(fill='both',expand=True)
        self.popup=tk.Toplevel(root);self.popup.withdraw();self.popup.overrideredirect(True)
        self.popup.title('Recent regions and servers');self.popup.attributes('-topmost',True)
        self.content=tk.Canvas(self.popup,bg='#0b111a',highlightthickness=1,highlightbackground='#334155',bd=0)
        self.content.pack(fill='both',expand=True)
        self.window.update_idletasks();self.popup.update_idletasks()
        self.hwnd=self.native_input(self.window);self.popup_hwnd=self.native_input(self.popup)
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)

    @staticmethod
    def native_input(window):
        import ctypes
        from ctypes import wintypes as w
        api=ctypes.windll.user32;api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        hwnd=api.GetParent(window.winfo_id()) or window.winfo_id()
        api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
        api.SetWindowLongW(hwnd,-20,(api.GetWindowLongW(hwnd,-20)|0x80000|0x80|0x08000000)&~0x20)
        # WS_EX_LAYERED alone does not make a window drawable. Windows requires
        # an initial alpha/color-key setting (or UpdateLayeredWindow). The
        # button later gets Tk opacity; the popup otherwise never did.
        api.SetLayeredWindowAttributes.argtypes=[w.HWND,w.DWORD,w.BYTE,w.DWORD]
        if not api.SetLayeredWindowAttributes(hwnd,0,255,2):
            raise OSError('Could not initialize HUD window opacity')
        api.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD];api.SetWindowDisplayAffinity(hwnd,0x11)
        # Explicitly accept the first click without activating the window. Tk's
        # default mouse-activation handling must not consume that first click.
        proc_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
        api.GetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int];api.GetWindowLongPtrW.restype=ctypes.c_ssize_t
        api.SetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_ssize_t];api.SetWindowLongPtrW.restype=ctypes.c_ssize_t
        api.CallWindowProcW.argtypes=[ctypes.c_void_p,w.HWND,w.UINT,w.WPARAM,w.LPARAM];api.CallWindowProcW.restype=ctypes.c_ssize_t
        original=api.GetWindowLongPtrW(hwnd,-4)
        @proc_type
        def mouse_proc(handle,message,wp,lp):
            if message==0x21:return 3  # WM_MOUSEACTIVATE / MA_NOACTIVATE (do not eat input)
            return api.CallWindowProcW(original,handle,message,wp,lp)
        window._mouse_proc=mouse_proc
        api.SetWindowLongPtrW(hwnd,-4,ctypes.cast(mouse_proc,ctypes.c_void_p).value)
        return hwnd

    @staticmethod
    def place(hwnd, x, y, width, height):
        import ctypes
        from ctypes import wintypes as w
        api=ctypes.windll.user32
        api.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
        api.SetWindowPos(hwnd,w.HWND(-1),x,y,width,height,0x10|0x40)

    def press(self,event):
        self.origin=(event.x_root,event.y_root)
        self.last_input=dict(kind='press',x=event.x,y=event.y,at=time.time())

    def drag(self,event):
        pass  # The region control is a button, never a drag handle.

    def release(self,event):
        origin=getattr(self,'origin',None);self.origin=None
        self.last_input=dict(kind='release',x=event.x,y=event.y,at=time.time(),had_press=bool(origin),
                             width=self.canvas.winfo_width(),height=self.canvas.winfo_height())
        # Tk event coordinates and native screen coordinates can differ under
        # display scaling. Hit-test in the same widget-local space as the event.
        if origin and 0<=event.x<self.canvas.winfo_width() and 0<=event.y<self.canvas.winfo_height():
            self.toggle()

    def hide_popup(self,reason='explicit_close'):
        if self.open:self.last_transition=dict(open=False,reason=reason,at=time.time())
        self.popup.withdraw();self.open=False

    def toggle(self):
        if self.open:self.hide_popup();return
        if not self.visible:return
        rows=recent_visits(self.snapshot)
        width=510;height=(36+len(rows)*52 if rows else 72)+32
        c=self.content;c.configure(width=width,height=height);c.delete('all')
        c.create_text(12,15,anchor='w',text='RECENT REGIONS / SERVERS · TAIPEI (UTC+8)',fill='#94a3b8',font=('Consolas',9,'bold'))
        if not rows:c.create_text(12,47,anchor='w',text='No recorded visits yet.',fill='#cbd5e1',font=('Consolas',9))
        for i,row in enumerate(rows):
            y=35+i*52
            c.create_line(10,y-5,width-10,y-5,fill='#1e293b')
            c.create_text(12,y+4,anchor='w',text=('NOW · ' if row['current'] else '')+row['region']+' · '+row['server'],fill='#38bdf8' if row['current'] else '#cbd5e1',font=('Consolas',9,'bold'),width=width-24)
            c.create_text(12,y+25,anchor='w',text=row['times'],fill='#94a3b8',font=('Consolas',8))
        action='Unlock server bar to reposition' if self.ribbon.server_bar_locked else 'Lock server bar in place'
        c.create_rectangle(8,height-30,width-8,height-5,fill='#152131',outline='#334155',tags='lock')
        c.create_text(18,height-18,anchor='w',text=action,fill='#38bdf8',font=('Consolas',9,'bold'),tags='lock')
        c.tag_bind('lock','<ButtonRelease-1>',lambda event:self.toggle_lock())
        self.popup_size=(width,height)
        self.popup.geometry(f'{width}x{height}');self.popup.deiconify()
        self.popup.update_idletasks()
        self.position_popup()
        self.open=True
        self.last_transition=dict(open=True,at=time.time())
        import ctypes
        self.last_down=bool(ctypes.windll.user32.GetAsyncKeyState(1)&0x8000)
        self.root.after(80,self.dismiss_poll)

    def position_popup(self):
        width,height=self.popup_size
        x,y,w,h=self.geometry;b=self.bounds
        x=max(b['left'],min(x,b['left']+b['width']-width))
        y=y+h+4 if y+h+height+4<=b['top']+b['height'] else max(b['top'],y-height-4)
        self.place(self.popup_hwnd,x,y,width,height);self.popup_rect=(x,y,width,height)

    def toggle_lock(self):
        self.ribbon.server_bar_locked=not self.ribbon.server_bar_locked
        self.ribbon._save_preferences(dict(locked=self.ribbon.server_bar_locked))
        self.ribbon.set_editing(not self.ribbon.server_bar_locked)
        self.hide_popup()

    def dismiss_poll(self):
        if not self.open:return
        import ctypes
        from ctypes import wintypes as w
        down=bool(ctypes.windll.user32.GetAsyncKeyState(1)&0x8000)
        if down and not self.last_down:
            point=w.POINT();ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            if not any(x<=point.x<x+width and y<=point.y<y+height for x,y,width,height in (self.geometry,self.popup_rect)):
                self.hide_popup('outside_click');return
        self.last_down=down;self.root.after(80,self.dismiss_poll)

    def follow(self,ribbon,bounds):
        self.ribbon=ribbon;self.bounds=bounds
        hit=getattr(ribbon,'region_hit',None)
        visible=bool(getattr(ribbon,'_visible',False) and hit and ribbon.state.get('connection_status')!='unavailable')
        if not visible:
            self.window.withdraw();self.hide_popup('ribbon_hidden');self.visible=False;return
        match=re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',ribbon._last_geometry or '')
        if not match:return
        geometry=(int(match[3])+hit['left'],int(match[4]),hit['right']-hit['left'],ribbon.BAR_HEIGHT)
        if geometry!=self.geometry or not self.visible:
            self.geometry=geometry
            self.visible=True
            x,y,width,height=geometry
            self.window.geometry(f'{width}x{height}');self.window.deiconify()
            self.window.update_idletasks();self.place(self.hwnd,*geometry)
            if self.open:self.position_popup()
        key=(hit['label'],hit['text'],hit['color'],geometry[2:])
        if key!=getattr(self,'paint_key',None):
            self.paint_key=key;self.canvas.delete('all');cy=ribbon.BAR_HEIGHT//2
            self.canvas.create_text(0,cy,anchor='w',text=hit['label'],fill='#64748b',font=('Consolas',8,'bold'))
            self.canvas.create_text(hit['value_x'],cy,anchor='w',text=hit['text'],fill=hit['color'],font=('Consolas',8,'bold'),tags='region_value')
        if getattr(self,'opacity',None)!=ribbon.opacity:
            self.window.attributes('-alpha',ribbon.opacity);self.opacity=ribbon.opacity
        self.visible=True
