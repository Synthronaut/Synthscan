"""Activity HUD commands and a small, always-clickable server-ribbon end button."""
import time,uuid,re
from telemetry_ipc import publish_json

BUTTON_WIDTH=52

def fresh_activity_status(status,owner,now):
    try:return status.get('pid')==owner and 0<=now-float(status.get('at',0))<3
    except (TypeError,ValueError):return False

def toggle_request(status,owner,now,request_id=None):
    if not fresh_activity_status(status,owner,now):raise ValueError('Activity HUD is not ready')
    return dict(id=request_id or uuid.uuid4().hex,action='set_activity_expanded',at=now,owner_pid=owner,
                expanded=not bool(status.get('activity_expanded',True)))

def button_position(bar,bounds,width=BUTTON_WIDTH):
    x,y,w,h=bar;right=bounds['left']+bounds['width'];bottom=bounds['top']+bounds['height']
    left=x+w+3
    if left+width>right:left=x-width-3
    left=max(bounds['left'],min(left,right-width))
    top=max(bounds['top'],min(y,bottom-h))
    return int(left),int(top),int(width),int(h)

def notify_native(status,owner,api=None):
    """Wake only our native control window; the command file remains authoritative."""
    if not fresh_activity_status(status,owner,time.time()):return False
    import ctypes
    from ctypes import wintypes as w
    api=ctypes.windll.user32 if api is None else api
    api.FindWindowW.argtypes=[w.LPCWSTR,w.LPCWSTR];api.FindWindowW.restype=w.HWND
    api.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    api.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    hwnd=api.FindWindowW('SynthScanHost','SynthScan services')
    if not hwnd:return False
    pid=w.DWORD();api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    return bool(pid.value==owner and api.PostMessageW(hwnd,0x8000+42,0,0))

class ActivityButton:
    def __init__(self,root,directory,owner):
        import tkinter as tk
        self.directory=directory;self.owner=owner;self.status={};self.pending=None;self.visible=False;self.geometry=None
        self.window=tk.Toplevel(root);self.window.withdraw();self.window.overrideredirect(True)
        self.window.title('Expand activity HUD');self.window.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.window,width=BUTTON_WIDTH,height=24,bg='#070a0f',highlightthickness=0,bd=0,cursor='hand2')
        self.canvas.pack(fill='both',expand=True);self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.window.update_idletasks();self._native_input()
    def _native_input(self):
        import ctypes
        from ctypes import wintypes as w
        api=ctypes.windll.user32;api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
        self.hwnd=api.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        # The ribbon can remain click-through when locked. This small separate
        # end button always accepts a click without activating over the game.
        style=(api.GetWindowLongW(self.hwnd,-20)|0x80000|0x80|0x08000000)&~0x20
        api.SetWindowLongW(self.hwnd,-20,style);api.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD];api.SetWindowDisplayAffinity(self.hwnd,0x11)
    def press(self,event):self.pressed=True
    def release(self,event):
        pressed=getattr(self,'pressed',False);self.pressed=False
        if pressed:self.click(event)
    def click(self,event=None):
        if self.pending:return
        if event is not None and not (0<=event.x<BUTTON_WIDTH and 0<=event.y<self.height):return
        try:
            request=toggle_request(self.status,self.owner,time.time())
            if publish_json(self.directory/'activity_hud_command.json',request):
                self.pending=request;notify_native(self.status,self.owner)
        except (OSError,ValueError):return
        self.paint()
    def paint(self):
        ready=fresh_activity_status(self.status,self.owner,time.time())
        expanded=bool(self.status.get('activity_expanded',True));label='HUD '+('−' if expanded else '+')
        if self.pending:label='HUD ·'
        key=(label,ready,self.height)
        if getattr(self,'paint_key',None)==key:return
        self.paint_key=key;self.canvas.delete('all')
        self.canvas.create_rectangle(0,0,BUTTON_WIDTH-1,self.height-1,fill='#101722',outline='#334155')
        self.canvas.create_text(BUTTON_WIDTH//2,self.height//2,text=label,fill='#cbd5e1' if ready else '#64748b',font=('Consolas',9,'bold'))
        self.window.title('Collapse activity HUD' if expanded else 'Expand activity HUD')
    def follow(self,ribbon,bounds):
        import ctypes
        from ctypes import wintypes as w
        self.height=ribbon.BAR_HEIGHT
        visible=bool(getattr(ribbon,'_visible',False))
        if visible:
            match=re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',getattr(ribbon,'_last_geometry','') or '')
            bar=(int(match[3]),int(match[4]),int(match[1]),int(match[2])) if match else (ribbon.bar_win.winfo_x(),ribbon.bar_win.winfo_y(),ribbon.bar_width,ribbon.BAR_HEIGHT)
            geometry=button_position(bar,bounds);showing=not self.visible
            if showing:self.window.deiconify()
            if geometry!=self.geometry or showing:
                x,y,width,height=geometry
                if self.geometry is None or self.geometry[2:]!=geometry[2:]:self.window.geometry(f'{width}x{height}')
                api=ctypes.windll.user32
                api.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
                api.SetWindowPos(self.hwnd,None,x,y,width,height,0x14);self.geometry=geometry
            if getattr(self,'opacity',None)!=ribbon.opacity:
                self.window.attributes('-alpha',ribbon.opacity);self.opacity=ribbon.opacity
        elif self.visible:self.window.withdraw()
        self.visible=visible
    def sync(self,ribbon,status,bounds):
        self.status=status
        if self.pending and (status.get('activity_command_id')==self.pending['id'] or time.time()-self.pending['at']>3):self.pending=None
        self.follow(ribbon,bounds);self.paint()
    def close(self):self.window.destroy()
