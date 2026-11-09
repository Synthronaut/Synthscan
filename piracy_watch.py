"""DisplayInfo observations for piracy planning; population is not a catch signal."""
import math
import time

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
    """Log-only piracy support. No capture worker, OCR imports or screen metrics."""
    def __init__(self, directory):
        self.watch=PopulationWatch(directory)

    def tick(self, enabled, token, now=None):
        now=time.time() if now is None else now
        self.watch.session(token,now)
        if not enabled and self.watch.started is not None:self.watch.command('toggle_wait',now)
        view=self.watch.view(now,False)
        view.update(metrics={},field_ages={},held_fields=[],points=[],delta_5m=None,delta_15m=None,
                    observed_at=0,age_s=None,fresh=False,source='Game logs and manual timer',
                    status='Log reports and manual wait timer' if token else 'Join a shard to use the wait timer')
        return view

    def close(self):
        pass
