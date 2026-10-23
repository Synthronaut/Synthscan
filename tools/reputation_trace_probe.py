"""Prepare a local reputation diagnostic for a normal future restart.

Uses the existing trace-configuration research, not console input or memory access.
Preparing files does not demonstrate that the released game honors the settings.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.snare_trace_probe import GAME, LAUNCHER, default_filter, diagnostic_environment, running_names

PROFILE = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'SynthScan/reputation-trace-probe'
EVENTS = ['Local Trace Config loaded', 'OnReputationServiceExternalMessage',
          'CommandGetPlayerReputationClient::<lambda_1>::operator ()',
          'UpdateReputationCache', 'GetScoreHistory', 'QueryReputations']

# Only the traced, explicitly rendered push message is recognized. Structured
# trace payload formats remain unsupported until a real sample establishes them.
IDENTITY = r'(?:[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[0-9]+)'
SCORE_MESSAGE = re.compile(
    r'Received reputation update from push message for: subject (' + IDENTITY +
    r') - entity (' + IDENTITY + r') - scope: (' + IDENTITY +
    r') - score (-?\d+) - standing ([^\s,]+)')


def parse_score_candidate(line):
    """A candidate is not an authenticated own-account observation."""
    try:
        value = json.loads(line)
    except (ValueError, TypeError):
        value = line

    def strings(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for child in node.values():
                yield from strings(child)
        elif isinstance(node, list):
            for child in node:
                yield from strings(child)

    for text in strings(value):
        match = SCORE_MESSAGE.search(text)
        if match:
            score = int(match[4])
            if not -(2**31) <= score < 2**31:
                continue
            return dict(subject=match[1], entity=match[2], scope=match[3], score=score,
                        standing=match[5], own_account_verified=False)
    return None


def status(profile=PROFILE):
    result = dict(state='prepared_only', trace_ready=False, numeric_score_candidates=0,
                  live_balance_verified=False, files=[], skipped_files=0)
    try:
        manifest = json.loads((profile / 'probe_manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        result['state'] = 'not_prepared'
        return result
    launched = manifest.get('launch_requested_at')
    if not isinstance(launched, (int, float)) or launched > time.time():
        return result
    prefix = manifest['environment']['SYSTEM_TRACE_OUTPUT_FILENAME']
    if not re.fullmatch(r'SynthScanReputationTrace_[0-9a-f]{10}', prefix):
        result['state'] = 'invalid_run_manifest'
        return result
    result['state'] = 'awaiting_filter_control'
    expected = str((profile / 'trace_filter.json').resolve()).replace('\\', '/').casefold()
    total = 0
    for path in sorted((profile / 'events').glob(prefix + '*')):
        if not path.is_file() or path.stat().st_mtime < launched:
            continue
        size = path.stat().st_size
        if size > 20 * 1024 * 1024 or total + size > 64 * 1024 * 1024:
            result['skipped_files'] += 1
            continue
        total += size
        result['files'].append(dict(name=path.name, bytes=size))
        with path.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                normalized = line.replace('\\\\', '/').replace('\\', '/').casefold()
                if 'Local Trace Config loaded' in line and expected in normalized:
                    result['trace_ready'] = True
                # Windows hosted runners and some installs use an 8.3 TEMP
                # alias. Compare decoded paths after resolving both spellings.
                try:
                    control=json.loads(line)
                    if (isinstance(control,dict) and control.get('event')=='Local Trace Config loaded'
                            and isinstance(control.get('path'),str)
                            and Path(control['path']).resolve()==(profile/'trace_filter.json').resolve()):
                        result['trace_ready']=True
                except (ValueError,OSError):pass
                if parse_score_candidate(line):
                    result['numeric_score_candidates'] += 1
    if result['trace_ready']:
        result['state'] = 'filter_loaded_candidates_unverified'
    else:
        # A normal game launch is not readiness. Surface a known startup
        # override instead of leaving a misleading perpetual waiting state.
        try:
            with (GAME/'Game.log').open(encoding='utf-8',errors='replace') as stream:
                startup=stream.read(128*1024)
            from telemetry_core import timestamp
            match=re.search(r'^<([^>]+)>',startup)
            started=timestamp(match[1]) if match else None
            if started is not None and started>=launched:
                overridden="'SYSTEM_TRACE_SERVICE_ENABLED' was already set via 'Cmdline"
                if overridden in startup:
                    result['remote_trace_disabled']=False
                    result['startup_override_detected']=True
                    result['state']='startup_override_no_local_filter_control'
        except OSError:
            pass
    return result


def prepare(profile=PROFILE):
    raw = (GAME / 'Bin64/StarCitizen.exe').read_bytes()
    base = default_filter(raw)
    config = copy.deepcopy(base)
    config['Publish'] = [{'Severity': ['Emergency', 'Alert', 'Critical', 'Error',
                                     'Warning', 'Notice', 'Info', 'Debug'],
                          'Include Events': EVENTS}]
    profile.mkdir(parents=True, exist_ok=True)
    (profile / 'events').mkdir(exist_ok=True)
    (profile / 'trace_filter.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    environment = diagnostic_environment(profile)
    environment['SYSTEM_TRACE_OUTPUT_FILENAME'] = 'SynthScanReputationTrace_' + uuid.uuid4().hex[:10]
    manifest = dict(schema=1, exe_sha256=hashlib.sha256(raw).hexdigest(),
                    environment=environment, events=EVENTS, runtime_verified=False,
                    live_balance_verified=False, local_only=True)
    (profile / 'probe_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def launch():
    names = running_names()
    if 'starcitizen.exe' in names or 'rsi launcher.exe' in names:
        raise RuntimeError('Exit Star Citizen and quit RSI Launcher normally first. Neither will be closed by this helper.')
    if not LAUNCHER.is_file():
        raise FileNotFoundError('RSI Launcher was not found at its configured path')
    manifest = prepare()
    environment = os.environ.copy()
    environment.update(manifest['environment'])
    manifest['launch_requested_at'] = time.time()
    (PROFILE / 'probe_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    process = subprocess.Popen([str(LAUNCHER)], env=environment, cwd=LAUNCHER.parent,
                               creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    manifest['launcher_pid'] = process.pid
    (PROFILE / 'probe_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Diagnostic launcher started. Launch the game normally. Exact reputation output is still unverified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.launch:
        launch()
    elif args.status:
        print(json.dumps(status(), indent=2))
    else:
        manifest = prepare()
        print(json.dumps(dict(prepared=True, profile=str(PROFILE),
                              events=manifest['events'], runtime_verified=False)))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('Reputation trace test was not started:', error)
        raise SystemExit(1)
