"""Bounded, read-only GPU and Windows memory recorder for supervised tests."""
import argparse
import csv
import ctypes
from ctypes import wintypes as w
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.gpu_diagnostics import gpu_sample,FIELDS,HOME


class MemoryStatus(ctypes.Structure):
    _fields_=[('length',w.DWORD),('load_percent',w.DWORD)]+[(name,ctypes.c_uint64) for name in
        ('total_physical','available_physical','total_pagefile','available_pagefile',
         'total_virtual','available_virtual','available_extended_virtual')]


def memory_sample():
    value=MemoryStatus();value.length=ctypes.sizeof(value)
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(MemoryStatus)]
    api.GlobalMemoryStatusEx.restype=w.BOOL
    if not api.GlobalMemoryStatusEx(ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())
    return dict(memory_load_percent=value.load_percent,
        total_physical_mib=round(value.total_physical/1024**2,1),
        available_physical_mib=round(value.available_physical/1024**2,1),
        total_pagefile_mib_reported=round(value.total_pagefile/1024**2,1),
        available_pagefile_mib_reported=round(value.available_pagefile/1024**2,1))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--seconds',type=int,default=1800)
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,50}',args.label) or not 1<=args.seconds<=1800:
        parser.error('Use a short lowercase label and duration from 1 to 1800 seconds')
    out=HOME/'results'/(args.label+'-'+datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
    fields=['observed_at']+FIELDS+list(memory_sample())
    metadata=dict(state='recording',recording_started_at=datetime.now().astimezone().isoformat(),
        maximum_recording_seconds=args.seconds,read_only=True,does_not_determine_test_pass=True)
    (out/'recording.json').write_text(json.dumps(metadata,indent=2))
    print('Recording:',out.resolve(),flush=True)
    started=time.monotonic();samples=0;errors=0;reason='duration_reached'
    try:
        with (out/'hardware-sensors.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            while time.monotonic()-started<args.seconds:
                if (out/'stop-recording').exists():reason='stop_marker';break
                try:
                    row=dict(observed_at=datetime.now().astimezone().isoformat(),**gpu_sample(),**memory_sample())
                    writer.writerow(row);f.flush();samples+=1
                except Exception as exc:
                    errors+=1;print('Sample unavailable:',type(exc).__name__,flush=True)
                time.sleep(2)
    except KeyboardInterrupt:reason='user_stopped'
    finally:
        metadata.update(state='finished',samples=samples,sample_errors=errors,stop_reason=reason,
                        elapsed_seconds=round(time.monotonic()-started,1))
        (out/'recording.json').write_text(json.dumps(metadata,indent=2))
        print('Recording finished:',reason,flush=True)


if __name__=='__main__':main()
