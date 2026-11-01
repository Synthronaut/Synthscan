"""Shared PYAM cycle model; no game input, account data, or JavaScript execution.

Adapted from exec.xyxyll.com/app.js, MIT, Copyright (c) 2025 Xyxyll.
See third_party/executive_hangar/LICENSE and NOTICE.md.
"""
from datetime import datetime,timezone
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,math,re,time,urllib.request

SOURCE='https://exec.xyxyll.com/'
SCHEMA=1


def _ceil_fraction(value):return (value.numerator+value.denominator-1)//value.denominator

def _integer(text,name):
    match=re.search(r'\bconst\s+'+re.escape(name)+r'\s*=\s*(-?\d+)\s*;',text)
    if not match:raise ValueError('Unsupported timer definition: '+name)
    return int(match[1])


def parse_source(script,page='',now=None):
    """Read whitelisted literal data only. Remote code is never evaluated."""
    now=time.time() if now is None else now
    online=_integer(script,'DESIGN_ONLINE_MIN');offline=_integer(script,'DESIGN_OFFLINE_MIN');drift=_integer(script,'CYCLE_DRIFT_MS')
    if not 1<=online<=180 or not 1<=offline<=360 or abs(drift)>60000:raise ValueError('Unsupported timer durations')
    match=re.search(r"INITIAL_OPEN_TIME\s*=\s*new Date\(['\"]([^'\"]+)['\"]\)",script)
    if not match:raise ValueError('Timer anchor missing')
    anchor=datetime.fromisoformat(match[1].replace('Z','+00:00'))
    if anchor.utcoffset() is None:raise ValueError('Timer anchor requires a timezone')
    anchor_ms=round(anchor.timestamp()*1000)
    if not datetime(2024,1,1,tzinfo=timezone.utc).timestamp()*1000<=anchor_ms<=(now+86400)*1000:raise ValueError('Timer anchor outside supported dates')
    cycle=(online+offline)*60000+drift
    # JavaScript Math.round, including its positive half-up rule.
    active_group=(2*cycle*online+(online+offline))//(2*(online+offline));charging=cycle-active_group
    rows=re.findall(r"\{\s*until:\s*(\d+(?:\s*/\s*\d+)?)\s*,\s*colors:\s*\[([^\]]+)\]\s*\}",script)
    if len(rows)!=11:raise ValueError('Unsupported five-light timer model')
    segments=[]
    for group,(start,length,subset) in enumerate([(0,active_group,rows[:6]),(active_group,charging,rows[6:])]):
        previous=Fraction(0)
        for ratio,words in subset:
            until=Fraction(ratio.replace(' ',''));colors=re.findall(r"['\"](green|red|empty)['\"]",words)
            if len(colors)!=5 or not previous<until<=1:raise ValueError('Invalid light definition')
            phase='charging' if 'red' in colors else ('open' if 'green' in colors else 'reset')
            if (group==1)!=(phase=='charging'):raise ValueError('Unexpected light phases')
            end=start+_ceil_fraction(until*length)
            segments.append(dict(start_ms=segments[-1]['end_ms'] if segments else 0,end_ms=end,phase=phase,lights=colors))
            previous=until
        if previous!=1:raise ValueError('Incomplete timer phase')
    modified=re.search(r'@lastModified\s+(\d{4}-[A-Za-z]{3}-\d{2})',script)
    modified=datetime.strptime(modified[1],'%Y-%b-%d').date().isoformat() if modified else anchor.date().isoformat()
    version=re.search(r'@version\s+([\d.]+)',script)
    patch=re.search(r'Star Citizen Patch\s+([A-Za-z0-9.-]+)\s*\(Server Version\s+(\d+)\)',page)
    result=dict(schema=SCHEMA,source=SOURCE,anchor_ms=anchor_ms,cycle_ms=cycle,segments=segments,
                source_modified=modified,source_version=version[1] if version else '',
                source_sha256=hashlib.sha256(script.encode()).hexdigest(),
                patch=patch[1] if patch else '',server_build=patch[2] if patch else '')
    validate(result);return result


