"""Serialize SynthStrings edits across the per-user Python services."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path
import threading

_fallback = threading.RLock()


@contextmanager
def localization_lock(path):
    if os.name != 'nt':
        with _fallback:
            yield
        return
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
    api.CreateMutexW.restype = w.HANDLE
    api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    api.WaitForSingleObject.restype = w.DWORD
    api.ReleaseMutex.argtypes = [w.HANDLE]
    api.CloseHandle.argtypes = [w.HANDLE]
    key = hashlib.sha256(os.path.normcase(str(Path(path).resolve())).encode()).hexdigest()
    handle = api.CreateMutexW(None, False, 'Local\\SynthScan.Localization.' + key)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        result = api.WaitForSingleObject(handle, 5000)
        acquired = result in (0, 0x80)  # Includes a writer that exited unexpectedly.
        if not acquired:
            raise TimeoutError('Another SynthStrings update is still in progress')
        yield
    finally:
        if acquired:
            api.ReleaseMutex(handle)
        api.CloseHandle(handle)
