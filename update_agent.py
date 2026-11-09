"""Detached updater: never launches, closes, or sends input to Star Citizen."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import logging
from pathlib import Path
import subprocess
import time


def image_path(pid):
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];api.OpenProcess.restype=w.HANDLE
    api.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    api.CloseHandle.argtypes=[w.HANDLE]
    handle=api.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        size=w.DWORD(32768);value=ctypes.create_unicode_buffer(size.value)
        return Path(value.value).resolve() if api.QueryFullProcessImageNameW(handle,0,value,ctypes.byref(size)) else None
    finally:api.CloseHandle(handle)


def idle_windows(root):
    """Defer for activating SynthScan windows; passive HUD overlays don't block."""
    root=Path(root).resolve();api=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    api.EnumWindows.argtypes=[callback_type,w.LPARAM];api.IsWindowVisible.argtypes=[w.HWND]
    api.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    api.GetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int];api.GetWindowLongPtrW.restype=ctypes.c_ssize_t
    api.GetForegroundWindow.restype=w.HWND
    foreground=w.DWORD();api.GetWindowThreadProcessId(api.GetForegroundWindow(),ctypes.byref(foreground))
    foreground_path=image_path(foreground.value)
    if foreground_path and foreground_path.is_relative_to(root):return False
    busy=[]
    @callback_type
    def check(hwnd,param):
        if not api.IsWindowVisible(hwnd) or api.GetWindowLongPtrW(hwnd,-20)&0x08000000:return True
        pid=w.DWORD();api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));path=image_path(pid.value)
        if path and path.is_relative_to(root):busy.append(pid.value)
        return True
    if not api.EnumWindows(check,0):return False
    return not busy


def stop_native(expected,timeout=25):
    expected=Path(expected).resolve();api=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    api.FindWindowW.argtypes=[w.LPCWSTR,w.LPCWSTR];api.FindWindowW.restype=w.HWND
    api.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)];api.GetWindowThreadProcessId.restype=w.DWORD
    api.PostThreadMessageW.argtypes=[w.DWORD,w.UINT,w.WPARAM,w.LPARAM]
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.CloseHandle.argtypes=[w.HANDLE]
    hwnd=api.FindWindowW('SCMinerGUI',None)
    if not hwnd:return
    pid=w.DWORD();thread=api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if image_path(pid.value)!=expected:raise ValueError('Another installation owns the native window; update deferred')
    handle=kernel.OpenProcess(0x100000,False,pid.value)
    if not handle:raise OSError('Could not wait for native shutdown')
    try:
        if not api.PostThreadMessageW(thread,0x12,0,0):raise OSError('Could not request native shutdown')
        if kernel.WaitForSingleObject(handle,int(timeout*1000))!=0:raise TimeoutError('SynthScan has not exited yet')
    finally:kernel.CloseHandle(handle)


def ready(target,directory,timeout=120):
    from app_updates import load
    from app_lifecycle import kernel
    api=kernel();deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        status=load(Path(directory)/'native_status.json');pid=status.get('pid')
        if pid and image_path(pid)==Path(target)/'dist/native/SynthScan.exe' and 0<=time.time()-status.get('at',0)<5:
            event=api.OpenEventW(0x100000,False,r'Local\SynthScan.Native.Ready')
            if event:
                try:
                    if api.WaitForSingleObject(event,0)==0:return True
                finally:api.CloseHandle(event)
        time.sleep(.25)
    stop_native(Path(target)/'dist/native/SynthScan.exe')
    return False


def run(root,current,directory):
    import app_lifecycle
    app_lifecycle.ROOT=Path(root).resolve()
    from app_lifecycle import SingleInstance,game_process_ids,instance_running,send_signal
    from app_updates import activate,load,write,UpdateDeferred
    root=Path(root).resolve();current=Path(current).resolve();directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=directory/'application_update.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    lock=SingleInstance('updating')
    if not lock.acquired:return
    def launch(target,health):
        subprocess.Popen([str(root/'SynthScan.exe'),'--autostart']+(['--update-health'] if health else []),
                         cwd=root,creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    stopped=False
    try:
        if game_process_ids() or not idle_windows(root) or instance_running('setup') or load(directory/'update_preferences.json').get('automatic_app',True) is not True:return
        send_signal('watcher-stop');deadline=time.monotonic()+8
        while instance_running('watcher') and time.monotonic()<deadline:time.sleep(.1)
        if instance_running('watcher'):raise TimeoutError('Startup watcher is still using the previous runtime')
        # Recheck after staging; starting the game cancels this attempt.
        if game_process_ids():return
        stop_native(current/'dist/native/SynthScan.exe');stopped=True
        send_signal('contract-share-stop')
        deadline=time.monotonic()+8
        while any(instance_running(kind) for kind in ('contract-share','native-top-hud','data-updates','native-timing','network-probe','mission-log')) and time.monotonic()<deadline:time.sleep(.1)
        if game_process_ids():return
        result=activate(root,current,directory,health=lambda target:ready(target,directory),launch=launch,
                        can_activate=lambda:not game_process_ids() and load(directory/'update_preferences.json').get('automatic_app',True) is True)
        write(directory/'app_update_status.json',dict(status='applied',detail='Application update installed and readiness verified.',at=time.time(),last_install=result))
        logging.info('Applied version %s',result['version'])
    except Exception as error:
        logging.exception('Update failed; previous application retained')
        pending=load(directory/'updates/pending.json')
        if pending.get('sha256') and not isinstance(error,UpdateDeferred):
            write(directory/'updates/failed.json',dict(sha256=pending['sha256'],reason=str(error),at=time.time()))
            (directory/'updates/pending.json').unlink(missing_ok=True)
        write(directory/'app_update_status.json',dict(status='staged' if isinstance(error,UpdateDeferred) else 'rolled_back' if stopped else 'deferred',detail=str(error),at=time.time()))
    finally:
        lock.close()
        if stopped:launch(root,False)
        else:
            # A game launch during preparation must not leave startup disabled.
            subprocess.Popen([str(root/'SynthScan.exe'),'--watch'],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW,
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--current',required=True);parser.add_argument('--profile',required=True)
    args=parser.parse_args();run(args.root,args.current,args.profile)
