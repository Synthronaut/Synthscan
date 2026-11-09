"""Passive, local evidence capture while the current native app keeps running.

Only consumes already-published own-account data. Never reads credentials or
starts account requests. The ledger can replay this append-only evidence file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from telemetry_ipc import read_shared_json, publish_json


def capture(directory, owner):
    from native_bridge import owner_alive
    directory = Path(directory)
    seen = {}
    path = directory / 'mission_evidence.jsonl'
    with path.open('a', encoding='utf-8', buffering=1) as stream:
        while owner_alive(owner):
            from account_permission import require_account_access
            try:
                require_account_access(directory)
                for filename, kind in [('reputation_snapshot.json', 'reputation'),
                                       ('questing_journal.json', 'missions'),
                                       ('session_state.json', 'context')]:
                    value = read_shared_json(directory / filename, limit=4*1024*1024) or {}
                    if kind == 'context':
                        value = {key: value.get(key) for key in ('written_at', 'questing')}
                    if not value:
                        continue
                    # Context timestamps change every second; retain meaningful
                    # mission/participant changes rather than redundant frames.
                    key = json.dumps(value.get('questing') if kind == 'context' else value,
                                     sort_keys=True, allow_nan=False)
                    digest = hashlib.sha256(key.encode()).hexdigest()
                    if seen.get(kind) == digest:
                        continue
                    stream.write(json.dumps(dict(kind=kind, observed_at=time.time(), data=value),
                                            ensure_ascii=False, allow_nan=False) + '\n')
                    seen[kind] = digest
                publish_json(directory / 'mission_capture_status.json',
                             dict(at=time.time(), owner_pid=owner, running=True, source='existing app snapshots'))
            except (OSError, ValueError, TypeError, PermissionError):
                pass
            time.sleep(1)
    publish_json(directory / 'mission_capture_status.json',
                 dict(at=time.time(), owner_pid=owner, running=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--owner', type=int, required=True)
    args = parser.parse_args()
    capture(args.directory, args.owner)
