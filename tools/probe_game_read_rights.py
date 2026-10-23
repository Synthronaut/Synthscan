"""One-shot standard Windows read-access check. No access restrictions bypassed.

Queries the handle's granted rights and tries reading only the two-byte PE header
at the client's preferred image base. Never scans memory, dumps keys, writes to
the game, enables debug privileges, or installs a driver.
"""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_lifecycle import game_process_ids


def main():
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    api.OpenProcess.restype = w.HANDLE
    api.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    api.CloseHandle.argtypes = [w.HANDLE]
    ntquery = ctypes.WinDLL('ntdll').NtQueryObject
    ntquery.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
    games = game_process_ids()
    if len(games) != 1:
        raise RuntimeError('Expected exactly one running game')
    pid = next(iter(games))
    report = {'game_pid': pid, 'administrator': bool(ctypes.windll.shell32.IsUserAnAdmin()),
              'requested_access': '0x1010', 'read_scope': 'two-byte executable header only'}
    handle = api.OpenProcess(0x1010, False, pid)
    report['open_succeeded'] = bool(handle)
    if handle:
        try:
            # PUBLIC_OBJECT_BASIC_INFORMATION contains fourteen ULONG fields.
            # Some Windows builds require its exact size for this info class.
            info = ctypes.create_string_buffer(56)
            returned = w.ULONG()
            status = ntquery(handle, 0, info, len(info), ctypes.byref(returned))
            report['query_status'] = int(status)
            if status == 0:
                access = int.from_bytes(info.raw[4:8], 'little')
                report['granted_access'] = hex(access)
                report['vm_read_granted'] = bool(access & 0x10)
            header = ctypes.create_string_buffer(2)
            count = ctypes.c_size_t()
            ok = api.ReadProcessMemory(handle, ctypes.c_void_p(0x140000000), header, 2, ctypes.byref(count))
            report.update(read_succeeded=bool(ok), read_error=0 if ok else ctypes.get_last_error(),
                          bytes_read=count.value, executable_header_matches=header.raw == b'MZ')
        finally:
            api.CloseHandle(handle)
    else:
        report['open_error'] = ctypes.get_last_error()
    path = Path(os.environ['LOCALAPPDATA'])/'SynthScan/network-research/read-access.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
