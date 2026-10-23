"""Consume fresh PresentMon measurements for the currently running game PID."""
import math

from app_lifecycle import game_process_ids
from frame_telemetry import LIVE_FRAMES
from telemetry_ipc import read_shared_json


def read_client_fps(now, path=LIVE_FRAMES, current_pids=None):
    try:
        data = read_shared_json(path)
        if data['status'] != 'capturing' or data['source'] != 'presentmon_application_presents':
            return None
        pids = game_process_ids() if current_pids is None else current_pids
        if data['game_pid'] not in pids:
            return None
        sample = data['sample']
        if not sample or sample['source'] != data['source']:
            return None
        stamp, written, fps = float(sample['observed_at']), float(data['written_at']), float(sample['client_fps'])
        if not all(math.isfinite(value) for value in (stamp, written, fps)):
            return None
        if not -.25 <= now-stamp <= 2 or not -.25 <= now-written <= 2:
            return None
        if not 0 < fps <= 2000 or sample['frames_in_window'] < 3:
            return None
        return {'client_fps': fps, 'observed_at': stamp, 'source': data['source']}
    except (OSError, ValueError, KeyError, TypeError):
        return None
