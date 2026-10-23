"""Persistent refinery stock ledger, separate from cargo inventory.

Only repeated, agreeing terminal observations establish completion. Timers are
estimates. An unseen/vanished panel never establishes collection.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def utcstamp(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


class RefineryOrderBook:
    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).parent / 'refinery_orders.json')
        self.lock = threading.RLock()
        self.pending = {}
        self.data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else dict(schema=1, orders={})
        if self.data.get('schema') != 1 or not isinstance(self.data.get('orders'), dict):
            raise ValueError('Unrecognized refinery ledger; original file preserved')

    @staticmethod
    def validate(observation):
        if observation.get('status') not in ('processing', 'completed'):
            raise ValueError('Only processing/completed orders can be tracked')
        if not observation.get('station', '').strip() or type(observation.get('number')) is not int or observation['number'] < 0:
            raise ValueError('Station and order number are required')
        parts = observation.get('parts')
        if not parts:
            raise ValueError('No readable order materials')
        keys = set()
        for part in parts:
            q, amount = part.get('quality'), part.get('scu')
            if not part.get('material') or type(q) is not int or not 1 <= q <= 1000:
                raise ValueError('A measured material quality is required')
            if type(amount) not in (int, float) or not math.isfinite(amount) or not 0 < amount <= 1e6:
                raise ValueError('Invalid SCU quantity')
            key = (part['material'], q)
            if key in keys:
                raise ValueError('Ambiguous repeated material/quality rows')
            keys.add(key)
        remaining = observation.get('remaining_seconds')
        if remaining is not None and (type(remaining) is not int or not 0 <= remaining <= 365*86400):
            raise ValueError('Invalid remaining time')

    def observe(self, observation, now=None):
        self.validate(observation)
        now = time.time() if now is None else now
        key = hashlib.sha256((observation['station'].strip().casefold() + ':' + str(observation['number'])).encode()).hexdigest()[:24]
        evidence = dict(status=observation['status'], parts=sorted(observation['parts'], key=lambda p: (p['material'], p['quality'])))
        fingerprint = json.dumps(evidence, sort_keys=True)
        with self.lock:
            previous = self.pending.get(key)
            self.pending[key] = (fingerprint, now)
            if not previous or previous[0] != fingerprint or not 0 < now - previous[1] <= 20:
                return 'awaiting_confirmation'
            working = copy.deepcopy(self.data)
            orders = working['orders']
            order = orders.get(key)
            if order and order.get('collected_at'):
                return 'number_reused_review_required'
            if not order:
                order = orders[key] = dict(id=key, station=observation['station'].strip(), number=observation['number'],
                                           first_seen=utcstamp(now), parts=[], status='processing',
                                           source=observation.get('source', 'Terminal OCR'))
            known = {(p['material'], p['quality']): p for p in order['parts']}
            new_materials = bool(known) and any((p['material'], p['quality']) not in known for p in observation['parts'])
            # Never silently replace a recorded yield, nor treat a new run with
            # a reused number as another batch of the previous order.
            for part in observation['parts']:
                old = known.get((part['material'], part['quality']))
                if old and not math.isclose(old['scu'], part['scu'], abs_tol=.00005):
                    return 'yield_conflict_review_required'
            if order['status'] == 'completed' and observation['status'] == 'processing':
                return 'number_reused_review_required'
            for part in observation['parts']:
                if (part['material'], part['quality']) not in known:
                    order['parts'].append(copy.deepcopy(part))
            first_completion = observation['status'] == 'completed' and order['status'] != 'completed'
            order.update(last_seen=utcstamp(now), partial=observation.get('partial', True))
            if observation['status'] == 'completed':
                order['status'] = 'completed'
                order.setdefault('completed_at', utcstamp(now))
            remaining = observation.get('remaining_seconds')
            if remaining is not None and order['status'] != 'completed':
                order['estimated_due'] = now + remaining
            atomic_json(self.path, working)
            self.data = working
            return 'completed' if first_completion else 'materials_updated' if new_materials else 'updated'

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            rows = copy.deepcopy(list(self.data['orders'].values()))
        for row in rows:
            row['display_status'] = ('collected' if row.get('collected_at') else 'completed' if row['status'] == 'completed'
                                     else 'due — needs terminal confirmation' if row.get('estimated_due', math.inf) <= now else 'processing')
        return sorted(rows, key=lambda r: r['first_seen'], reverse=True)

    def mark_collected(self, order_id, now=None):
        """Explicit user observation only; does not fabricate a cargo location."""
        with self.lock:
            working = copy.deepcopy(self.data)
            order = working['orders'][order_id]
            if order['status'] != 'completed':
                raise ValueError('Completion has not been observed')
            order['collected_at'] = utcstamp(time.time() if now is None else now)
            atomic_json(self.path, working)
            self.data = working

    def archive_for_reuse(self, order_id):
        """Explicitly free a reused number while retaining its history."""
        with self.lock:
            working = copy.deepcopy(self.data)
            row = working['orders'].pop(order_id)
            if not row.get('collected_at'):
                raise ValueError('Mark the previous order collected before reusing its number')
            key = order_id + ':' + row['first_seen']
            row['id'] = key
            row['archived'] = True
            working['orders'][key] = row
            atomic_json(self.path, working)
            self.data = working
            self.pending.pop(order_id, None)
