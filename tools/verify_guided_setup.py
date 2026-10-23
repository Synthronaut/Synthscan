"""Render the app's own setup window off-screen with synthetic data only."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import app_launcher

def capture(window,file):
    user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
    user.GetParent.argtypes=[w.HWND];user.GetParent.restype=w.HWND
    user.GetWindowDC.argtypes=[w.HWND];user.GetWindowDC.restype=w.HDC
    user.ReleaseDC.argtypes=[w.HWND,w.HDC]
    user.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
    user.PrintWindow.argtypes=[w.HWND,w.HDC,w.UINT]
    gdi.CreateCompatibleDC.argtypes=[w.HDC];gdi.CreateCompatibleDC.restype=w.HDC
    gdi.CreateCompatibleBitmap.argtypes=[w.HDC,ctypes.c_int,ctypes.c_int];gdi.CreateCompatibleBitmap.restype=w.HBITMAP
    gdi.SelectObject.argtypes=[w.HDC,w.HGDIOBJ];gdi.SelectObject.restype=w.HGDIOBJ
    gdi.GetDIBits.argtypes=[w.HDC,w.HBITMAP,w.UINT,w.UINT,ctypes.c_void_p,ctypes.c_void_p,w.UINT]
    gdi.DeleteObject.argtypes=[w.HGDIOBJ];gdi.DeleteDC.argtypes=[w.HDC]
    hwnd=user.GetParent(window.winfo_id()) or window.winfo_id()
    user.SetWindowPos(hwnd,None,20,20,700,480,0x10|0x40);window.update()
    rect=w.RECT();user.GetWindowRect(hwnd,ctypes.byref(rect));width=rect.right-rect.left;height=rect.bottom-rect.top
    dc=user.GetWindowDC(hwnd);memory=gdi.CreateCompatibleDC(dc);bitmap=gdi.CreateCompatibleBitmap(dc,width,height)
    old=gdi.SelectObject(memory,bitmap)
    class Header(ctypes.Structure):
        _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
    header=Header(40,width,-height,1,32,0,width*height*4,0,0,0,0);pixels=ctypes.create_string_buffer(width*height*4)
    try:
        assert user.PrintWindow(hwnd,memory,2)
        assert gdi.GetDIBits(memory,bitmap,0,height,pixels,ctypes.byref(header),0)
        Image.frombytes('RGB',(width,height),pixels.raw,'raw','BGRX').save(file)
    finally:gdi.SelectObject(memory,old);gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,dc)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    # The test's own desktop is never made visible. Tk can map and paint its
    # widgets here without activating a window on the player's desktop.
    import uuid
    user=ctypes.windll.user32;kernel=ctypes.windll.kernel32
    user.GetThreadDesktop.argtypes=[w.DWORD];user.GetThreadDesktop.restype=w.HANDLE
    user.CreateDesktopW.argtypes=[w.LPCWSTR,w.LPCWSTR,ctypes.c_void_p,w.DWORD,w.DWORD,ctypes.c_void_p];user.CreateDesktopW.restype=w.HANDLE
    user.SetThreadDesktop.argtypes=[w.HANDLE];user.CloseDesktop.argtypes=[w.HANDLE]
    original=user.GetThreadDesktop(kernel.GetCurrentThreadId())
    desktop=user.CreateDesktopW('SynthScanTest_'+uuid.uuid4().hex,None,None,0,0x1ff,None)
    if not desktop or not user.SetThreadDesktop(desktop):raise ctypes.WinError()
    with tempfile.TemporaryDirectory() as d,patch.object(app_launcher,'PROFILE',Path(d)),patch.object(app_launcher,'ready',return_value=True):
        root=tk.Tk();root.withdraw();root.geometry('700x480')
        model=dict(state='restart',title='Your reputation is ready — restart Star Citizen',detail='Numbers are prepared for 14 corporation names. Fully exit the game and reopen it when convenient. Logging out alone will not reload the text.')
        try:
            with patch.object(app_launcher,'reputation_view',return_value=model):
                ui=app_launcher.SetupWindow(root,True);ui.poll();root.deiconify();root.update();capture(root,out/'reputation-ready.png')
                ui.messages.put(('error',('Windows blocked game text. Choose Allow game-text access, then retry.',True)))
                with patch.object(app_launcher,'ready',return_value=False):ui.poll();root.update();capture(root,out/'permission-help.png')
                def widgets(parent):
                    for child in parent.winfo_children():yield child;yield from widgets(child)
                clipping=[]
                for widget in widgets(root):
                    if widget.winfo_manager() and widget.winfo_rooty()+widget.winfo_height()>root.winfo_rooty()+root.winfo_height():clipping.append(str(widget))
                assert not clipping,clipping
                (out/'result.json').write_text(json.dumps(dict(own_window_only=True,synthetic_data=True,no_game_input=True,no_clipped_controls=True)),encoding='utf-8')
                ui.show.close();ui.stop.close()
        finally:root.destroy();user.SetThreadDesktop(original);user.CloseDesktop(desktop)
    print('Guided setup and permission-recovery screens rendered without clipped controls.')

if __name__=='__main__':main()
