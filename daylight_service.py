"""Headless Day/Night Forecast service for the desktop TypeScript page.

Publishes the validated catalogue, per-body calibration and saved destination
to ``daylight_state.json`` and applies bounded commands from
``daylight_commands``. All forecasting rules stay in ``daylight.py`` and all
catalogue/calibration rules stay in ``daylight_catalogue.py``. Never controls
the game, reads game memory or sends input.
"""
import ctypes
import json
import logging
import math
from pathlib import Path
import threading
import time

import daylight_catalogue as catalogue
from refinery_orders import atomic_json

STATE_FILE = 'daylight_state.json'
COMMAND_DIR = 'daylight_commands'
PREFERENCES_FILE = 'daylight_preferences.json'
REFRESH_SECONDS = 6*3600
BUILD_SECONDS = 60
COMMAND_LIMIT = 16*1024
LABEL_LIMIT = 256
ACTIONS = {'daylight_refresh', 'daylight_preferences', 'daylight_observe'}


def owner_alive(pid):
    """True while the native owner process exists (SYNCHRONIZE handle)."""
    if not pid:
        return True
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.restype = ctypes.c_void_p
    api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = api.OpenProcess(0x00100000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5  # access denied still means it exists
    try:
        return api.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
    finally:
        api.CloseHandle(handle)


def label(value):
    if not isinstance(value, str) or not 1 <= len(value) <= LABEL_LIMIT:
        raise ValueError('Choose a destination from the list')
    return value


class DaylightService:
    def __init__(self, directory, owner=None, clock=time.time, build=catalogue.build_identity,
                 refresher=catalogue.refresh):
        self.directory = Path(directory)
        self.owner = owner
        self.clock = clock
        self.build_source = build
        self.refresher = refresher
        self.commands = self.directory/COMMAND_DIR
        self.commands.mkdir(parents=True, exist_ok=True)
        self.data = catalogue.load(self.directory)
        self.build = self.build_source()
        self.build_at = time.monotonic()
        self.preferences = self.read_preferences()
        self.sync = dict(state='idle', at=self.data.get('checked_at'), message='')
        self.notice = None
        self.revision = 0
        self.published = None
        self.lock = threading.Lock()
        self.fetch = None
        self.fetch_at = -REFRESH_SECONDS
        self.fetch_result = None

    # -- state -----------------------------------------------------------
    def read_preferences(self):
        try:
            saved = catalogue.read_json(self.directory/PREFERENCES_FILE)
        except (OSError, ValueError):
            return {}
        if not isinstance(saved, dict):
            return {}
        return {key: saved[key] for key in ('system', 'body', 'site') if isinstance(saved.get(key), str)}

    def calibrations(self):
        try:
            stamp = (self.directory/'daylight_calibration.json').stat().st_mtime_ns
        except OSError:
            stamp = None
        # Observations expire after seven days; re-evaluate at least each minute.
        key = (stamp, json.dumps(self.build, sort_keys=True, default=str), self.data['signature'], int(self.clock()//60))
        if key != getattr(self, 'calibration_key', None):
            result = {}
            for body in self.data['bodies']:
                offset, quality = catalogue.calibration(self.directory, self.data, body['name'], self.build, now=self.clock())
                result[body['name']] = dict(phase_offset=offset, quality=quality, calibrated=quality.startswith('Local observation'))
            self.calibration_key, self.calibration_cache = key, result
        return self.calibration_cache

    def view(self):
        source = {key: self.data[key] for key in ('schema', 'source', 'signature', 'bodies', 'sites')}
        source['checked_at'] = self.data.get('checked_at')
        return dict(kind='daylight_state', schema=1, owner_pid=self.owner, catalogue=source,
                    calibration=self.calibrations(), preferences=self.preferences,
                    build=dict(available=bool(self.build), patch=(self.build or {}).get('patch')),
                    sync=self.sync, notice=self.notice)

    def publish(self, force=False):
        view = self.view()
        encoded = json.dumps(view, sort_keys=True, allow_nan=False)
        if not force and encoded == self.published:
            return False
        self.revision += 1
        atomic_json(self.directory/STATE_FILE, dict(view, revision=self.revision, written_at=self.clock()))
        self.published = encoded
        return True

    # -- catalogue refresh ------------------------------------------------
    def refresh(self):
        if self.fetch and self.fetch.is_alive():
            return
        self.fetch_at = time.monotonic()
        self.sync = dict(state='checking', at=self.sync.get('at'), message='Checking the public catalogue…')

        def worker():
            try:
                result = ('data', self.refresher(self.directory))
            except Exception as exc:  # network/parse failure keeps the offline catalogue
                result = ('error', str(exc))
            with self.lock:
                self.fetch_result = result
        self.fetch = threading.Thread(target=worker, daemon=True)
        self.fetch.start()

    def collect(self):
        with self.lock:
            result, self.fetch_result = self.fetch_result, None
        if not result:
            return
        kind, value = result
        if kind == 'data':
            self.data = value
            self.sync = dict(state='ok', at=value.get('checked_at', self.clock()),
                             message='Public catalogue checked · timing calibration is separate')
        else:
            logging.info('Daylight catalogue refresh failed: %s', value)
            self.sync = dict(state='offline', at=self.sync.get('at'),
                             message='Offline catalogue in use · automatic refresh will retry')

    # -- commands ---------------------------------------------------------
    def site(self, command):
        key = (label(command.get('system')), label(command.get('body')), label(command.get('site')))
        row = next((s for s in self.data['sites'] if (s['system'], s['body'], s['name']) == key), None)
        if not row:
            raise ValueError('Choose a destination from the list')
        return row

    def command(self, command, now):
        if not isinstance(command, dict) or command.get('action') not in ACTIONS:
            raise ValueError('Unsupported daylight command')
        if self.owner and command.get('owner_pid') != self.owner:
            raise ValueError('Command belongs to another SynthScan window')
        stamp = command.get('at')
        if type(stamp) not in (int, float) or not math.isfinite(stamp) or not -5 <= now-stamp < 60:
            raise ValueError('Command expired')
        identifier = command.get('request_id')
        identifier = identifier if isinstance(identifier, str) and len(identifier) <= 80 else ''
        action = command['action']
        try:
            if action == 'daylight_refresh':
                self.refresh()
                return
            row = self.site(command)
            if action == 'daylight_preferences':
                preferences = dict(system=row['system'], body=row['body'], site=row['name'])
                if preferences != self.preferences:
                    atomic_json(self.directory/PREFERENCES_FILE, preferences)
                    self.preferences = preferences
                return
            kind = command.get('kind')
            at = command.get('observed_at')
            if kind not in ('sunrise', 'sunset'):
                raise ValueError('Choose sunrise or sunset')
            if type(at) not in (int, float) or not math.isfinite(at):
                raise ValueError('Use a valid local date and time')
            if not 0 <= now-at <= 7*86400:
                raise ValueError('Choose an observation from the last seven days')
            build = self.build_source()
            self.build, self.build_at = build, time.monotonic()
            if command.get('signature') != self.data['signature']:
                raise ValueError('Game build or catalogue changed; reopen the observation dialog')
            catalogue.save_observation(self.directory, self.data, row, build, float(at), kind)
            self.notice = dict(id=identifier, ok=True, message='Observation saved. '+row['body']+' clock adjusted.')
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            if action == 'daylight_observe':
                self.notice = dict(id=identifier, ok=False, message=str(exc)[:240])
            else:
                raise

    def drain(self):
        now = self.clock()
        for path in sorted(self.commands.glob('*.json'))[:12]:
            try:
                if path.stat().st_size > COMMAND_LIMIT:
                    raise ValueError('Daylight command exceeds size limit')
                self.command(json.loads(path.read_text(encoding='utf-8')), now)
            except (ValueError, TypeError, OSError, KeyError) as exc:
                logging.info('Daylight command ignored: %s', exc)
            finally:
                path.unlink(missing_ok=True)

    def step(self):
        before = (self.sync, self.notice, self.preferences, self.data.get('signature'))
        self.collect()
        self.drain()
        if time.monotonic()-self.build_at > BUILD_SECONDS:
            self.build, self.build_at = self.build_source(), time.monotonic()
            self.dirty = True
        if time.monotonic()-self.fetch_at > REFRESH_SECONDS:
            self.refresh()
        changed = before != (self.sync, self.notice, self.preferences, self.data.get('signature'))
        if changed or getattr(self, 'dirty', False) or time.monotonic()-getattr(self, 'checked_at', 0) > 30:
            self.dirty = False
            self.checked_at = time.monotonic()
            self.publish()


def main():
    import argparse
    from app_lifecycle import SingleInstance
    from native_control import DATA
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner', type=int, required=True)
    args = parser.parse_args()
    lock = SingleInstance(f'daylight-service-{args.owner}')
    if not lock.acquired:
        return
    try:
        service = DaylightService(DATA, args.owner)
        service.publish(force=True)
        while owner_alive(args.owner):
            service.step()
            time.sleep(.25)
    except Exception:
        logging.exception('Day/Night Forecast service failed')
    finally:
        lock.close()


if __name__ == '__main__':
    main()
