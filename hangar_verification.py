"""Patch awareness without treating a successful download as a new timing sync."""
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from telemetry_ipc import read_shared_json, publish_json


def timing_key(schedule):
    fields={k:schedule.get(k) for k in ('anchor_ms','cycle_ms','segments')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()


def installed_build(game):
    data=read_shared_json(Path(game)/'build_manifest.id')['Data']
    match=re.search(r'(\d+\.\d+\.\d+)',str(data.get('Branch','')))
    if not match or not data.get('BuildId'):raise ValueError('Game build metadata unavailable')
    date=''
    try:date=datetime.strptime(str(data.get('BuildDateStamp','')),'%a %b %d %Y').date().isoformat()
    except ValueError:pass
    channel='PTU' if 'ptu' in str(data.get('Branch','')).lower() or Path(game).name.upper() in ('PTU','EPTU','TECH-PREVIEW') else 'LIVE'
    return dict(patch=match[1],channel=channel,fingerprint=str(data['BuildId'])+':'+str(data.get('RequestedP4ChangeNum','')),built_on=date)


class HangarVerification:
    def __init__(self,directory):
        self.path=Path(directory)/'executive_hangar_verification.json'
        try:
            self.state=read_shared_json(self.path)
            if not isinstance(self.state,dict):raise ValueError('Invalid verification state')
            for key in ('build','last_timing','baseline'):
                if key in self.state and not isinstance(self.state[key],str):raise ValueError('Invalid verification history')
            stamp=self.state.get('reset_at',0)
            if not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or stamp<0:raise ValueError('Invalid reset timestamp')
        except (OSError,ValueError):self.state={}

    def evaluate(self,build,schedule,now,fetched_at,refresh_error=False,reset_check=None):
        before=dict(self.state);state=self.state
        if build:
            previous=state.get('build')
            if previous and previous!=build['fingerprint']:
                state['pending']=True
                state['baseline']=state.get('last_timing') or (timing_key(schedule) if schedule else '')
            state['build']=build['fingerprint']
        key=timing_key(schedule) if schedule else ''
        patch_match=bool(build and schedule and build.get('channel','LIVE')=='LIVE' and re.match(r'^'+re.escape(build['patch'])+r'-LIVE(?:\.|$)',schedule.get('patch',''),re.I))
        date_match=bool(schedule and build and build.get('built_on') and schedule.get('source_modified','')>=build['built_on'])
        # Server build numbers can differ from the installed client build. Compare
        # patch labels, and invalidate an observed client-build change separately.
        recent=0<=now-fetched_at<=86400
        reset_ok=False
        if reset_check is not None:
            try:
                reset_ok=bool(reset_check.get('ok') and 0<=now-float(reset_check.get('checked_at',0))<=86400)
                stamp=float(reset_check.get('latest_reset_at',0))
                if 0<stamp<=now+86400:state['reset_at']=max(float(state.get('reset_at',0)),stamp)
            except (ValueError,TypeError,AttributeError):reset_ok=False
        after_reset=bool(schedule and schedule['anchor_ms']/1000>=state.get('reset_at',0))
        if state.get('pending') and key and key!=state.get('baseline') and patch_match and date_match and recent and not refresh_error and after_reset and reset_ok:
            state['pending']=False
        if key:state['last_timing']=key
        if schedule is None:reason='Waiting for a community timing sync'
        elif not build:reason='Game patch could not be verified'
        elif not patch_match or not date_match or state.get('pending'):reason='Timing unverified for this patch'
        elif not after_reset:reason='Timing unverified after maintenance'
        elif not reset_ok:reason='Server reset check unavailable'
        elif not recent or refresh_error:reason='Saved timing · live sync unavailable'
        else:reason='Community schedule · estimate'
        verified=reason=='Community schedule · estimate'
        if state!=before:publish_json(self.path,state)
        return dict(community_synced=verified,reason=reason,patch=build.get('patch','') if build else '',
                    needs_resync=not verified,build_changed=bool(build and before.get('build') and before.get('build')!=build['fingerprint']))
