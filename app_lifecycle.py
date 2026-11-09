"""Small Windows lifecycle helpers; no game memory access or input injection."""
import ctypes
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def object_name(kind):
    # Versioned runtimes share one installation's helper/update mutexes.
    anchor=ROOT
    if ROOT.parent.name=='versions' and len(ROOT.name)==64 and all(c in '0123456789abcdef' for c in ROOT.name) and (ROOT.parent.parent/'SynthScan.exe').is_file():anchor=ROOT.parent.parent
    key = hashlib.sha256(os.path.normcase(str(anchor)).encode()).hexdigest()[:20]
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


def named_processes(names):
    """PID/parent inventory by executable name; no process handles or memory."""
    names={name.casefold() for name in names}
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
        found = {}
        more = api.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() in names:
                found[entry.th32ProcessID]=(entry.szExeFile.casefold(),entry.th32ParentProcessID)
            more = api.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return found
    finally:
        api.CloseHandle(handle)


def game_process_ids():
    return frozenset(named_processes({'starcitizen.exe'}))


def launcher_process_ids():
    """Only launcher roots: Electron renderer restarts are not new sessions."""
    rows=named_processes({'rsi launcher.exe','rsilauncher.exe'})
    return frozenset(pid for pid,(_,parent) in rows.items() if parent not in rows)


def launcher_session_key(pids):
    """Launcher creation time keeps a reused PID from suppressing a new check."""
    if os.name!='nt':return ','.join(map(str,sorted(pids)))
    api=kernel();api.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];api.OpenProcess.restype=w.HANDLE
    api.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
    result=[]
    for pid in sorted(pids):
        handle=api.OpenProcess(0x1000,False,pid)
        if not handle:result.append(str(pid));continue
        try:
            created,exited,system,user=(w.FILETIME() for _ in range(4))
            if api.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(system),ctypes.byref(user)):
                result.append(f'{pid}:{created.dwHighDateTime}:{created.dwLowDateTime}')
            else:result.append(str(pid))
        finally:api.CloseHandle(handle)
    return ','.join(result)


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
