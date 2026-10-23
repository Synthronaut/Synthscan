"""Collect game UDP ping/pong and PresentMon player FPS. Administrator required.

No driver installation, injection, traffic modification, or outbound probes.
Only decoded timing/frame metadata is written; packet bodies are discarded.
Stops on game exit, --seconds deadline, or a local stop-request file.
"""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_lifecycle import SingleInstance, game_process_ids
from network_protocol import PingTracker, decode_control
from telemetry_core import IncrementalGameLog
from telemetry_ipc import publish_json
from frame_telemetry import PresentMonCollector
from tools.analyze_game_network import Frame, udp

from installation import PROFILE
LAB = PROFILE.parent / 'network-research'
LIVE = LAB / 'live-network.json'
STOP = LAB / 'stop-live-network'


def game_udp_ports(pid):
    api = ctypes.WinDLL('iphlpapi').GetExtendedUdpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                    wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
    api.restype = wintypes.ULONG
    size = wintypes.DWORD()
    result = api(None, ctypes.byref(size), False, socket.AF_INET, 1, 0)
    if result not in (0, 122):
        raise ctypes.WinError(result)
    buffer = ctypes.create_string_buffer(size.value)
    result = api(buffer, ctypes.byref(size), False, socket.AF_INET, 1, 0)
    if result:
        raise ctypes.WinError(result)
    count = struct.unpack_from('<I', buffer.raw)[0]
    ports = set()
    for i in range(count):
        _, port, owner = struct.unpack_from('<III', buffer.raw, 4+i*12)
        if owner == pid:
            ports.add(int.from_bytes(struct.pack('<I', port)[:2], 'big'))
    return ports


def local_route(address, port):
    # UDP connect selects a local route; no datagram is sent.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect((address, port))
        return route.getsockname()[0]


def run(seconds, owner=0):
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('Windows raw packet capture requires administrator access')
    lock = SingleInstance('network-probe')
    if not lock.acquired:
        return
    LAB.mkdir(parents=True, exist_ok=True)
    STOP.unlink(missing_ok=True)
    reader = IncrementalGameLog()
    # Do not attach capture to an old endpoint while replaying a large log.
    initial_size=Path(reader.log_path).stat().st_size if Path(reader.log_path).exists() else 0
    while reader.last_pos<initial_size:
        before=reader.last_pos;reader.poll()
        if reader.last_pos<=before:break
    tracker, counts, source, endpoint, latest = PingTracker(calibrate_clock=True), Counter(), None, None, None
    started, refresh, last_write = time.time(), 0, 0
    state = {"status": "starting", "started_at": started, "source": "game_udp_ping_pong"}
    report_path = LAB / time.strftime('live-results-%Y%m%d-%H%M%S.jsonl')
    frames = None
    try:
        with report_path.open('a', encoding='utf-8') as report:
            while not STOP.exists() and (seconds == 0 or time.time()-started < seconds):
                now = time.time()
                if now >= refresh:
                    if owner:
                        from native_bridge import owner_alive
                        if not owner_alive(owner):break
                    games = game_process_ids()
                    if len(games) != 1:
                        break
                    pid = next(iter(games))
                    if frames is None or frames.pid != pid:
                        if frames:
                            frames.stop()
                        frames = PresentMonCollector(pid)
                        frames.start()
                    reader.poll()
                    current = (pid, reader.session_token, reader.ip_address, reader.port)
                    if current != endpoint:
                        if source:
                            source.close()
                            source = None
                        tracker, latest = PingTracker(calibrate_clock=True), None
                        endpoint = current
                        if reader.connected and reader.ip_address and reader.port:
                            address, port = reader.ip_address, int(reader.port)
                            ports = game_udp_ports(pid)
                            local = local_route(address, port)
                            source = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
                            source.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
                            source.bind((local, 0))
                            source.ioctl(socket.SIO_RCVALL, 3)  # RCVALL_IPLEVEL; no promiscuous NIC mode.
                            source.settimeout(.25)
                    state.update(game_pid=pid, full_shard_id=reader.full_shard_id,
                                 joined_at=reader.joined_at, endpoint=list(current[2:]))
                    refresh = now + 1
                if source:
                    try:
                        raw = source.recv(65535)
                        observed_at = time.time()
                    except socket.timeout:
                        raw = None
                    if raw:
                        packet = udp(Frame(observed_at, 101, raw))
                        if packet:
                            if packet['source'] == address and packet['sport'] == port and packet['dport'] in ports:
                                direction = 'in'
                            elif packet['destination'] == address and packet['dport'] == port and packet['sport'] in ports:
                                direction = 'out'
                            else:
                                continue
                            counts['game_datagrams'] += 1
                            control = decode_control(packet['payload'])
                            if control:
                                counts[f'{direction}_type_{control.kind}'] += 1
                                local_port = packet['dport'] if direction == 'in' else packet['sport']
                                flow = (address, port, local, local_port)
                                sample = tracker.feed(control, direction, observed_at, flow)
                                if sample:
                                    latest = sample
                                    counts['rtt_samples'] += 1
                                    report.write(json.dumps(sample)+'\n')
                                    report.flush()
                else:
                    time.sleep(.1)
                if time.time()-last_write >= .5:
                    state.update(status='capturing' if source else 'waiting_for_join',
                                 written_at=time.time(), sample=latest, counters=dict(counts))
                    if not publish_json(LIVE, state):
                        counts['metadata_write_failures'] += 1
                    last_write = time.time()
    except Exception as error:
        state.update(status='error', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        if frames:
            frames.stop()
        if source:
            try:
                source.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            except OSError:
                pass
            source.close()
        state.update(status=state.get('status') if state.get('status') == 'error' else 'stopped',
                     written_at=time.time(), counters=dict(counts))
        publish_json(LIVE, state)
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--owner', type=int, default=0)
    options = parser.parse_args()
    if not 0 <= options.seconds <= 86400:
        parser.error('--seconds must be 0 (until game exit) or at most 86400')
    run(options.seconds,options.owner)
