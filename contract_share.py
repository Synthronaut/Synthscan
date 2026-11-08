"""Notification acceptance policy. No input or game access in this module."""
from datetime import datetime
import re
import time
import xml.etree.ElementTree as ET

UUID=r'[0-9a-fA-F-]{36}'
STAMP=re.compile(r'^<([^>]+)>')

def accept_blockers(held,accept_vk):
    """Movement/mouse activity is normal gameplay, not a reason to miss a share.

    Prevent a synthetic accept becoming Ctrl/Alt/Shift/Win + accept, or releasing
    an accept key the player is physically holding. No movement key is released.
    """
    protected={0x10,0x11,0x12,0x5b,0x5c,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5}
    if accept_vk:protected.add(accept_vk)
    return tuple(sorted(set(held)&protected))

class ContractSession:
    """Stale telemetry pauses input; only fresh identity changes reset the queue."""
    def __init__(self):self.token=None
    def update(self,snapshot,owner,now):
        valid=snapshot.get('owner_pid')==owner and 0<=now-snapshot.get('written_at',0)<3
        if not valid:return False,False
        current=snapshot.get('session_token')
        changed=current!=self.token;self.token=current
        return bool(current),changed

def acceptance_settings(raw):
    """Migrate the existing contract preference; social acceptance is opt-in."""
    return dict(contract=raw.get('enabled') is True,
                party=raw.get('party_enabled') is True, friend=raw.get('friend_enabled') is True)

def notification_kind(title):
    plain=re.sub(r'<[^>]+>','',title).strip()
    for prefix,kind in (('Contract Shared:','contract'),('Party Invite Received:','party'),('Friend Request:','friend')):
        if plain.startswith(prefix):return kind
    return None

class ContractQueue:
    ACTIVE_SECONDS=30
    RETRY_SECONDS=.75
    MAX_ATTEMPTS=40
    def __init__(self,enabled=None):
        self.enabled=dict(contract=True,party=False,friend=False) if enabled is None else dict(enabled)
        self.reset()
    def reset(self):
        self.pending={};self.active=None;self.push=[];self.attempted=set();self.accepted=set()
        self.message='Watching for incoming requests';self.last_attempt=None;self.inputs={}

    @staticmethod
    def prompt_key(candidate):
        return candidate['queue_id'],candidate['active_at'],candidate['mission']
    def feed(self,record):
        stamp=STAMP.match(record)
        if not stamp:return
        try:at=datetime.fromisoformat(stamp[1].replace('Z','+00:00')).timestamp()
        except ValueError:return
        push=re.search(r'<MissionShared> Received share push message: ownerId\[\d+\] - missionId\[('+UUID+r')\]',record)
        self.push=[p for p in self.push if 0<=at-p[1]<=2]
        if push:self.push.append((push[1].lower(),at))
        added=re.search(r'<SHUDEvent_OnNotification> Added notification "(.*?)" \[(\d+)\] to queue',record,re.S)
        if added:
            title,qid=added.groups()
            if title.startswith('Contract Shared:'):
                if len(self.push)==1:
                    mid=self.push[0][0];self.pending[qid]=dict(mission=mid,title=re.sub(r'<[^>]+>','',title).strip(),raw_title=title,queued_at=at,kind='contract')
                    self.message='Contract share queued; waiting for its prompt'
                else:self.message='Ambiguous share identity; manual acceptance required'
                self.push=[]
            kind=notification_kind(title)
            if kind in ('party','friend'):
                self.pending[qid]=dict(mission=f'{kind}:{qid}:{at}',title=re.sub(r'<[^>]+>','',title).strip(),raw_title=title,queued_at=at,kind=kind)
                self.message=kind.capitalize()+' request queued; waiting for its prompt'
            if title.startswith('Contract Accepted:'):
                m=re.search(r'MissionId: \[('+UUID+r')\]',record)
                if m and m[1]!='00000000-0000-0000-0000-000000000000':
                    self.accepted.add(m[1].lower())
                    if self.last_attempt and self.last_attempt['mission']==m[1].lower():self.message='Contract acceptance confirmed'
        update=re.search(r'<UpdateNotificationItem> Notification "(.*?)" \[(\d+)\], Action: (\w+)',record,re.S)
        if '<UpdateNotificationItem>' in record and not update:self.active=None
        if update:
            title,qid,action=update.groups()
            if action=='Next':
                previous=self.active
                self.active=None  # every notification, including party/friend/ordinary messages
                if qid in self.pending and title==self.pending[qid]['raw_title']:
                    # Duplicate state records must not restart the retry clock.
                    self.active=previous if previous and previous['queue_id']==qid and previous['raw_title']==title else dict(self.pending[qid],queue_id=qid,active_at=at)
                    self.message=self.active['kind'].capitalize()+' prompt active'
            elif action in ('StartFade','Remove'):
                if self.active and self.active['queue_id']==qid:
                    if self.active['mission'] not in self.attempted and self.active['mission'] not in self.accepted:
                        self.message='Prompt closed before an attempt; waiting for the next share'
                    self.active=None
                if action=='Remove':self.pending.pop(qid,None)
        # Bound stale queued messages without assuming the queue wait is short.
        self.pending={k:v for k,v in self.pending.items() if 0<=at-v['queued_at']<=1800}
    def candidate(self,now):
        a=self.active
        if not a or not self.enabled.get(a['kind'],False) or a['mission'] in self.accepted:return None
        # Never act on replay/backlog, a clock jump, or an old active prompt.
        if now<a['active_at'] or now>=a['active_at']+self.ACTIVE_SECONDS:return None
        attempts,last=self.inputs.get(self.prompt_key(a),(0,None))
        if attempts>=self.MAX_ATTEMPTS:return None
        if last is not None and now<last+self.RETRY_SECONDS:return None
        return dict(a)
    def attempted_once(self,candidate,now):
        if self.candidate(now)!=candidate:return False
        key=self.prompt_key(candidate);count,_=self.inputs.get(key,(0,None));self.inputs[key]=(count+1,now)
        self.attempted.add(candidate['mission']);self.last_attempt=dict(candidate,attempt_at=now)
        self.message='Accept key sent; awaiting confirmation, retrying while this request prompt stays active' if candidate['kind']=='contract' else 'Accept key sent; retrying while this request prompt stays active'
        return True
    def view(self,now):
        if self.active and now>=self.active['active_at']+self.ACTIVE_SECONDS and self.active['mission'] not in self.accepted:
            self.message='Request prompt timed out without confirmation; waiting for a fresh request'
        elif self.last_attempt and self.last_attempt['mission'] not in self.accepted and not self.active:
            self.message='Request prompt closed without acceptance confirmation; waiting for a fresh request' if self.last_attempt['kind']=='contract' else 'Request prompt closed; waiting for a fresh request'
        elif self.active and self.active['mission'] not in self.accepted and self.prompt_key(self.active) in self.inputs:
            self.message='Waiting for acceptance confirmation; retrying while this request prompt stays active' if self.active['kind']=='contract' else 'Accept key sent; retrying while this request prompt stays active'
        return dict(message=self.message,queued=len(self.pending),active=self.active,
                    attempts=sum(v[0] for v in self.inputs.values()),confirmed=len(self.accepted & self.attempted),
                    retry_interval_seconds=self.RETRY_SECONDS,prompt_timeout_seconds=self.ACTIVE_SECONDS)

