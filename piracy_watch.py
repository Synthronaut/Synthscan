"""DisplayInfo observations and persistent snare pull ledger for piracy & flight planning."""
import json
import math
from pathlib import Path
import time
import uuid

from flight_tracker import atomic_json

FIELDS=('shard_pop','srv_pop','server_fps','ping_ms')
LIVE_SECONDS=4
HOLD_SECONDS=10

class PopulationWatch:
    def __init__(self, directory):
        self.token=None;self.points=[];self.metrics={};self.field_at={};self.observed_at=0;self.last_frame_at=0
        self.elapsed=0;self.started=None

    def session(self, token, now):
        if token==self.token:return
        self.token=token;self.points=[];self.metrics={};self.field_at={};self.observed_at=0;self.last_frame_at=0
        self.elapsed=0;self.started=None

    def observe(self, values, at, token, now):
        if not token or token!=self.token or not 0<=now-at<=HOLD_SECONDS or at<=self.last_frame_at:return False
        validated=set(values.get('_validated_fields',()))
        metrics={}
        for key in FIELDS:
            value=values.get(key)
            limit=100000 if key in ('shard_pop','srv_pop') else 240 if key=='server_fps' else 30000
            if key in validated and type(value) in (int,float) and math.isfinite(value) and 0<=value<=limit:
                if key not in ('shard_pop','srv_pop') or value==int(value):metrics[key]=value
        if metrics.get('srv_pop',0)>metrics.get('shard_pop',100000):
            metrics.pop('srv_pop',None);metrics.pop('shard_pop',None)
        self.last_frame_at=at
        for key,value in metrics.items():self.metrics[key]=value;self.field_at[key]=at
        if metrics:self.observed_at=max(self.field_at.values())
        if 'shard_pop' in metrics and (not self.points or at-self.points[-1]['at']>=5):
            self.points.append(dict(at=at,value=metrics['shard_pop']))
        self.points=[p for p in self.points if now-900<=p['at']<=now][-181:]
        return True

    def command(self, action, now):
        if not self.token:return
        if action=='toggle_wait':
            if self.started is None:self.started=now
            else:self.elapsed+=max(0,now-self.started);self.started=None
        elif action=='reset_wait':self.elapsed=0;self.started=now if self.started is not None else None

    def view(self, now, enabled=True):
        ages={key:now-self.field_at[key] for key in self.metrics if key in self.field_at}
        metrics={key:value for key,value in self.metrics.items() if enabled and self.token and 0<=ages.get(key,float('inf'))<=HOLD_SECONDS}
        # Do not combine a newer, smaller shard count with an older local count.
        if metrics.get('srv_pop',0)>metrics.get('shard_pop',100000):
            metrics.pop('srv_pop',None);metrics.pop('shard_pop',None)
        held=[key for key in metrics if ages[key]>LIVE_SECONDS]
        fresh=bool(metrics and not held)
        points=[p for p in self.points if now-900<=p['at']<=now]
        def delta(seconds):
            if 'shard_pop' not in metrics or ages['shard_pop']>LIVE_SECONDS:return None
            candidates=[p for p in points if abs(p['at']-(now-seconds))<=20]
            if not candidates:return None
            return metrics['shard_pop']-min(candidates,key=lambda p:abs(p['at']-(now-seconds)))['value']
        elapsed=self.elapsed+(max(0,now-self.started) if self.started is not None else 0)
        oldest=max((ages[key] for key in metrics),default=0)
        status=('DisplayInfo read live · '+str(int(oldest))+'s ago') if fresh else ('Last read '+str(int(oldest))+'s ago · awaiting refresh') if metrics else 'Population needs readable DisplayInfo'
        return dict(metrics=metrics,field_ages={key:round(ages[key],2) for key in metrics},held_fields=held,observed_at=self.observed_at,age_s=max(0,now-self.observed_at) if self.observed_at else None,
                    fresh=fresh,points=points,delta_5m=delta(300),delta_15m=delta(900),
                    waiting_s=int(elapsed),waiting_active=self.started is not None,
                    source='DisplayInfo screen reader',status=status,
                    timer_note='Manual timer · not snare detection')

class PiracyReader:
    """Log-only piracy & flight telemetry support. No capture worker, OCR imports or screen metrics."""
    def __init__(self, directory, log_path=None):
        self.directory = Path(directory) if directory is not None else None
        self.log_file = (self.directory / 'piracy_log.json') if self.directory is not None else None
        self.watch = PopulationWatch(directory)
        from flight_tracker import FlightTracker
        self.flight = FlightTracker(directory, log_path)
        self.pulls = []
        self._load_pulls()

    def _load_pulls(self):
        if self.log_file and self.log_file.exists():
            try:
                data = json.loads(self.log_file.read_text(encoding='utf-8'))
                if data.get('schema') == 1 and isinstance(data.get('pulls'), list):
                    self.pulls = data['pulls'][-200:]
            except Exception:
                self.pulls = []

    def _save_pulls(self):
        if not self.log_file:
            return
        try:
            atomic_json(self.log_file, {'schema': 1, 'pulls': self.pulls[-200:]})
        except Exception:
            pass

    def command(self, action, payload=None, now=None):
        now = time.time() if now is None else now
        payload = payload or {}
        if action in ('toggle_wait', 'piracy_toggle_wait'):
            self.watch.command('toggle_wait', now)
        elif action in ('reset_wait', 'piracy_reset_wait'):
            self.watch.command('reset_wait', now)
        elif action == 'piracy_log_pull':
            outcome = str(payload.get('outcome') or 'catch').strip().lower()
            if outcome not in ('catch', 'escaped', 'dry', 'combat'):
                outcome = 'catch'
            try:
                value_uec = max(0, int(payload.get('value_uec') or 0))
            except (TypeError, ValueError):
                value_uec = 0
            entry = {
                'id': uuid.uuid4().hex[:12],
                'at': float(payload.get('observed_at') or now),
                'target': str(payload.get('target') or 'Unknown Vessel')[:80],
                'lane': str(payload.get('lane') or self.flight.active_route or 'Open Lane')[:80],
                'outcome': outcome,
                'value_uec': value_uec,
                'notes': str(payload.get('notes') or '')[:160],
            }
            self.pulls.append(entry)
            self.pulls = self.pulls[-200:]
            self._save_pulls()
        elif action == 'piracy_delete_pull':
            pull_id = str(payload.get('pull_id') or '')
            if pull_id:
                self.pulls = [p for p in self.pulls if p.get('id') != pull_id]
                self._save_pulls()

    def _pull_summary(self):
        total = len(self.pulls)
        catches = sum(1 for p in self.pulls if p.get('outcome') == 'catch')
        loot = sum(int(p.get('value_uec') or 0) for p in self.pulls)
        return {
            'pulls': list(reversed(self.pulls[-40:])),
            'pull_stats': {
                'total': total,
                'catches': catches,
                'hit_rate': int(round((catches / total) * 100)) if total > 0 else 0,
                'total_loot_uec': loot,
            },
        }

    def tick(self, enabled, token, now=None):
        now=time.time() if now is None else now
        self.watch.session(token,now)
        if not enabled and self.watch.started is not None:self.watch.command('toggle_wait',now)
        view=self.watch.view(now,False)
        view.update(metrics={},field_ages={},held_fields=[],points=[],delta_5m=None,delta_15m=None,
                    observed_at=0,age_s=None,fresh=False,source='Game logs and manual timer',
                    status='Log reports and manual wait timer' if token else 'Join a shard to use the wait timer')
        view['flight']=self.flight.tick(now)
        view.update(self._pull_summary())
        return view

    def close(self):
        pass