def validate(data):
    if not isinstance(data,dict):raise ValueError('Schedule must be an object')
    if data.get('schema')!=SCHEMA or data.get('source')!=SOURCE:raise ValueError('Unsupported hangar schedule')
    for key in ['anchor_ms','cycle_ms']:
        if not isinstance(data.get(key),int):raise ValueError('Non-integer timing')
    if not 60000<=data['cycle_ms']<=12*3600000:raise ValueError('Invalid cycle duration')
    segments=data.get('segments',[])
    if not isinstance(segments,list) or len(segments)!=11:raise ValueError('Invalid segment count')
    end=0
    for row in segments:
        if not isinstance(row,dict):raise ValueError('Invalid segment')
        if row.get('start_ms')!=end or not isinstance(row.get('end_ms'),int) or row['end_ms']<=end:raise ValueError('Non-contiguous timing')
        colors=row.get('lights',[])
        if not isinstance(colors,list) or len(colors)!=5 or any(c not in ['red','green','empty'] for c in colors):raise ValueError('Invalid lights')
        phase='charging' if 'red' in colors else ('open' if 'green' in colors else 'reset')
        if row.get('phase')!=phase:raise ValueError('Invalid phase colors')
        end=row['end_ms']
    if end!=data['cycle_ms'] or segments[0]['lights']!=['green']*5 or segments[-1]['lights']!=['green']*4+['red']:raise ValueError('Incomplete cycle')
    if [r['phase'] for r in segments]!=['open']*5+['reset']+['charging']*5:raise ValueError('Unsupported phase order')
    for key in ['source_modified','source_version','source_sha256','patch','server_build']:
        if not isinstance(data.get(key,''),str) or len(data.get(key,''))>80:raise ValueError('Invalid source metadata')
    return data


def project(schedule,now_ms):
    validate(schedule)
    if not math.isfinite(now_ms):raise ValueError('Invalid current time')
    now_ms=math.floor(now_ms);elapsed=now_ms-schedule['anchor_ms'];cycle=elapsed//schedule['cycle_ms'];position=elapsed%schedule['cycle_ms']
    start=schedule['anchor_ms']+cycle*schedule['cycle_ms']
    row=next(r for r in schedule['segments'] if position<r['end_ms'])
    closes=start+next(r['start_ms'] for r in schedule['segments'] if r['phase']=='reset')
    next_open=start+schedule['cycle_ms']
    phase=row['phase'];event=closes if phase=='open' else (row['end_ms']+start if phase=='reset' else next_open)
    return dict(phase=phase,lights=list(row['lights']),next_light_ms=start+row['end_ms'],next_open_ms=next_open,
                closes_ms=closes if phase=='open' else None,event_ms=event,remaining_ms=event-now_ms,
                light_remaining_ms=start+row['end_ms']-now_ms,now_ms=now_ms,
                source_modified=schedule.get('source_modified',''),patch=schedule.get('patch',''),estimated=True)


def countdown(milliseconds):
    total=max(0,math.ceil(milliseconds/1000));hours,rest=divmod(total,3600);minutes,seconds=divmod(rest,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}' if hours else f'{minutes:02}:{seconds:02}'


def fetch_schedule():
    def read(name):
        request=urllib.request.Request(SOURCE+name,headers={'User-Agent':'SynthScan-hangar-schedule/1.0'})
        with urllib.request.urlopen(request,timeout=8) as response:raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Timer response exceeds limit')
        return raw.decode('utf-8-sig')
    script=read('app.js');page=read('')
    return parse_source(script,page)


class HangarScheduleService:
    def __init__(self,directory,fetcher=fetch_schedule):
        self.path=Path(directory)/'executive_hangar_sync.json';self.fetcher=fetcher;self.future=None;self.pool=None
        self.schedule=None;self.note='';self.fetched_at=0;self.attempted_at=-math.inf;self.cached=True
        seed=Path(__file__).resolve().parent/'data/executive_hangar_schedule.json'
        for path in [self.path,seed]:
            try:
                from telemetry_ipc import read_shared_json
                data=read_shared_json(path)
                if not isinstance(data,dict):raise ValueError('Cache must be an object')
                candidate=validate(data.get('schedule',data));stamp=float(data.get('fetched_at',0))
                if not math.isfinite(stamp) or stamp<0:raise ValueError('Invalid cached timestamp')
                self.schedule=candidate;self.fetched_at=stamp;break
            except (OSError,ValueError,TypeError,KeyError):continue
    def tick(self,enabled,now=None):
        now=time.time() if now is None else now
        if self.future and self.future.done():
            try:
                self.schedule=validate(self.future.result());self.fetched_at=now;self.cached=False;self.note=''
                from telemetry_ipc import publish_json
                publish_json(self.path,dict(schedule=self.schedule,fetched_at=now))
            except Exception as exc:
                self.cached=True;self.note=type(exc).__name__
            self.future=None
        if enabled and self.future is None and not -60<=now-self.fetched_at<21600 and now-self.attempted_at>=300:
            self.attempted_at=now
            if self.pool is None:self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='hangar-schedule')
            self.future=self.pool.submit(self.fetcher)
        if not enabled or self.schedule is None:return None
        result=project(self.schedule,now*1000);result.update(cached=self.cached,refresh_error=bool(self.note))
        return result
    def close(self):
        if self.pool:self.pool.shutdown(wait=False,cancel_futures=True)
