"""Searchable shard-visit timeline. Raw UTC evidence stays separate from display."""
import csv,io,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from session_store import format_duration
from telemetry_core import timestamp,utc_iso
from refinery_orders import atomic_json

DISPLAY_ZONE=timezone(timedelta(hours=8),'Asia/Taipei')
ZONE_LABEL='Asia/Taipei · UTC+08:00'

def local_time(value):
    at=timestamp(value)
    return datetime.fromtimestamp(at,DISPLAY_ZONE).strftime('%Y-%m-%d %H:%M:%S') if at is not None else 'Unknown'

def date_bounds(date_from='',date_to=''):
    try:
        start=datetime.combine(date.fromisoformat(date_from),datetime.min.time(),DISPLAY_ZONE).timestamp() if date_from else None
        stop=(datetime.combine(date.fromisoformat(date_to),datetime.min.time(),DISPLAY_ZONE)+timedelta(days=1)).timestamp() if date_to else None
    except ValueError:raise ValueError('Enter dates as YYYY-MM-DD')
    if start is not None and stop is not None and start>=stop:raise ValueError('The end date must be on or after the start date')
    return start,stop

def time_source(session,key):
    source=session.get(key+'_time_source')
    if source=='game_log_timestamp':return 'Game log timestamp'
    if source=='next_join_bound':return 'Upper bound: another shard join was observed'
    if source=='process_observation':return 'Detected game exit; exact logout was not logged'
    if source=='absence_on_startup':return 'Game was already closed at startup; exact logout unknown'
    if source:return 'Observed by the app; exact event time unavailable'
    return 'Legacy record; timestamp source not retained'

