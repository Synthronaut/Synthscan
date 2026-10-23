"""Read fresh, session-matched metadata from the separate packet listener."""
import math
import os
from pathlib import Path
from telemetry_ipc import read_shared_json

DEFAULT_PATH = Path(os.environ.get('LOCALAPPDATA', '.')) / 'SynthScan/network-research/live-network.json'


def read_network_ping(reader, now, path=DEFAULT_PATH):
    try:
        value = read_shared_json(path)
        if value['status'] != 'capturing' or value['source'] != 'game_udp_ping_pong':
            return None
        if not reader.connected or value['full_shard_id'] != reader.full_shard_id:
            return None
        if value['joined_at'] != reader.joined_at:
            return None
        if value['endpoint'] != [reader.ip_address, str(reader.port)]:
            return None
        sample = value['sample']
        if not sample or sample['source'] != 'game_udp_ping_pong':
            return None
        if sample.get('timing_method') != 'game_clock_calibrated':
            return None
        stamp, written = float(sample['observed_at']), float(value['written_at'])
        ping = float(sample['average_ms'])
        if not all(math.isfinite(v) for v in (stamp, written, ping)):
            return None
        if not -0.25 <= now-stamp <= 3 or not -0.25 <= now-written <= 2:
            return None
        if not 0 <= ping <= 3000 or not 3 <= sample['average_samples'] <= 16:
            return None
        return {'ping_ms': ping, 'observed_at': stamp, 'source': 'game_udp_ping_pong'}
    except (OSError, ValueError, KeyError, TypeError):
        return None
