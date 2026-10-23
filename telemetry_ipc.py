"""Small, replace-safe metadata files shared between telemetry processes."""
import ctypes
import json
import os
from pathlib import Path
import time

from telemetry_core import atomic_json


def read_shared_json(path, limit=16384):
    if os.name != 'nt':
        with Path(path).open('rb') as stream:
            raw = stream.read(limit+1)
    else:
        from ctypes import wintypes as w
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                   w.DWORD, w.DWORD, w.HANDLE]
        api.CreateFileW.restype = w.HANDLE
        api.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD,
                                 ctypes.POINTER(w.DWORD), ctypes.c_void_p]
        api.CloseHandle.argtypes = [w.HANDLE]
        # Ordinary Python opens can exclude FILE_SHARE_DELETE on Windows,
        # preventing the publisher's atomic replacement while a read is open.
        handle = api.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer = ctypes.create_string_buffer(limit+1)
            count = w.DWORD()
            if not api.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            raw = buffer.raw[:count.value]
        finally:
            api.CloseHandle(handle)
    if len(raw) > limit:
        raise ValueError('Telemetry metadata exceeds its size limit')
    return json.loads(raw.decode('utf-8-sig'))


def publish_json(path, value, attempts=5):
    """Retry transient Windows sharing errors; an unavailable update is not fatal.

    Old observations retain their timestamp and expire in the reader. Permanent
    errors must not be disguised as successful writes.
    """
    for attempt in range(attempts):
        try:
            atomic_json(path, value)
            return True
        except PermissionError:
            if attempt+1 < attempts:
                time.sleep(.005*(attempt+1))
    return False
