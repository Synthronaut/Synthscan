"""Shared capture policy and verified game identity. Never captures the desktop."""
from dataclasses import dataclass
from pathlib import Path
import ctypes
import json
import os
import threading
import time

_activity_at=0
_activity_lock=threading.Lock()
def record_activity():
    """Timestamp/source only, so all helpers share an honest capture indicator."""
    global _activity_at
    now=time.time()
    with _activity_lock:
        if now-_activity_at<1:return
        _activity_at=now
    from installation import PROFILE
    temporary=PROFILE/('capture_activity.'+str(os.getpid())+'.tmp')
    try:
        PROFILE.mkdir(parents=True,exist_ok=True)
        temporary.write_text(json.dumps({'at':now,'source':'verified_game_window_wgc'}),encoding='utf-8')
        os.replace(temporary,PROFILE/'capture_activity.json')
    except OSError:pass
    finally:
        try:temporary.unlink(missing_ok=True)
        except OSError:pass

@dataclass(frozen=True)
class Policy:
    paused: bool = False
    pause_unfocused: bool = True

def read_policy(directory=None):
    if directory is None:
        from installation import PROFILE
        directory=PROFILE
    path=Path(directory)/'capture_privacy.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('schema')!=1:
            return Policy(paused=True)
        if any(key in data and not isinstance(data[key],bool) for key in ('paused','pause_unfocused')):
            return Policy(paused=True)
        return Policy(data.get('paused',False),data.get('pause_unfocused',True))
    except FileNotFoundError:return Policy()
    except (OSError,ValueError):return Policy(paused=True)

@dataclass(frozen=True)
class GameTarget:
    hwnd: int
    pid: int
    left: int
    top: int
    width: int
    height: int

def game_target(hwnd=None):
    """Class and executable must both match. Launcher/title-only matches fail."""
    if os.name!='nt':return None
    from ctypes import wintypes as w
    u=ctypes.WinDLL('user32');k=ctypes.WinDLL('kernel32')
    u.IsWindowVisible.argtypes=[w.HWND];u.IsIconic.argtypes=[w.HWND]
    u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)];u.ClientToScreen.argtypes=[w.HWND,ctypes.POINTER(w.POINT)]
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)];k.CloseHandle.argtypes=[w.HANDLE]
    def verify(candidate):
        if not u.IsWindowVisible(candidate) or u.IsIconic(candidate):return None
        cls=ctypes.create_unicode_buffer(128)
        if not u.GetClassNameW(candidate,cls,128) or cls.value!='CryENGINE':return None
        pid=w.DWORD();u.GetWindowThreadProcessId(candidate,ctypes.byref(pid))
        process=k.OpenProcess(0x1000,False,pid.value)
        if not process:return None
        try:
            path=ctypes.create_unicode_buffer(32768);length=w.DWORD(32768)
            if not k.QueryFullProcessImageNameW(process,0,path,ctypes.byref(length)) or Path(path.value).name.casefold()!='starcitizen.exe':return None
        finally:k.CloseHandle(process)
        rect=w.RECT();origin=w.POINT()
        if not u.GetClientRect(candidate,ctypes.byref(rect)) or not u.ClientToScreen(candidate,ctypes.byref(origin)):return None
        if rect.right<320 or rect.bottom<240:return None
        return GameTarget(int(candidate),pid.value,origin.x,origin.y,rect.right,rect.bottom)
    if hwnd:return verify(hwnd)
    found=[];callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    @callback
    def visit(candidate,param):
        target=verify(candidate)
        if target:found.append(target);return False
        return True
    u.EnumWindows.argtypes=[callback,w.LPARAM];u.EnumWindows(visit,0)
    return found[0] if found else None

def capture_allowed(target,policy=None):
    policy=policy or read_policy()
    if policy.paused or not target:return False
    if not policy.pause_unfocused:return True
    from ctypes import wintypes as w
    u=ctypes.WinDLL('user32');u.GetForegroundWindow.restype=w.HWND
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    foreground=u.GetForegroundWindow();pid=w.DWORD();u.GetWindowThreadProcessId(foreground,ctypes.byref(pid))
    if foreground==target.hwnd or pid.value==os.getpid():return True
    # The native UI and OCR Python helpers are separate owned processes.
    from installation import PROFILE
    try:
        status=json.loads((PROFILE/'native_status.json').read_text())
        return pid.value==status.get('pid') and time.time()-float(status.get('at',0))<3
    except (OSError,ValueError,TypeError):return False

def require_account_access(directory=None):
    if directory is None:
        from installation import PROFILE
        directory=PROFILE
    directory=Path(directory)
    try:
        data=json.loads((directory/'capture_privacy.json').read_text())
        if not isinstance(data,dict) or data.get('schema')!=1:raise PermissionError('Invalid privacy preferences')
        allowed=data.get('account_access',False)
        if not isinstance(allowed,bool) or not allowed:raise PermissionError('Game-account features are disabled in Privacy & capture')
    except FileNotFoundError:raise PermissionError('Enable game-account features in Privacy & capture first')
    except PermissionError:raise
    except (OSError,ValueError) as error:raise PermissionError('Cannot verify game-account permission') from error

class GameCapture:
    """Persistent WGC window session, latest frame only, no disk or network I/O."""
    def __init__(self,factory=None):
        self.factory=factory;self.controller=None;self.capture=None;self.target=None
        self.latest=None;self.lock=threading.Lock();self.generation=0
    def stop(self):
        self.generation+=1;controller=self.controller;self.controller=None;self.capture=None;self.target=None
        with self.lock:self.latest=None
        if controller:
            try:controller.stop()
            except Exception:pass
    def grab(self,rect=None):
        target=game_target()
        if not capture_allowed(target):self.stop();return None
        if self.target!=target or (self.controller and self.controller.is_finished()):
            self.stop();self.target=target
            if self.factory is None:
                from windows_capture import WindowsCapture
                self.factory=WindowsCapture
            generation=self.generation
            self.capture=self.factory(window_hwnd=target.hwnd,cursor_capture=False,draw_border=True,minimum_update_interval=125)
            @self.capture.event
            def on_frame_arrived(frame,control):
                if generation!=self.generation:return
                if read_policy().paused:
                    with self.lock:self.latest=None
                    control.stop();return
                with self.lock:self.latest=(frame.frame_buffer[:,:,:3].copy(),time.monotonic())
                record_activity()
            @self.capture.event
            def on_closed():
                if generation==self.generation:
                    with self.lock:self.latest=None
            self.controller=self.capture.start_free_threaded()
            # Manual terminal captures also get a fresh first frame without
            # needing a second click. The native hot path uses GPU cropping.
            deadline=time.monotonic()+.2
            while self.latest is None and time.monotonic()<deadline:time.sleep(.005)
        with self.lock:latest=self.latest
        if not latest or time.monotonic()-latest[1]>.5:return None
        frame=latest[0]
        # The returned frame is still the verified window surface, not the
        # desktop behind this rectangle. Clamp/zero-pad off-window regions.
        if rect is None:return frame.copy()
        import numpy as np
        x=int(rect['left'])-target.left;y=int(rect['top'])-target.top
        width=int(rect['width']);height=int(rect['height'])
        if not 0<width<=16384 or not 0<height<=16384:return None
        result=np.zeros((height,width,3),dtype=np.uint8)
        x0=max(0,x);y0=max(0,y);x1=min(frame.shape[1],x+width);y1=min(frame.shape[0],y+height)
        if x1>x0 and y1>y0:result[y0-y:y1-y,x0-x:x1-x]=frame[y0:y1,x0:x1]
        return result
