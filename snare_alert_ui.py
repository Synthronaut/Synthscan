"""Small click-through alert, independent of the game's map and input."""
from datetime import datetime
from pathlib import Path
import time

WIDTH,HEIGHT=640,108

def paint_alert(canvas,events):
    canvas.delete('all');canvas.create_rectangle(1,1,WIDTH-1,HEIGHT-1,fill='#10151e',outline='#f5ad42',width=2)
    canvas.create_rectangle(1,1,8,HEIGHT-1,fill='#f5ad42',outline='#f5ad42')
    canvas.create_text(24,27,anchor='w',text='INTERDICTION REPORTED',fill='#ffc66d',font=('Bahnschrift',-23,'bold'))
    names=', '.join(e['target'] for e in events[:2])
    if len(events)>2:names+=' +'+str(len(events)-2)+' more'
    if len(names)>58:names=names[:55]+'…'
    canvas.create_text(24,59,anchor='w',text=names,fill='#f1f5f9',font=('Consolas',-17,'bold'))
    from session_timeline import DISPLAY_ZONE
    stamp=datetime.fromtimestamp(events[-1]['at'],DISPLAY_ZONE).strftime('%H:%M:%S %z')
    canvas.create_text(24,87,anchor='w',text=f'Game log · {stamp} · {len(events)} new report(s)',fill='#aab8cc',font=('Consolas',-12,'normal'))

class SnareAlertWindow:
    def __init__(self,root,bounds):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes as w
        self.bounds=bounds;self.until=0;self.token=None;self.events=[];self.shown=0
        self.win=tk.Toplevel(root);self.win.withdraw();self.win.title('SynthScan Snare Watch');self.win.overrideredirect(True)
        self.win.wm_attributes('-topmost',True);self.win.wm_attributes('-alpha',.96)
        self.canvas=tk.Canvas(self.win,width=WIDTH,height=HEIGHT,bg='#10151e',highlightthickness=0,bd=0);self.canvas.pack()
        self.win.update_idletasks();user=ctypes.windll.user32
        user.GetParent.argtypes=[w.HWND];user.GetParent.restype=w.HWND
        user.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];user.GetWindowLongW.restype=ctypes.c_long
        user.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long];user.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD]
        self.hwnd=user.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        user.SetWindowLongW(self.hwnd,-20,user.GetWindowLongW(self.hwnd,-20)|0x80000|0x80|0x08000000|0x20)
        user.SetWindowDisplayAffinity(self.hwnd,0x11)
    def update(self,events,token,enabled,now=None):
        now=time.time() if now is None else now
        if events:
            self.events=events;self.token=token;self.until=now+7;self.shown+=1;paint_alert(self.canvas,events)
            import winsound
            sound=Path(__file__).resolve().parent/'assets/snare_watch.wav'
            try:winsound.PlaySound(str(sound),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            except RuntimeError:pass
        if not enabled or token!=self.token or now>=self.until:self.win.withdraw();return
        rect=self.bounds()
        if not rect:self.win.withdraw();return
        import ctypes
        from ctypes import wintypes as w
        width=min(WIDTH,rect['width']-24);left=rect['left']+(rect['width']-width)//2;top=rect['top']+48
        self.win.geometry(f'{width}x{HEIGHT}');self.win.deiconify()
        user=ctypes.windll.user32;user.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
        user.SetWindowPos(self.hwnd,ctypes.c_void_p(-1),left,top,width,HEIGHT,0x10|0x40)