class LogRecords:
    """Tail from EOF; assemble multiline records and never replay on rotation."""
    def __init__(self,path):self.path=path;self.offset=None;self.identity=None;self.buffer=''
    def read(self):
        stat=self.path.stat();identity=(stat.st_dev,stat.st_ino)
        if self.offset is None or identity!=self.identity or stat.st_size<self.offset:
            self.offset=stat.st_size;self.identity=identity;self.buffer='';return [],True
        with self.path.open('rb') as stream:
            stream.seek(self.offset);raw=stream.read(256*1024+1);self.offset=stream.tell()
        if len(raw)>256*1024:
            self.offset=stat.st_size;self.buffer='';return [],True
        self.buffer+=raw.decode('utf-8',errors='replace')
        # All relevant records terminate in the comms/team suffix, so a newline
        # closes the event without waiting for the next unrelated log message.
        lines=self.buffer.splitlines(keepends=True);records=[];current=''
        for line in lines:
            if not line.endswith(('\n','\r')):current+=line;continue
            if STAMP.match(line):
                if current:records.append(current)
                current=line
            else:current+=line
            if '[Team_CoreGameplayFeatures][Missions][Comms]' in current or '<MissionShared> Received share push message:' in current:
                records.append(current);current=''
        self.buffer=current
        if len(self.buffer)>65536:self.buffer='';return [],True
        return records,False

def accept_scan_code(profile):
    """Resolve the Notifications binding, never the separate legacy Invite binding."""
    key='lbracket'
    if profile.exists():
        root=ET.parse(profile).getroot()
        for mapping in root.findall('.//actionmap'):
            if mapping.get('name')!='default':continue
            for action in mapping.findall('action'):
                if action.get('name')!='notification_accept':continue
                bindings=[r.get('input','') for r in action.findall('rebind') if r.get('input','').startswith('kb1_')]
                if bindings:key=bindings[-1][4:]
    scans={'lbracket':0x1a,'rbracket':0x1b,'backslash':0x2b,'semicolon':0x27,'apostrophe':0x28,
           'comma':0x33,'period':0x34,'slash':0x35}
    scans.update(zip('qwertyuiop',range(0x10,0x1a)));scans.update(zip('asdfghjkl',range(0x1e,0x27)))
    scans.update(zip('zxcvbnm',range(0x2c,0x33)));scans.update(zip('1234567890',range(2,12)))
    if key not in scans:raise ValueError('Unsupported or disabled Notifications Accept binding; no key will be sent')
    return key,scans[key]
