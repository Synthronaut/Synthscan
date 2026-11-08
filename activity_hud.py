"""Small non-activating collapse controls; the HUD body remains click-through."""
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

def afk_request(status,owner,now,request_id=None):
    if not fresh_activity_status(status,owner,now):raise ValueError('Activity HUD is not ready')
    return dict(id=request_id or uuid.uuid4().hex,action='set_afk_armed',at=now,owner_pid=owner,
                armed=not bool((status.get('afk_jiggler') or {}).get('armed',False)))

def button_position(bar,bounds,width=BUTTON_WIDTH):
    x,y,w,h=bar;right=bounds['left']+bounds['width'];bottom=bounds['top']+bounds['height']
    left=x+w+3
    if left+width>right:left=x-width-3
    left=max(bounds['left'],min(left,right-width))
    top=max(bounds['top'],min(y,bottom-h))
    return int(left),int(top),int(width),int(h)

def collapse_position(rect,bounds,width=24,height=24):
    left,top,right,bottom=(int(rect[k]) for k in ('left','top','right','bottom'))
    x=left-width-2
    if x<bounds['left']:x=right+2
    x=max(bounds['left'],min(x,bounds['left']+bounds['width']-width))
    y=max(bounds['top'],min(top,bounds['top']+bounds['height']-height))
    return x,y,width,height