def timeline(sessions,now,filters=None,history=None,interdictions=None):
    filters=filters or {};start,stop=date_bounds(filters.get('date_from',''),filters.get('date_to',''))
    query=filters.get('query','').strip().casefold();region=filters.get('region','').strip().casefold()
    ordered=sorted(sessions,key=lambda s:timestamp(s.get('joined_at')) or 0)
    counts={};previous={};rows=[];regions=set();next_joins={};following=None
    reports={}
    for e in interdictions or []:reports.setdefault((e['full_shard_id'],e['joined_utc']),[]).append(e)
    for index in range(len(ordered)-1,-1,-1):
        next_joins[index]=following
        observed=timestamp(ordered[index].get('joined_at'))
        if observed is not None:following=observed
    for index,session in enumerate(ordered):
        full=session.get('full_shard_id') or ''
        raw_region=session.get('region_raw','');regions.add(raw_region)
        identity=full or session['id'];counts[identity]=counts.get(identity,0)+1;visit=counts[identity];prior=previous.get(identity);previous[identity]=session
        joined=timestamp(session.get('joined_at'));left=timestamp(session.get('left_at'));active=bool(session.get('active'))
        confirmed=timestamp(session.get('last_confirmed_at'))
        # A missing logout remains unknown. A later visit bounds it without
        # silently turning that later login into an exact logout timestamp.
        following=next_joins[index]
        end=now if active else left if left is not None else following if following is not None else confirmed if confirmed is not None else joined
        if start is not None and (end is None or end<=start):continue
        if stop is not None and (joined is None or joined>=stop):continue
        if region not in ('','all') and region!=raw_region.casefold():continue
        duration=max(0,(now if active else left if left is not None else confirmed if confirmed is not None else joined or 0)-(joined or 0))
        status='Current session' if active else 'Exit unknown' if left is None else 'Ended' if session.get('left_time_source')=='game_log_timestamp' else 'Ended · see source'
        known=history.get_known_name(raw_region,session.get('shard_id',''),full) if history and full else None
        name=known or session.get('server_name') or ('Shard '+str(session.get('shard_id','?')))
        joined_label=local_time(session.get('joined_at'));left_label='Still playing' if active else local_time(session.get('left_at'))
        duration_label=format_duration(duration) if active or left is not None else ('At least '+format_duration(duration) if confirmed is not None else 'Unknown')
        if not active and left is not None:
            source=session.get('left_time_source')
            if source in ('next_join_bound','absence_on_startup'):left_label='By '+left_label;duration_label='Up to '+duration_label
            elif source in ('process_observation','observation'):left_label='Detected '+left_label;duration_label='About '+duration_label
        visit_label='First recorded visit' if visit==1 else 'Return #'+str(visit)
        details=f"{name}\nFull shard ID: {full or 'Not recorded'}\nRegion: {session.get('region_display',raw_region)} ({raw_region.upper()})\n\nTimes: {ZONE_LABEL}\nJoined: {joined_label}\nLeft: {left_label}\nDuration: {duration_label}\nStatus: {status}\n\nJoin UTC: {session.get('joined_at') or 'Unknown'}\nJoin source: {time_source(session,'joined')}\nLeave UTC: {session.get('left_at') or 'Not recorded'}\nLeave source: {time_source(session,'left') if left is not None else 'Unknown'}\nEnd reason: {session.get('end_reason') or 'Not recorded'}\n"
        if confirmed is not None:details+='Last confirmed joined: '+local_time(session['last_confirmed_at'])+'\n'
        if left is None and not active and following is not None:details+='Exit occurred no later than next recorded join: '+local_time(utc_iso(following))+' (upper bound, not an exact logout)\n'
        details+='\n'+visit_label+'\n'
        if prior:details+='Previous visit: '+local_time(prior.get('joined_at'))+' to '+local_time(prior.get('left_at'))+'\n'
        reminders=history.active_cooldowns(full) if history and full else []
        for reminder in reminders:details+='Active shard reminder: '+str(reminder.get('label',''))+'\n'
        details+='\nNamed locations observed:\n'
        for location in session.get('locations',[]):
            if isinstance(location,dict):details+=local_time(location.get('observed_at'))+' · '+str(location.get('name',''))+'\n'
            else:details+=str(location)+'\n'
        details+='\nNotes:\n'+str(session.get('notes',''))
        encounters=reports.get((full,session.get('joined_at')),[])
        if encounters:
            details+='\n\nLogged interdiction reports (not a count of ships still held):\n'
            for e in encounters:details+=local_time(e['observed_utc'])+' · '+e['target']+'\n'
        searchable=' '.join([name,full,raw_region,joined_label,left_label,details]).casefold()
        if query and not all(term in searchable for term in query.split()):continue
        rows.append(dict(id=session['id'],name=name,kind=raw_region.upper(),category=joined_label,detail=details,notes=session.get('notes',''),
                         joined_local=joined_label,left_local=left_label,full_shard_id=full,shard_id=session.get('shard_id','?'),
                         duration=duration_label,status=status,visit=visit_label,region=raw_region.upper(),joined_utc=session.get('joined_at'),left_utc=session.get('left_at'),
                         join_source=time_source(session,'joined'),leave_source=time_source(session,'left') if left is not None else 'Unknown',
                         last_confirmed_utc=session.get('last_confirmed_at'),end_reason=session.get('end_reason','')))
        rows[-1]['interdiction_reports']=len(encounters);rows[-1]['interdicted_handles']='; '.join(e['target'] for e in encounters)
    return dict(rows=list(reversed(rows)),count=len(rows),total=len(sessions),regions=sorted(x for x in regions if x),
                timezone=ZONE_LABEL,filters=filters)

def export_timeline(destination,view,kind):
    path=Path(destination)
    if kind=='json':
        atomic_json(path,dict(format='SynthScan session timeline',version=1,timezone=ZONE_LABEL,filters=view['filters'],visits=view['rows']))
    elif kind=='csv':
        fields=['joined_local','left_local','duration','status','region','full_shard_id','name','visit','joined_utc','left_utc','join_source','leave_source','last_confirmed_utc','end_reason','interdiction_reports','interdicted_handles','notes']
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=['display_timezone']+fields,extrasaction='ignore');writer.writeheader()
        for row in view['rows']:
            # Spreadsheet applications must not interpret player notes as formulas.
            safe={k:("'"+str(row.get(k,'')) if str(row.get(k,'')).lstrip().startswith(('=','+','-','@','\t','\r')) else row.get(k,'')) for k in fields}
            writer.writerow(dict(display_timezone=ZONE_LABEL,**safe))
        temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(stream.getvalue(),encoding='utf-8-sig',newline='');temporary.replace(path)
    else:raise ValueError('Choose CSV or JSON export')
    return len(view['rows'])
