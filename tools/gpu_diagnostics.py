"""Local GPU diagnostics launcher. Never changes clocks, BIOS or game settings.

Default invocation shows a menu. --preflight performs no GPU stress work.
VRAM testing runs only after the user selects it with Star Citizen closed.
"""
import argparse
import csv
import ctypes
from ctypes import wintypes as w
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_lifecycle import game_process_ids,SingleInstance

HOME=ROOT/'research/performance/2026-10-31/gpu-check'
VRAM=HOME/'tools/memtest_vulkan.exe'
OCCT=HOME/'tools/OCCT.exe'
EXPECTED_VRAM='09e67704210762ae8d8ad70fe6d71275eefbe815cc2c0658cd5afc8e231d0df6'
EXPECTED_OCCT='64f403fb690afa724b3bf31f439f8a29c81c34b4d3496a63456a9ab224e9599b'
FIELDS=['name','driver_version','temperature.gpu','memory.total','memory.used',
        'power.draw','power.limit','clocks.gr','clocks.mem','fan.speed','utilization.gpu',
        'clocks_event_reasons.hw_thermal_slowdown','clocks_event_reasons.hw_power_brake_slowdown']


def verify(path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Diagnostic tool does not match its prepared hash: '+path.name)


def gpu_sample():
    result=subprocess.run(['nvidia-smi','--query-gpu='+','.join(FIELDS),'--format=csv,noheader,nounits'],
        capture_output=True,text=True,timeout=6,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    rows=list(csv.reader(result.stdout.strip().splitlines(),skipinitialspace=True))
    if len(rows)!=1 or len(rows[0])!=len(FIELDS):raise ValueError('Expected exactly one NVIDIA GPU')
    return dict(zip(FIELDS,rows[0]))


def preflight():
    # This guard precedes even tool validation and NVIDIA queries.
    if game_process_ids():return dict(ok=False,reason='Close Star Citizen fully before testing. No test started.')
    verify(VRAM,EXPECTED_VRAM);verify(OCCT,EXPECTED_OCCT)
    sample=gpu_sample()
    if 'RTX 3080' not in sample['name']:return dict(ok=False,reason='Prepared test targets your RTX 3080; GPU identity changed.')
    return dict(ok=True,gpu=sample['name'],driver=sample['driver_version'],sample=sample)


class KillOnCloseJob:
    """Own diagnostic child is killed if its launcher window is closed."""
    def __init__(self):
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('process_limit',w.DWORD),
                ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                      ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];self.api.CreateJobObjectW.restype=w.HANDLE
        self.api.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        self.api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        self.api.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        limits=Extended();limits.basic.flags=0x2000
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            error=ctypes.get_last_error();self.close();raise ctypes.WinError(error)

    def assign(self,process):
        if not self.api.AssignProcessToJobObject(self.handle,w.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None


def assessment(reason,code,standard_pass,error_found,seconds):
    if error_found or (code is not None and code&0xE0==0x40 and code&2):return 'errors_detected'
    if reason=='duration_reached' and standard_pass and seconds>=600 and code is not None and code&0xE0==0x40 and code&1 and not code&4:
        return 'no_errors_observed_in_this_run'
    return 'inconclusive'


def stop_test(process):
    if process.poll() is None:
        try:process.send_signal(signal.CTRL_BREAK_EVENT);process.wait(timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            process.kill();process.wait(timeout=5)


def run_vram():
    check=preflight()
    if not check['ok']:print(check['reason']);return 2
    sample=check['sample'];free_mib=float(sample['memory.total'])-float(sample['memory.used'])
    test_bytes=int(min(8192,free_mib-768))*1024*1024
    if test_bytes<4*1024**3:print('Not enough free VRAM for the prepared test. Close GPU-heavy applications.');return 2
    out=HOME/'results'/datetime.now().strftime('%Y%m%d-%H%M%S-%f');out.mkdir(parents=True)
    metadata=dict(state='running',started_at=datetime.now().astimezone().isoformat(),test='memtest_vulkan',
        gpu=sample['name'],driver=sample['driver_version'],requested_bytes=test_bytes,duration_seconds=600,
        settings_changed=False,xmp_changed=False)
    result_path=out/'result.json'
    result_path.write_text(json.dumps(metadata,indent=2))
    print('VRAM check: 10 minutes. Close this window to stop. XMP and clocks stay unchanged.')
    print('Results:',out)
    error_found=threading.Event();standard_pass=threading.Event();target_verified=threading.Event();wrong_target=threading.Event();reason='not_started'
    process=None;job=None;reader=None;started=time.monotonic();samples=0;failures=0
    try:
        job=KillOnCloseJob()
        # Explicit device and size run the upstream tool in a single process.
        process=subprocess.Popen([str(VRAM),'1',str(test_bytes)],cwd=out,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        job.assign(process)
        def read_output():
            with (out/'vram.log').open('w',encoding='utf-8') as log:
                for line in process.stdout:
                    log.write(line);log.flush();print(line.rstrip(),flush=True)
                    if 'Error found.' in line or 'ERRORS FOUND' in line:error_found.set()
                    if 'Standard 5-minute test PASSed!' in line:standard_pass.set()
                    if 'Standard 5-minute test of' in line:
                        if 'NVIDIA GeForce RTX 3080' in line and 'Microsoft Direct3D12' not in line:target_verified.set()
                        else:wrong_target.set()
        reader=threading.Thread(target=read_output,daemon=True);reader.start();reason='tool_exited'
        with (out/'gpu-sensors.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['observed_at']+FIELDS);writer.writeheader();f.flush()
            while process.poll() is None:
                if error_found.is_set():reason='error_reported';break
                if wrong_target.is_set():reason='unexpected_vulkan_device';break
                if game_process_ids():reason='game_started';break
                if time.monotonic()-started>=600:reason='duration_reached';break
                try:
                    values=gpu_sample();failures=0
                    writer.writerow(dict(observed_at=datetime.now().astimezone().isoformat(),**values));f.flush();samples+=1
                    if float(values['temperature.gpu'])>=90:reason='gpu_core_temperature_guard';break
                except Exception:
                    failures+=1
                    if failures>=3:reason='sensor_unavailable';break
                time.sleep(2)
    except KeyboardInterrupt:reason='user_stopped'
    except Exception as exc:reason='launcher_error_'+type(exc).__name__
    finally:
        if process is not None:stop_test(process)
        if reader is not None:reader.join(timeout=5)
        if job is not None:job.close()
        code=process.returncode if process is not None else None
        elapsed=time.monotonic()-started
        outcome=assessment(reason,code,standard_pass.is_set(),error_found.is_set(),elapsed)
        if outcome=='no_errors_observed_in_this_run' and not target_verified.is_set():outcome='inconclusive'
        metadata.update(state='finished',outcome=outcome,stop_reason=reason,exit_code=code,elapsed_seconds=round(elapsed,1),
                        sensor_samples=samples,standard_five_minute_pass_seen=standard_pass.is_set(),target_verified=target_verified.is_set())
        result_path.write_text(json.dumps(metadata,indent=2))
    print('\nResult:',outcome,'Reason:',reason)
    print('A clean run does not certify the card healthy. Report any failure for comparison with your crashes.')
    return 1 if outcome=='errors_detected' else 0


def open_occt(memory=False):
    check=preflight()
    if not check['ok']:print(check['reason']);return 2
    if memory:
        print('In OCCT: Stability test > Memory. Leave XMP and BIOS unchanged.')
        print('Run 20 minutes using the default memory preset and 70% memory allocation.')
        print('Keep error detection enabled. Stop on any error or CPU reaching 95 C.')
    else:
        print('In OCCT: Stability test > 3D Adaptive; RTX 3080; error detection ON.')
        print('First run: 10 minutes, Steady mode, 50% intensity. Then cool down.')
        print('Second run: 10 minutes, Variable mode, error detection ON. Save the error count/result.')
        print('Stop on errors, artifacts, a driver reset, or GPU core reaching 90 C.')
    print('Leave tuning and combined Power tests alone for this comparison.')
    os.startfile(str(OCCT))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true');parser.add_argument('--vram',action='store_true')
    args=parser.parse_args()
    if args.preflight:print(json.dumps(preflight(),indent=2));return 0
    lock=SingleInstance('gpu-diagnostics')
    if not lock.acquired:print('GPU Check is already open.');return 2
    try:
        if args.vram:return run_vram()
        print('GPU CHECK\n1. Ten-minute VRAM error test (logs automatically)\n2. Open OCCT for the GPU-core test\n3. Open OCCT for RAM testing with XMP enabled\n4. Exit')
        choice=input('Choose 1, 2, 3 or 4: ').strip()
        if choice=='1':return run_vram()
        if choice=='2':return open_occt()
        if choice=='3':return open_occt(memory=True)
        return 0
    finally:lock.close()


if __name__=='__main__':raise SystemExit(main())
