"""A quiet, non-activating notification; never restarts or controls the game."""
import time
from setup_status import reputation_view,read

class NoticeGate:
    def __init__(self):self.seen=set()
    def consume(self,view,pids):
        key=tuple(sorted(pids))
        if view.get('state')!='restart' or not key or key in self.seen:return False
        self.seen.add(key);return True

class ReputationNotice:
    def __init__(self,root,directory,bounds):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes as w
        self.directory=directory;self.bounds=bounds;self.gate=NoticeGate();self.until=0
        self.win=tk.Toplevel(root);self.win.withdraw();self.win.overrideredirect(True);self.win.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.win,width=500,height=108,bg='#13232b',highlightthickness=1,highlightbackground='#69cbbd');self.canvas.pack()
        self.canvas.create_text(18,24,anchor='w',text='Your reputation numbers are ready',fill='#b6f3e7',font=('Segoe UI',12,'bold'))
        self.canvas.create_text(18,61,anchor='w',text='Fully restart Star Citizen when convenient.\nMore → Setup & reputation shows your sync status.',fill='#e5edf3',font=('Segoe UI',10))
        self.win.update_idletasks();user=ctypes.windll.user32
        user.GetParent.argtypes=[w.HWND];user.GetParent.restype=w.HWND
        user.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];user.GetWindowLongW.restype=ctypes.c_long
        user.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
        user.SetLayeredWindowAttributes.argtypes=[w.HWND,w.DWORD,ctypes.c_byte,w.DWORD]
        user.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD]
        user.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
        self.hwnd=user.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        user.SetWindowLongW(self.hwnd,-20,user.GetWindowLongW(self.hwnd,-20)|0x80|0x08000000|0x20|0x80000)
        user.SetLayeredWindowAttributes(self.hwnd,0,250,2)
        user.SetWindowDisplayAffinity(self.hwnd,0x11)
    def poll(self):
        import ctypes
        now=time.time();view=reputation_view(self.directory,now)
        session=read(self.directory/'session_state.json',limit=8*1024*1024)
        if self.gate.consume(view,session.get('game_pids',[])):self.until=now+18
        rect=self.bounds()
        if now>=self.until or not rect:self.win.withdraw();return
        ctypes.windll.user32.SetWindowPos(self.hwnd,-1,int(rect['left']+rect['width']-520),int(rect['top']+rect['height']-145),500,108,0x10|0x40)