def control_hit(event,width,height):
    return event is not None and 0<=event.x<width and 0<=event.y<height


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
    WIDTH=BUTTON_WIDTH
    collapse_only=False
    def __init__(self,root,directory,owner):
        import tkinter as tk
        self.directory=directory;self.owner=owner;self.status={};self.pending=None;self.visible=False;self.geometry=None;self.height=24
        self.window=tk.Toplevel(root);self.window.withdraw();self.window.overrideredirect(True)
        self.window.title('Expand activity HUD');self.window.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.window,width=self.WIDTH,height=24,bg='#070a0f',highlightthickness=0,bd=0,cursor='hand2')
        self.canvas.pack(fill='both',expand=True);self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.window.update_idletasks();self._native_input()
    def _native_input(self):
        import ctypes
        from ctypes import wintypes as w
        api=ctypes.windll.user32;api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
        self.hwnd=api.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        # Only this small control accepts clicks; it never activates the app.
        style=(api.GetWindowLongW(self.hwnd,-20)|0x80000|0x80|0x08000000)&~0x20
        api.SetWindowLongW(self.hwnd,-20,style);api.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD];api.SetWindowDisplayAffinity(self.hwnd,0x11)
        # Explicitly retain the game's focus on the first click as well.
        proc_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
        api.GetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int];api.GetWindowLongPtrW.restype=ctypes.c_ssize_t
        api.SetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_ssize_t];api.SetWindowLongPtrW.restype=ctypes.c_ssize_t
        api.CallWindowProcW.argtypes=[ctypes.c_void_p,w.HWND,w.UINT,w.WPARAM,w.LPARAM];api.CallWindowProcW.restype=ctypes.c_ssize_t
        original=api.GetWindowLongPtrW(self.hwnd,-4)
        @proc_type
        def mouse_proc(handle,message,wp,lp):
            if message==0x21:return 3  # MA_NOACTIVATE, allow only this button's click
            return api.CallWindowProcW(original,handle,message,wp,lp)
        self._mouse_proc=mouse_proc
        api.SetWindowLongPtrW(self.hwnd,-4,ctypes.cast(mouse_proc,ctypes.c_void_p).value)
    def press(self,event):
        self.pressed=bool(control_hit(event,self.WIDTH,self.height) and fresh_activity_status(self.status,self.owner,time.time()))
    def release(self,event):
        pressed=getattr(self,'pressed',False);self.pressed=False
        if pressed:self.click(event)
    def click(self,event=None):
        if not control_hit(event,self.WIDTH,self.height) or self.pending:return
        try:
            request=toggle_request(self.status,self.owner,time.time())
            if self.collapse_only:request['expanded']=False
            if publish_json(self.directory/'activity_hud_command.json',request):
                self.pending=request;notify_native(self.status,self.owner)
        except (OSError,ValueError):return
        self.paint()
    def paint(self):
        ready=fresh_activity_status(self.status,self.owner,time.time())
        expanded=bool(self.status.get('activity_expanded',True));label='−' if self.collapse_only else 'HUD '+('−' if expanded else '+')
        if self.pending:label='·' if self.collapse_only else 'HUD ·'
        key=(label,ready,self.height)
        if getattr(self,'paint_key',None)==key:return
        self.paint_key=key;self.canvas.delete('all')
        self.canvas.create_rectangle(0,0,self.WIDTH-1,self.height-1,fill='#101722',outline='#334155')
        self.canvas.create_text(self.WIDTH//2,self.height//2,text=label,fill='#cbd5e1' if ready else '#64748b',font=('Consolas',9,'bold'))
        self.window.title('Collapse mining HUD' if self.collapse_only else ('Collapse activity HUD' if expanded else 'Expand activity HUD'))
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


class ActivityCollapseButton(ActivityButton):
    """A small minus docked to the activity panel, outside its click-through body."""
    WIDTH=24
    collapse_only=True
    def follow(self,ribbon,bounds):
        import ctypes
        from ctypes import wintypes as w
        status=self.status
        visible=bool(fresh_activity_status(status,self.owner,time.time()) and status.get('hud_visible') and
                     status.get('activity_expanded') and status.get('overlay_mode') and getattr(ribbon,'_visible',False))
        rect=status.get('hud_position') or {}
        if visible and all(k in rect for k in ('left','top','right','bottom')):
            self.height=24;geometry=collapse_position(rect,bounds,self.WIDTH,self.height);showing=not self.visible
            if showing:self.window.deiconify()
            if geometry!=self.geometry or showing:
                x,y,width,height=geometry;self.window.geometry(f'{width}x{height}')
                api=ctypes.windll.user32
                api.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
                api.SetWindowPos(self.hwnd,w.HWND(-1),x,y,width,height,0x10|0x40);self.geometry=geometry
            if getattr(self,'opacity',None)!=ribbon.opacity:
                self.window.attributes('-alpha',ribbon.opacity);self.opacity=ribbon.opacity
        else:
            visible=False
            if self.visible:self.window.withdraw()
        self.visible=visible


class ActivityQuickControls(ActivityCollapseButton):
    """One non-activating strip: collapse, then a direct AFK toggle beside it."""
    WIDTH=78
    AFK_LEFT=27
    def press(self,event):
        super().press(event)
        self.pressed_action=('collapse' if event.x<24 else 'afk' if event.x>=self.AFK_LEFT else None) if self.pressed else None
    def release(self,event):
        pressed=getattr(self,'pressed',False);self.pressed=False
        action=getattr(self,'pressed_action',None);self.pressed_action=None
        if not pressed or not control_hit(event,self.WIDTH,self.height) or self.pending:return
        released='collapse' if event.x<24 else 'afk' if event.x>=self.AFK_LEFT else None
        if not action or action!=released:return
        try:
            now=time.time()
            request=afk_request(self.status,self.owner,now) if action=='afk' else toggle_request(self.status,self.owner,now)
            if action=='collapse':request['expanded']=False
            if publish_json(self.directory/'activity_hud_command.json',request):
                self.pending=request;notify_native(self.status,self.owner)
        except (OSError,ValueError):return
        self.paint()
    def paint(self):
        ready=fresh_activity_status(self.status,self.owner,time.time())
        afk=self.status.get('afk_jiggler') or {};armed=bool(afk.get('armed',False))
        error=str(afk.get('status','')).startswith('error')
        pending=self.pending.get('action') if self.pending else None
        last=float(afk.get('last_pulse_at') or 0)
        sent_recently=bool(armed and 0<=time.time()-last<2)
        seconds=int(afk.get('next_in_seconds',-1))
        indicator='●' if armed else '○'
        if armed and ready:
            if afk.get('pulse_active'):indicator='↔'
            elif sent_recently:indicator='✓'
            elif 0<seconds<=10:indicator=str(seconds)
        label='AFK '+('·' if pending=='set_afk_armed' else '!' if error else indicator)
        key=(ready,armed,error,pending,label,self.height)
        if getattr(self,'paint_key',None)==key:return
        self.paint_key=key;self.canvas.delete('all')
        self.canvas.configure(width=self.WIDTH)
        self.canvas.create_rectangle(0,0,23,self.height-1,fill='#101722',outline='#334155')
        self.canvas.create_text(12,self.height//2,text='·' if pending=='set_activity_expanded' else '−',fill='#cbd5e1' if ready else '#64748b',font=('Consolas',9,'bold'))
        self.canvas.create_rectangle(self.AFK_LEFT,0,self.WIDTH-1,self.height-1,fill='#12251f' if armed else '#101722',outline='#397d66' if armed else '#334155')
        self.canvas.create_text((self.AFK_LEFT+self.WIDTH)//2,self.height//2,text=label,fill='#f0b35b' if error else '#8ee2bd' if armed and ready else '#cbd5e1' if ready else '#64748b',font=('Consolas',9,'bold'))
        detail=f"on — {afk.get('status','waiting')} — {int(afk.get('nudges',0))} pulses sent; click to turn off" if armed else 'off — click to turn on'
        self.window.title('Collapse HUD / AFK mouse jiggler: '+detail)
