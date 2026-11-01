"""Passive overlay input policy. No mouse movement, injection or focus changes."""
import ctypes
from ctypes import wintypes as w


def protect_game_input(foreground_pid, own_pids, game_present):
    return bool(game_present and (not foreground_pid or foreground_pid not in own_pids))


def foreground_process_id():
    api=ctypes.windll.user32
    api.GetForegroundWindow.restype=w.HWND
    api.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    pid=w.DWORD();api.GetWindowThreadProcessId(api.GetForegroundWindow(),ctypes.byref(pid))
    return pid.value


def set_passthrough(hwnd, protected, api=None):
    api=ctypes.windll.user32 if api is None else api
    api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.GetWindowLongW.restype=ctypes.c_long
    api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
    style=api.GetWindowLongW(hwnd,-20)
    wanted=style|0x08000000  # WS_EX_NOACTIVATE: never grab keyboard focus
    wanted=(wanted|0x20) if protected else (wanted&~0x20)
    if wanted!=style:api.SetWindowLongW(hwnd,-20,wanted)
    return wanted


def input_blocked(control):
    guard=getattr(control,'input_guard',None)
    try:return bool(guard()) if guard else bool(getattr(control,'input_protected',True))
    except OSError:return True
