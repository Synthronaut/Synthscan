"""Evidence-based interdiction reports. A crime report is not a universal snare sensor."""
import hashlib,json,math,re,time
from pathlib import Path

class InterdictionNotifications:
    START='<SHUDEvent_OnNotification> Added notification "Crime Committed: Unauthorized Interdiction'
    END=re.compile(r'^against ([^\r\n]{1,128}?):\s*"\s*\[(\d+)\]\s+to queue\.')
    def __init__(self):self.pending=None
    def reset(self):self.pending=None
    def feed(self,line,at,time_source):
        if self.START in line:
            self.pending=dict(at=at,time_source=time_source,lines=0)
            tail=line.split(self.START,1)[1].strip()
            if not tail:return None
        elif self.pending:
            self.pending['lines']+=1
            if self.pending['lines']>2 or abs(at-self.pending['at'])>.5:self.reset();return None
            tail=re.sub(r'^<[^>]+>\s*','',line).strip()
        else:return None
        match=self.END.match(tail)
        pending=self.pending;self.reset()
        if not match or pending['time_source']!='game_log_timestamp':return None
        target=''.join(c for c in match[1] if c.isprintable()).strip()
        if not target:return None
        return dict(at=pending['at'],target=target,notification_id=match[2],source='game_log_interdiction_crime_notification')

class InterdictionJournal:
    def __init__(self,directory):
        self.path=Path(directory)/'interdiction_log.json';self.entries=[];self.read_only=False;self.live={}
        if self.path.exists():
            try:
                x=json.loads(self.path.read_text(encoding='utf-8'))
                if x.get('schema')!=1 or not isinstance(x.get('entries'),list):raise ValueError('Unknown interdiction journal')
                for e in x['entries']:
                    if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not isinstance(e.get('target'),str) or not math.isfinite(float(e['at'])):raise ValueError('Invalid interdiction entry')
                    if not all(isinstance(e.get(k),str) for k in ('full_shard_id','joined_utc','observed_utc','session_token','notification_id','source')):raise ValueError('Incomplete interdiction entry')
                self.entries=x['entries']
            except (OSError,ValueError,TypeError,KeyError):self.read_only=True
        self.ids={e['id'] for e in self.entries}
    def observe(self,event,now):
        from telemetry_core import atomic_json,utc_iso
        identity='|'.join([event['full_shard_id'],utc_iso(event['at']),event['notification_id']])
        key=hashlib.sha256(identity.encode()).hexdigest()[:32]
        if key in self.ids:return
        row=dict(id=key,at=event['at'],observed_utc=utc_iso(event['at']),received_at=now,target=event['target'],
                 notification_id=event['notification_id'],full_shard_id=event['full_shard_id'],joined_utc=utc_iso(event['joined_at']),
                 session_token=event['session'],source=event['source'],replayed=bool(event.get('replayed')),
                 interpretation='Interdiction crime reported; snare versus dampener not independently established')
        self.entries.append(row);self.ids.add(key)
        if not self.read_only:
            try:atomic_json(self.path,dict(schema=1,entries=self.entries))
            except OSError:self.read_only=True
        if not row['replayed'] and -.5<=now-row['at']<=5:self.live[key]=row
    def view(self,token,now,full_shard_id='',joined_at=None):
        from telemetry_core import utc_iso
        self.live={k:e for k,e in self.live.items() if 0<=now-e['received_at']<=8 and -.5<=now-e['at']<=12}
        joined=utc_iso(joined_at) if joined_at is not None else None
        current=[e for e in self.entries if token and e['full_shard_id']==full_shard_id and e['joined_utc']==joined]
        return dict(count=len(self.entries),recent=list(reversed(self.entries[-20:])),
                    current=list(reversed(current[-4:])),current_count=len(current),
                    alerts=[e for e in self.live.values() if token and e['session_token']==token],read_only=self.read_only,
                    coverage='Logged English Unauthorized Interdiction notices only; unmonitored/friendly captures may not report')

def piracy_alerts_enabled(settings,game_visible):
    return bool(settings.get('hud_mode','mining')=='piracy' and settings.get('show_hud',True) and settings.get('snare_alerts',True) and game_visible)

class AlertGate:
    """Consume each live alert once; startup/reconnect never replays old sounds."""
    def __init__(self,started_at=None):self.started_at=time.time() if started_at is None else started_at;self.seen=set()
    def consume(self,snapshot,owner,now,enabled):
        fresh=snapshot.get('owner_pid')==owner and 0<=now-snapshot.get('written_at',0)<4
        out=[]
        for e in snapshot.get('interdictions',{}).get('alerts',[]):
            key=e.get('id')
            if not key or key in self.seen:continue
            self.seen.add(key)
            if fresh and enabled and not e.get('replayed') and e.get('session_token')==snapshot.get('session_token') and e.get('received_at',0)>=self.started_at and 0<=now-e.get('received_at',0)<=8 and -.5<=now-e.get('at',0)<=12:out.append(e)
        return out
