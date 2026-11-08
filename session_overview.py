"""Local play-session recap from actual notifications and verified balances."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time


def stamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):
        return None


def play_events(line):
    match=re.search(r'^<([^>]+)>.*<SHUDEvent_OnNotification> Added notification "(.*?)" \[\d+\] to queue',line)
    if not match:return []
    at=stamp(match[1])
    if at is None:return []
    text=re.sub(r'<[^>]*>','',match[2]).strip().removesuffix(':').strip()
    event=None
    if text.startswith('Received Blueprint: '):
        event=dict(type='blueprint_received',name=re.sub(r'\[BP\]\s*','',text.split(': ',1)[1]).strip(),at=at)
    elif text.startswith('Contract Complete: '):
        title=re.sub(r'\s*\[(?:\d+ Rep|BP).*$', '',text.split(': ',1)[1]).strip()
        mission=re.search(r'MissionId: \[([^\]]+)\]',line)
        event=dict(type='contract_completed',name=title,at=at,mission_id=mission[1] if mission else '')
    else:
        refinery=re.fullmatch(r'(A|\d+) Refinery Work Orders? (?:has|have) been Completed at (.+)',text,re.I)
        if refinery:event=dict(type='refinery_completed',station=refinery[2].strip(),count=1 if refinery[1].lower()=='a' else int(refinery[1]),at=at)
    if not event:return []
    event['id']=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()[:24]
    return [event]


class SessionOverview:
    def __init__(self,directory,log):
        self.path=Path(directory)/'session_overview.json';self.log=Path(log)
        self.read_only=False;self.dirty=False
        try:
            self.data=json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('schema')!=1:raise ValueError('Unknown session history')
            for key in ('current','previous'):
                value=self.data.get(key)
                if value is not None and (not isinstance(value,dict) or not isinstance(value.get('blueprints'),dict) or not isinstance(value.get('contracts'),dict)):
                    raise ValueError('Invalid session history')
            if not isinstance(self.data.get('refinery'),dict):raise ValueError('Invalid refinery history')
        except FileNotFoundError:self.data=dict(schema=1,current=None,previous=None,balances=None,refinery={})
        except (OSError,ValueError):
            self.read_only=True;self.data=dict(schema=1,current=None,previous=None,balances=None,refinery={})
        self.rotate(True)

    def rotate(self,running,now=None):
        now=time.time() if now is None else now
        current=self.data.get('current')
        if not running:
            if current and not current.get('ended_at'):current['ended_at']=now;self.dirty=True
            return
        try:
            with self.log.open('rb') as stream:head=stream.read(8192).decode('utf-8',errors='replace')
            match=re.search(r'^<([^>]+)>',head,re.M);started=stamp(match[1]) if match else None
        except OSError:return
        if started is None:return
        key=hashlib.sha256((str(self.log.resolve())+'|'+str(started)).encode()).hexdigest()[:24]
        if current and current['id']==key:return
        if current:self.data['previous']=current
        self.data['current']=dict(id=key,started_at=started,ended_at=None,blueprints={},contracts={},rep_start=None,rep_latest=None)
        self.dirty=True

    def consume(self,event):
        kind=event.get('type');current=self.data.get('current')
        if kind=='refinery_completed':
            station=event['station'];old=self.data['refinery'].get(station)
            if not old or event['at']>old['at']:
                self.data['refinery'][station]=dict(event,dismissed=False);self.dirty=True
        if not current or event.get('at',0)<current['started_at']:return
        if kind=='blueprint_received':
            key=re.sub(r'\W+','',event['name']).casefold()
            if key not in current['blueprints']:current['blueprints'][key]=event;self.dirty=True
        elif kind=='contract_completed':
            key=event.get('mission_id')
            if not key or set(key.replace('-',''))=={'0'}:key=event['id']
            if key not in current['contracts']:current['contracts'][key]=event;self.dirty=True

    def reputation(self,snapshot):
        if not snapshot.get('own_character_verified') or not snapshot.get('complete') or snapshot.get('source')!='authenticated_reputation_service':return
        if not snapshot.get('character_key') or not isinstance(snapshot.get('records'),list):return
        records={}
        for record in snapshot['records']:
            if type(record.get('score')) not in (int,float) or not math.isfinite(record['score']):return
            key=str(record.get('entity',''))+'|'+str(record.get('scope',''))
            records[key]=dict(entity=record.get('entity',''),scope=record.get('scope',''),score=record['score'],standing_id=record.get('standing_id',''),standing=record.get('standing') or {})
        if not records:return
        value=dict(character=snapshot['character_key'],read_at=snapshot.get('read_at',0),records=records)
        if type(value['read_at']) not in (int,float) or not math.isfinite(value['read_at']):return
        previous=self.data.get('balances')
        if previous and previous['character']==value['character'] and previous['read_at']>=value['read_at']:return
        current=self.data.get('current')
        if current and value['read_at']>=current['started_at']:
            if not current.get('rep_start') or current['rep_start']['character']!=value['character']:
                # A balance from another play session cannot establish what was
                # earned in this one. Start at the first verified in-session read.
                current['rep_start']=value
            current['rep_latest']=value
        self.data['balances']=value;self.dirty=True

    def dismiss_refinery(self):
        for event in self.data['refinery'].values():event['dismissed']=True
        self.dirty=True

    def view(self,names=None,scopes=None):
        names=names or {};scopes=scopes or {}
        def run(value):
            if not value:return None
            changes=[];before=value.get('rep_start');after=value.get('rep_latest')
            if before and after and before['character']==after['character']:
                for key,record in after['records'].items():
                    old=before['records'].get(key)
                    if not old:continue
                    delta=record['score']-old['score']
                    if delta:
                        changes.append(dict(faction=names.get(record['entity'].rsplit(':',1)[-1],'Faction name pending'),
                            scope=scopes.get(record['scope'],{}).get('display_name','Reputation'),delta=delta,
                            before=old['score'],after=record['score'],standing_changed=old['standing_id']!=record['standing_id'],
                            standing=record['standing'].get('name','')))
            changes.sort(key=lambda r:-r['delta'])
            return dict(id=value['id'],started_at=value['started_at'],ended_at=value.get('ended_at'),
                blueprints=sorted(value['blueprints'].values(),key=lambda r:r['at']),contracts_completed=len(value['contracts']),
                reputation=changes,rep_baseline_at=before['read_at'] if before else None,
                rep_checked_at=after['read_at'] if after else None)
        refinery=sorted((e for e in self.data['refinery'].values() if not e.get('dismissed')),key=lambda e:-e['at'])
        notice=('Refinery finished · '+refinery[0]['station']+(' +'+str(len(refinery)-1)+' stations' if len(refinery)>1 else '')) if refinery else ''
        return dict(current=run(self.data.get('current')),previous=run(self.data.get('previous')),refinery=refinery,refinery_notice=notice,
                    history_warning=self.read_only,coverage='Logged blueprint grants and contract completions; reputation changes between verified balance reads.')

    def save(self):
        if self.dirty and not self.read_only:
            from telemetry_ipc import publish_json
            if publish_json(self.path,self.data):self.dirty=False
