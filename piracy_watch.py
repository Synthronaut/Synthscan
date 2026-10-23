"""DisplayInfo observations for piracy planning; population is not a catch signal."""
import math
import threading
import time

FIELDS=('shard_pop','srv_pop','server_fps','ping_ms')

class PopulationWatch:
    def __init__(self, directory):
        self.token=None;self.points=[];self.metrics={};self.observed_at=0
        self.elapsed=0;self.started=None

    def session(self, token, now):
        if token==self.token:return
        self.token=token;self.points=[];self.metrics={};self.observed_at=0
        self.elapsed=0;self.started=None

    def observe(self, values, at, token, now):
        if not token or token!=self.token or not 0<=now-at<=4 or at<=self.observed_at:return False
        validated=set(values.get('_validated_fields',()))
        metrics={}
        for key in FIELDS:
            value=values.get(key)
            limit=100000 if key in ('shard_pop','srv_pop') else 240 if key=='server_fps' else 30000
            if key in validated and type(value) in (int,float) and math.isfinite(value) and 0<=value<=limit:
                if key not in ('shard_pop','srv_pop') or value==int(value):metrics[key]=value
        if metrics.get('srv_pop',0)>metrics.get('shard_pop',100000):
            metrics.pop('srv_pop',None);metrics.pop('shard_pop',None)
        self.metrics=metrics;self.observed_at=at
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
        fresh=bool(enabled and self.token and self.metrics and 0<=now-self.observed_at<=4)
        metrics=self.metrics if fresh else {}
        points=[p for p in self.points if now-900<=p['at']<=now]
        def delta(seconds):
            if 'shard_pop' not in metrics:return None
            candidates=[p for p in points if abs(p['at']-(now-seconds))<=20]
            if not candidates:return None
            return metrics['shard_pop']-min(candidates,key=lambda p:abs(p['at']-(now-seconds)))['value']
        elapsed=self.elapsed+(max(0,now-self.started) if self.started is not None else 0)
        return dict(metrics=metrics,observed_at=self.observed_at,age_s=max(0,now-self.observed_at) if self.observed_at else None,
                    fresh=fresh,points=points,delta_5m=delta(300),delta_15m=delta(900),
                    waiting_s=int(elapsed),waiting_active=self.started is not None,
                    source='DisplayInfo screen reader',status=f'DisplayInfo read live · {int(now-self.observed_at)}s ago' if metrics else 'Waiting for readable DisplayInfo',
                    timer_note='Manual timer · not snare detection')

class PiracyReader:
    def __init__(self, directory):
        self.watch=PopulationWatch(directory)
        self.context=(False,None);self.lock=threading.Lock();self.latest=None;self.error=''
        self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self._run,name='piracy-displayinfo',daemon=True)
        self.thread.start()

    def _run(self):
        capture=None;reader=None;retry=0
        try:
            while not self.stop_event.wait(.5):
                enabled,token=self.context
                if not enabled or not token:
                    if capture:capture.stop();capture=None
                    continue
                if time.monotonic()<retry:continue
                try:
                    from window_telemetry_capture import WindowTelemetryCapture,game_window_handle
                    hwnd=game_window_handle()
                    if not hwnd:
                        if capture:capture.stop();capture=None
                        continue
                    if capture and (capture.hwnd!=hwnd or capture.finished):capture.stop();capture=None
                    if not capture:
                        capture=WindowTelemetryCapture(lambda:self.context[1],interval=1)
                        capture.start(hwnd)
                    frame=capture.take_latest()
                    if frame:
                        image,at,frame_token=frame
                        if reader is None:
                            from validated_displayinfo import ValidatedDisplayInfoReader
                            reader=ValidatedDisplayInfoReader()
                        values=reader.parse_image(image)
                        with self.lock:self.latest=(values,at,frame_token);self.error=''
                except Exception as exc:
                    with self.lock:self.error='Screen reader unavailable ('+type(exc).__name__+')'
                    if capture:
                        try:capture.stop()
                        except Exception:pass
                        capture=None
                    retry=time.monotonic()+10
        finally:
            if capture:
                try:capture.stop()
                except Exception:pass

    def tick(self, enabled, token, now=None):
        now=time.time() if now is None else now
        self.watch.session(token,now)
        if not enabled and self.watch.started is not None:self.watch.command('toggle_wait',now)
        self.context=(enabled,token)
        with self.lock:latest,self.latest=self.latest,None;error=self.error
        if latest:self.watch.observe(*latest,now)
        view=self.watch.view(now,enabled)
        if error:view['status']=error
        if not token:view['status']='Join a shard to watch population'
        return view

    def close(self):
        self.stop_event.set();self.thread.join(timeout=2)
