"""Short passive HUD notices; retained history lives in the desktop app."""
import math
import time


class NoticeGate:
    def __init__(self,started_at):self.started_at=started_at;self.seen=set()
    def consume(self,snapshot,owner,session_token,enabled,now):
        if snapshot.get('owner_pid')!=owner or not 0<=now-snapshot.get('written_at',0)<10:return []
        result=[]
        for event in snapshot.get('events',[]):
            identifier=event.get('id');at=event.get('at',0)
            if not identifier or identifier in self.seen:continue
            self.seen.add(identifier)
            if not enabled or not isinstance(at,(float,int)) or not math.isfinite(at) or at<self.started_at or not 0<=now-at<10:continue
            if event.get('kind')=='player_join' and (not session_token or event.get('session_token')!=session_token):continue
            if event.get('kind') in ('player_join','buyer_match'):result.append(event)
        if len(self.seen)>2000:self.seen={e.get('id') for e in snapshot.get('events',[]) if e.get('id')}
        return result


class CompanionToast:
    def __init__(self,root,bounds):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes as w
        self.bounds=bounds;self.until=0;self.events=[];self.shown=0
        self.win=tk.Toplevel(root);self.win.withdraw();self.win.title('SynthScan notifications');self.win.overrideredirect(True)
        self.win.wm_attributes('-topmost',True);self.win.wm_attributes('-alpha',.95)
        self.canvas=tk.Canvas(self.win,width=500,height=92,bg='#10151e',highlightthickness=0);self.canvas.pack()
        self.win.update_idletasks();api=ctypes.windll.user32
        api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        self.hwnd=api.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long];api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.GetWindowLongW.restype=ctypes.c_long
        api.SetWindowLongW(self.hwnd,-20,api.GetWindowLongW(self.hwnd,-20)|0x80000|0x80|0x08000000|0x20)
        api.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD];api.SetWindowDisplayAffinity(self.hwnd,0x11)
    def update(self,events,enabled,now=None,session_token=None):
        now=time.time() if now is None else now
        if events:
            self.events=events;self.until=now+6;self.shown+=1
            canvas=self.canvas;canvas.delete('all');canvas.create_rectangle(1,1,499,91,fill='#10151e',outline='#62ccff',width=2)
            title=events[0]['title']+('  +'+str(len(events)-1)+' more' if len(events)>1 else '')
            canvas.create_text(16,23,anchor='w',text=title[:57],fill='#9ce2ff',font=('Segoe UI',-17,'bold'))
            canvas.create_text(16,58,anchor='w',text=events[0]['detail'][:145],width=468,fill='#f1f5f9',font=('Segoe UI',-13))
        if not enabled or now>=self.until or any(e.get('kind')=='player_join' and e.get('session_token')!=session_token for e in self.events):self.win.withdraw();return
        rect=self.bounds()
        if not rect:self.win.withdraw();return
        import ctypes
        from ctypes import wintypes as w
        width=min(500,max(200,rect['width']-48));left=rect['left']+24;top=rect['top']+rect['height']-130
        self.win.geometry(f'{width}x92');self.win.deiconify()
        api=ctypes.windll.user32;api.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
        api.SetWindowPos(self.hwnd,ctypes.c_void_p(-1),left,top,width,92,0x10|0x40)
