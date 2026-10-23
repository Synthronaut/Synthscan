"""Small Windows lifecycle helpers; no game memory access or input injection."""
import ctypes
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def object_name(kind):
    key = hashlib.sha256(os.path.normcase(str(ROOT)).encode()).hexdigest()[:20]
    return rf"Local\SynthScan.{key}.{kind}"


def kernel():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
    api.CreateMutexW.restype = w.HANDLE
    api.OpenMutexW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
    api.OpenMutexW.restype = w.HANDLE
    api.CreateEventW.argtypes = [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
    api.CreateEventW.restype = w.HANDLE
    api.OpenEventW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
    api.OpenEventW.restype = w.HANDLE
    api.SetEvent.argtypes = [w.HANDLE]
    api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    api.WaitForSingleObject.restype = w.DWORD
    api.CloseHandle.argtypes = [w.HANDLE]
    return api


class SingleInstance:
    def __init__(self, kind="app"):
        self.api = kernel()
        self.handle = self.api.CreateMutexW(None, False, object_name(kind))
        error = ctypes.get_last_error()
        if not self.handle:
            raise ctypes.WinError(error)
        self.acquired = error != 183  # ERROR_ALREADY_EXISTS
        if not self.acquired:
            self.close()

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def instance_running(kind="app"):
    api = kernel()
    handle = api.OpenMutexW(0x100000, False, object_name(kind))
    if handle:
        api.CloseHandle(handle)
        return True
    error = ctypes.get_last_error()
    if error not in (0, 2):
        raise ctypes.WinError(error)
    return False


class Signal:
    def __init__(self, kind):
        self.api = kernel()
        self.handle = self.api.CreateEventW(None, False, False, object_name(kind))
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, seconds=0):
        result = self.api.WaitForSingleObject(self.handle, round(seconds * 1000))
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def send_signal(kind):
    api = kernel()
    handle = api.OpenEventW(2, False, object_name(kind))
    if not handle:
        return False
    try:
        return bool(api.SetEvent(handle))
    finally:
        api.CloseHandle(handle)


class ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", w.DWORD),
                ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]


def game_process_ids():
    """Read process names from Windows' snapshot; no handles to the game needed."""
    api = kernel()
    api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    api.CreateToolhelp32Snapshot.restype = w.HANDLE
    api.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(ProcessEntry)]
    api.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(ProcessEntry)]
    handle = api.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ProcessEntry(dwSize=ctypes.sizeof(ProcessEntry))
        found = set()
        more = api.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == "starcitizen.exe":
                found.add(entry.th32ProcessID)
            more = api.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return frozenset(found)
    finally:
        api.CloseHandle(handle)


class LaunchPolicy:
    """Launch once per game run. A manual app exit is respected until the next run."""
    def __init__(self):
        self.games = frozenset()
        self.launched = False

    def needs_launch(self, games, app_running):
        games = frozenset(games)
        if games != self.games:
            self.games = games
            self.launched = False
        if app_running:
            self.launched = True
        return bool(games) and not self.launched

    def mark_launched(self):
        self.launched = True
