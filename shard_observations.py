"""Personal shard observation history, deliberately separate from server uptime."""
from datetime import datetime, timedelta, timezone
import math
from telemetry_core import SHARD_RE, timestamp, utc_iso

LOCAL=timezone(timedelta(hours=8))
EXPLANATION='Recorded visits are personal history, not shard creation or continuous server uptime. Restarts and resets are unverified.'


def valid_time(value,now):
    if isinstance(value,str):value=timestamp(value)
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<value<=now else None


def span_label(seconds):
    if seconds>=86400:return f'{int(seconds//86400)}d'
    if seconds>=3600:return f'{int(seconds//3600)}h'
    return '<1h'


def observation_index(sessions,history,now):
    """Use all retained visits and full identities; the recent dropdown is capped."""
    records={}
    def record(full):
        full=str(full or '').lower()
        if not SHARD_RE.fullmatch(full):return None
        return records.setdefault(full,dict(times=[],joins=[],visits=0))
    for full,entry in history.items():
        if not isinstance(entry,dict):continue
        target=record(full)
        if target is None:continue
        first=valid_time(entry.get('first_seen'),now)
        if first is not None:target['times'].append(first)
        visits=entry.get('visits',0)
        if isinstance(visits,int) and not isinstance(visits,bool):target['visits']=max(0,visits)
    for session in sessions:
        target=record(session.get('full_shard_id'))
        if target is None:continue
        joined=valid_time(session.get('joined_at'),now)
        if joined is not None:
            target['joins'].append(joined);target['times'].append(joined)
    result={}
    for full,entry in records.items():
        if not entry['times']:continue
        first=min(entry['times']);joins=[]
        for joined in sorted(entry['joins']):
            if not joins or joined-joins[-1]>=.002:joins.append(joined)
        visits=max(entry['visits'],len(joins));span=max(0,now-first)
        result[full]=dict(full_shard_id=full,first_recorded_at=utc_iso(first),
            first_recorded_local=datetime.fromtimestamp(first,LOCAL).strftime('%Y-%m-%d %H:%M:%S'),
            visits=visits,history_span_seconds=span,history_label='HISTORY '+span_label(span) if span>=3600 else '',
            visit_label='FIRST RECORDED VISIT' if visits==1 else f'RECORDED VISITS: {visits}',
            server_age_seconds=None,server_started_at=None,last_restart_at=None,
            basis='personal_recorded_visits',explanation=EXPLANATION)
    return result


def popup_context(snapshot):
    """Only show the current identity's history; never reuse it in the menu."""
    value=snapshot.get('shard_observation') or {}
    if not snapshot.get('session_token') or value.get('full_shard_id')!=snapshot.get('full_shard_id'):return []
    return ['This shard · '+str(value.get('visit_label','Recorded visits')),
            'First recorded: '+str(value.get('first_recorded_local','Unknown'))+' (UTC+8)',
            'Personal history only · server uptime / reset unknown']
