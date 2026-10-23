"""Read application frame presentation events using the PresentMon CLI.

Only the selected game PID is tracked. No renderer injection or game memory
access is used. Application presentation FPS is separate from server tick rate.
"""
from collections import deque
import csv
import ctypes
import math
import os
from pathlib import Path
import subprocess
import threading
import time

from telemetry_ipc import publish_json

BASE = Path(os.environ.get('LOCALAPPDATA', '.')) / 'SynthScan'
LIVE_FRAMES = BASE / 'network-research/live-frames.json'
PRESENTMON = BASE / 'tools/PresentMon-2.6.0-x64.exe'


def qpc_frequency():
    value = ctypes.c_longlong()
    if not ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(value)):
        raise ctypes.WinError()
    return value.value


def qpc_seconds():
    value = ctypes.c_longlong()
    if not ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(value)):
        raise ctypes.WinError()
    return value.value / qpc_frequency()


class FrameWindow:
    def __init__(self, pid, frequency):
        self.pid, self.frequency = pid, frequency
        self.chains = {}
        self.total_frames = 0

    def add(self, row, now_qpc):
        try:
            if int(row['ProcessID']) != self.pid:
                return False
            stamp = int(row['QPCTime']) / self.frequency
            chain = row['SwapChainAddress']
            if not math.isfinite(stamp) or not -.05 <= now_qpc-stamp <= 3:
                return False
            if chain not in self.chains:
                if len(self.chains) >= 32:
                    oldest = min(self.chains, key=lambda c: self.chains[c][-1] if self.chains[c] else -math.inf)
                    del self.chains[oldest]
                self.chains[chain] = deque(maxlen=4000)
            points = self.chains[chain]
            if points and stamp <= points[-1]:
                return False
            points.append(stamp)
            self.total_frames += 1
            return True
        except (KeyError, TypeError, ValueError, OverflowError):
            return False

    def sample(self, now_qpc, now_wall):
        candidates = []
        for points in self.chains.values():
            while points and now_qpc-points[0] > 4:
                points.popleft()
            recent = [stamp for stamp in points if points[-1]-stamp <= 1]
            if len(recent) >= 3 and -.05 <= now_qpc-recent[-1] <= 2:
                span = recent[-1]-recent[0]
                if span > 0:
                    fps = (len(recent)-1)/span
                    if 0 < fps <= 2000:
                        candidates.append((len(recent), fps, recent[-1]))
        if not candidates:
            return None
        count, fps, last = max(candidates)
        return {'client_fps': fps, 'observed_at': now_wall-max(0, now_qpc-last),
                'frames_in_window': count, 'source': 'presentmon_application_presents',
                'definition': 'application present rate; not server FPS or hardware display refresh'}


class PresentMonCollector:
    def __init__(self, pid, executable=PRESENTMON, output=LIVE_FRAMES):
        self.pid, self.executable, self.output = pid, Path(executable), Path(output)
        self.process = None
        self.thread = None
        self.stopping = threading.Event()
        self.process_lock = threading.Lock()
        self.session = f'SynthScanFrames.{os.getpid()}.{pid}'
        self.state = {'game_pid': pid, 'source': 'presentmon_application_presents',
                      'status': 'starting', 'started_at': time.time(), 'sample': None}

    def publish(self, status, **kwargs):
        self.state.update(status=status, written_at=time.time(), **kwargs)
        return publish_json(self.output, self.state)

    def start(self):
        self.thread = threading.Thread(target=self.collect, daemon=True, name='SynthScanFrameEvents')
        self.thread.start()

    def collect(self):
        if not self.executable.is_file():
            self.publish('unavailable', error='PresentMon standalone executable was not found')
            return
        self.output.parent.mkdir(parents=True, exist_ok=True)
        args = [str(self.executable), '--process_id', str(self.pid), '--session_name', self.session,
                '--output_stdout', '--no_console_stats', '--no_track_input', '--no_track_gpu',
                '--no_track_display', '--qpc_time', '--v1_metrics']
        rows = 0
        try:
            self.publish('starting')
            frequency = qpc_frequency()
            window = FrameWindow(self.pid, frequency)
            with self.output.with_suffix('.log').open('w', encoding='utf-8') as errors:
                with self.process_lock:
                    if self.stopping.is_set():
                        return
                    self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors,
                                                    text=True, encoding='utf-8-sig', errors='replace',
                                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                                    bufsize=1)
                window_lock, reader_done = threading.Lock(), threading.Event()
                reader_errors = []
                def consume_rows():
                    nonlocal rows
                    try:
                        for row in csv.DictReader(self.process.stdout):
                            if self.stopping.is_set():
                                break
                            with window_lock:
                                rows += 1
                                window.add(row, qpc_seconds())
                    except Exception as error:
                        if not self.stopping.is_set():
                            reader_errors.append(f'{type(error).__name__}: {error}')
                    finally:
                        reader_done.set()
                consumer = threading.Thread(target=consume_rows, daemon=True, name='SynthScanFrameCSV')
                consumer.start()
                # PresentMon can deliver CSV rows in batches. Publish from a
                # timer after consuming them, rather than sampling the first
                # (oldest) row of every batch and rejecting all newer frames.
                while not self.stopping.is_set() and not reader_done.wait(.25):
                    now_qpc, now = qpc_seconds(), time.time()
                    with window_lock:
                        sample, accepted = window.sample(now_qpc, now), window.total_frames
                    self.publish('capturing', sample=sample, csv_rows=rows,
                                 accepted_frames=accepted, reader_errors=reader_errors)
                consumer.join(timeout=1)
                code = self.process.wait(timeout=3)
                self.publish('stopped' if self.stopping.is_set() else 'error', sample=None,
                             exit_code=code, csv_rows=rows, accepted_frames=window.total_frames)
        except Exception as error:
            self.publish('error', sample=None, error=f'{type(error).__name__}: {error}')
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            if self.process and self.process.stdout:
                self.process.stdout.close()

    def stop(self):
        with self.process_lock:
            self.stopping.set()
        if self.process and self.process.poll() is None:
            # Stop only our uniquely named ETW session, never another monitor's.
            try:
                subprocess.run([str(self.executable), '--session_name', self.session,
                                '--terminate_existing_session'], timeout=3,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
        if self.thread:
            self.thread.join(timeout=2)
        self.publish('stopped', sample=None)
