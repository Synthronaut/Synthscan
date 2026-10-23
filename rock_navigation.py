"""Experimental, player-operated rock return test. No game input or autopilot.

A bookmark uses its own capture epoch: predicting its return point needs a
rotation *difference*, not an assumed absolute planetary rotation epoch.
Reference body centers/axes/periods remain provisional until field checked.
"""
import hashlib,json,math,time,uuid,threading
from pathlib import Path
from position_capture import ArmedPosition,CoordinateClipboard
from refinery_orders import atomic_json

ROOT=Path(__file__).resolve().parent
REFERENCE=ROOT/'research/navigation_sources/reference/containers.json'

def vector(value):
    if not isinstance(value,(list,tuple)) or len(value)!=3:raise ValueError('Position needs three coordinates')
    out=[float(v) for v in value]
    if not all(math.isfinite(v) and abs(v)<1e16 for v in out):raise ValueError('Invalid coordinate')
    return out
def norm(v):return math.sqrt(sum(x*x for x in v))
def minus(a,b):return [x-y for x,y in zip(a,b)]
def plus(a,b):return [x+y for x,y in zip(a,b)]
def rotate_z(v,angle):
    c,s=math.cos(angle),math.sin(angle);return [c*v[0]-s*v[1],s*v[0]+c*v[1],v[2]]
def quat_rotate(v,q,inverse=False):
    q=[float(x) for x in q];length=norm(q)
    if length<1e-9:raise ValueError('Invalid body axis quaternion')
    w,x,y,z=[a/length for a in q]
    if inverse:x,y,z=-x,-y,-z
    return [(1-2*y*y-2*z*z)*v[0]+(2*x*y-2*z*w)*v[1]+(2*x*z+2*y*w)*v[2],
            (2*x*y+2*z*w)*v[0]+(1-2*x*x-2*z*z)*v[1]+(2*y*z-2*x*w)*v[2],
            (2*x*z-2*y*w)*v[0]+(2*y*z+2*x*w)*v[1]+(1-2*x*x-2*y*y)*v[2]]

def load_bodies(path=REFERENCE):
    rows=json.loads(Path(path).read_text(encoding='utf-8'));bodies={}
    for row in rows:
        if row.get('System') not in ('Stanton','Pyro','Nyx'):continue
        radius=float(row.get('BodyRadius') or 0);period=float(row.get('RotationSpeedX') or 0)*3600
        if row.get('Type')!='Planet' or radius<=0:continue
        body=dict(name=row['ObjectContainer'],system=row['System'],center=vector([row['XCoord'],row['YCoord'],row['ZCoord']]),
                  radius_m=radius,period_s=period,quaternion=[float(row['RotQuat'+a]) if row.get('RotQuat'+a) is not None else (1 if a=='W' else 0) for a in 'WXYZ'],
                  source='Community reference; current-build calibration required',source_url='https://starmap.space',
                  reference_note=row.get('Comment',''),axis_model='local +Z',spin_sign=1)
        body['id']=body['system']+'/'+body['name'];body['fingerprint']=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        bodies[body['id']]=body
    for system in ('Stanton','Pyro','Nyx'):
        key=system+'/Space test'
        bodies[key]=dict(id=key,name='Space / station test (fixed point)',system=system,center=[0,0,0],radius_m=0,
                         period_s=0,quaternion=[1,0,0,0],fingerprint='fixed-global-experiment-v1',space=True)
    return bodies

def near_body(xyz,body):
    radius=norm(minus(vector(xyz),body['center']))
    return body.get('space') or (radius>1 and abs(radius-body['radius_m'])<=max(200000,body['radius_m']*.7))

def rotated_target(mark,body,at):
    local=quat_rotate(minus(vector(mark['fix']['xyz_m']),body['center']),body['quaternion'],True)
    angle=0 if not body['period_s'] else (at-mark['fix']['received_at'])*2*math.pi/body['period_s']*body.get('spin_sign',1)
    return plus(body['center'],quat_rotate(rotate_z(local,angle),body['quaternion']))

def guidance(mark,body,fix,now=None):
    now=time.time() if now is None else now
    if mark['fix']['full_shard_id']!=fix['full_shard_id']:raise ValueError('Different shard: return to the recorded shard before navigating')
    if mark['model_fingerprint']!=body['fingerprint']:raise ValueError('Body reference changed; recalibration is required')
    if now-fix['received_at']>15 or fix['received_at']>now+1:raise ValueError('Position fix is stale; capture /showlocation again')
    checked=mark.get('rotation_check',{}).get('passed')
    if not checked and not mark.get('imported'):raise ValueError('Stationary check required before return guidance')
    actual=vector(fix['xyz_m']);current=quat_rotate(minus(actual,body['center']),body['quaternion'],True)
    radius=norm(current)
    if not near_body(actual,body):raise ValueError('Position is not near the selected body; frame/body is unverified')
    target_world=rotated_target(mark,body,fix['received_at']);target=quat_rotate(minus(target_world,body['center']),body['quaternion'],True)
    if body.get('space'):
        return dict(distance_m=norm(minus(target_world,actual)),delta_xyz_m=minus(target_world,actual),fix_age_s=max(0,now-fix['received_at']),
                    status=('Unverified shared estimate. ' if not checked else '')+'Fixed-point test only. No cockpit bearing available; station/rock frame remains experimental.')
    target_radius=norm(target)
    lat1=math.asin(max(-1,min(1,current[2]/radius)));lat2=math.asin(max(-1,min(1,target[2]/target_radius)))
    dlon=math.atan2(target[1],target[0])-math.atan2(current[1],current[0])
    angle=math.acos(max(-1,min(1,math.sin(lat1)*math.sin(lat2)+math.cos(lat1)*math.cos(lat2)*math.cos(dlon))))
    bearing=math.degrees(math.atan2(math.sin(dlon)*math.cos(lat2),math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(dlon)))%360
    return dict(distance_m=norm(minus(target_world,actual)),surface_m=angle*body['radius_m'],bearing_deg=bearing if angle>1e-8 else None,
                target_height_delta_m=target_radius-radius,fix_age_s=max(0,now-fix['received_at']),
                status='Unverified shared estimate: body model has not been checked locally' if not checked else 'Stationary rotation check passed · still verify rock visually')

class RockNavigation:
    def __init__(self,directory,clipboard_factory=CoordinateClipboard,clock=time.time,bodies=None):
        self.directory=Path(directory);self.path=self.directory/'rock_bookmarks.json';self.clock=clock
        try:self.bodies=load_bodies() if bodies is None else bodies
        except (OSError,ValueError,KeyError,TypeError):self.bodies={}
        self.clipboard_factory=clipboard_factory
        self.capture=None;self.role='';self.selected='';self.message='Choose a body, park beside the rock and arm a fresh position fix.';self.fix=None
        self.marks=[];self.read_only=False
        if self.path.exists():
            try:
                saved=json.loads(self.path.read_text(encoding='utf-8'))
                if saved.get('schema')!=1 or not isinstance(saved.get('marks'),list):raise ValueError('Unrecognized bookmark file')
                ids=set()
                for mark in saved['marks']:
                    self.validate_mark(mark)
                    if not isinstance(mark.get('id'),str) or not mark['id'] or mark['id'] in ids:raise ValueError('Invalid bookmark identity')
                    ids.add(mark['id'])
                self.marks=saved['marks']
                if self.marks:self.selected=self.marks[-1]['id'];self.message='Saved bookmark loaded. Start a new bookmark if you have moved; the stationary check must be performed at the marked point.'
            except (OSError,ValueError,KeyError,TypeError):self.read_only=True;self.message='Bookmark storage could not be read; original file preserved.'
        self.result={};self.revision=0;self.context={};self.lock=threading.RLock();self.stop=threading.Event();self.thread=None
    def start(self):
        def poll():
            while not self.stop.wait(.05):
                with self.lock:
                    if self.capture:
                        try:self.capture.poll(self.context)
                        except (OSError,ValueError):self.capture.status='clipboard_unavailable'
        self.thread=threading.Thread(target=poll,name='SynthScan armed coordinates',daemon=True);self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(2)
    def command(self,c,context):
        with self.lock:return self._command(c,context)
    def validate_mark(self,mark):
        if not isinstance(mark,dict) or mark.get('body_id') not in self.bodies:raise ValueError('Unknown bookmark body')
        if not isinstance(mark.get('name'),str) or not 1<=len(mark['name'])<=200:raise ValueError('Invalid bookmark name')
        fix=mark['fix'];vector(fix['xyz_m'])
        if not all(type(v) in (int,float) for v in fix['xyz_m']) or type(fix.get('received_at')) not in (int,float):raise ValueError('Coordinates and time must be numbers')
        if fix.get('frame')!='system_global_unverified' or fix.get('units')!='m' or fix.get('source')!='/showlocation clipboard':raise ValueError('Unsupported coordinate frame or source')
        if not near_body(fix['xyz_m'],self.bodies[mark['body_id']]):raise ValueError('Bookmark is not near the selected body')
        if not math.isfinite(float(fix['received_at'])) or float(fix['received_at'])<=0 or not isinstance(fix.get('full_shard_id'),str) or not 1<=len(fix['full_shard_id'])<=200:raise ValueError('Bookmark needs capture time and shard')
        if mark.get('model_fingerprint')!=self.bodies[mark['body_id']]['fingerprint']:raise ValueError('Bookmark body reference is incompatible')
        offset=float(mark.get('stand_off_m',0))
        if not math.isfinite(offset) or not 0<=offset<=100000:raise ValueError('Invalid rock stand-off distance')
    def save(self):
        if self.read_only:raise ValueError('Bookmark storage is unavailable; original file preserved')
        atomic_json(self.path,dict(schema=1,marks=self.marks));self.revision+=1
    def mark(self,key=None):
        key=self.selected if key is None else key
        entry=next((m for m in self.marks if m['id']==key),None)
        if entry is None:raise ValueError('Select a bookmark first')
        return entry
    def _command(self,c,context):
        action=c['action'];key=c.get('id','')
        try:
            if action in ('nav_import','nav_delete','nav_arm') and self.read_only:raise ValueError('Bookmark storage is unavailable; original file preserved')
            if action in ('nav_select','nav_delete','nav_import'):self.capture=None
            if action=='nav_select':self.mark(c['bookmark_id']);self.selected=c['bookmark_id'];self.fix=None;self.message='Bookmark selected. Capture a fresh position on its recorded shard.'
            elif action=='nav_cancel':self.capture=None;self.message='Position capture cancelled.'
            elif action=='nav_arm':
                if c.get('session_token')!=context.get('session_token'):raise ValueError('Session changed; wait for the current shard and arm again')
                body=self.bodies.get(c.get('body_id'))
                if not body:raise ValueError('Choose a body first')
                role=c.get('role','mark')
                if role not in ('mark','current','check'):raise ValueError('Invalid capture mode')
                if role!='mark':
                    self.mark();body=self.bodies[self.mark()['body_id']]
                    if self.mark()['fix']['full_shard_id']!=context.get('full_shard_id'):raise ValueError('This bookmark belongs to another shard')
                offset=float(c.get('stand_off_m') or 0)
                if not math.isfinite(offset) or not 0<=offset<=100000:raise ValueError('Stand-off must be 0–100000 meters')
                self.capture=ArmedPosition(self.clipboard_factory(),context,120,self.clock);self.role=role
                self.pending=dict(body_id=body['id'],name=str(c.get('name') or 'Rock bookmark')[:200],stand_off_m=offset,diary_id=str(c.get('diary_id',''))[:180])
                self.context=dict(context)
                self.message='Armed for 120 seconds. In game chat, type /showlocation and press Enter. No game input is automated.'
            elif action=='nav_import':
                path=Path(c['path'])
                if path.stat().st_size>256*1024:raise ValueError('Bookmark file is too large')
                payload=json.loads(path.read_text(encoding='utf-8'))
                if payload.get('format')!='SynthScan rock bookmark' or payload.get('version')!=1:raise ValueError('Unrecognized bookmark format')
                mark=payload['bookmark'];self.validate_mark(mark)
                mark={k:mark[k] for k in ('name','body_id','model_fingerprint','stand_off_m','fix')}
                mark['fix']={k:mark['fix'][k] for k in ('xyz_m','received_at','full_shard_id','frame','units','source')}
                # An imported claim is not a local field test.
                mark['id']=str(uuid.uuid4());mark['imported']=True;self.marks.append(mark);self.selected=mark['id'];self.save();self.fix=None;self.message='Bookmark imported. Fresh fixes provide an unverified shared estimate; check the shard and reference before flight.'
            elif action=='nav_export':
                mark=self.mark();self.validate_mark(mark)
                public={k:mark[k] for k in ['name','body_id','model_fingerprint','stand_off_m']}
                public['fix']={k:mark['fix'][k] for k in ['xyz_m','received_at','full_shard_id','frame','units','source']}
                atomic_json(Path(c['path']),dict(format='SynthScan rock bookmark',version=1,bookmark=public))
                self.message='Coordinate bookmark exported. It includes the exact position and shard you chose to share.'
            elif action=='nav_delete':
                self.mark();self.marks=[m for m in self.marks if m['id']!=self.selected];self.selected='';self.fix=None;self.save();self.message='Bookmark deleted.'
            else:raise ValueError('Unknown navigation action')
            self.result=dict(command_id=key,error=False,note=self.message)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            self.message=str(exc);self.result=dict(command_id=key,error=True,note=self.message)
    def tick(self,context):
        with self.lock:return self._tick(context)
    def _tick(self,context):
        self.context=dict(context)
        if self.capture:
            if self.capture.context.get('session_token')!=context.get('session_token') or set(self.capture.context.get('game_pids',[]))!=set(context.get('game_pids',[])):
                self.capture=None;self.message='Session changed. Arm a new capture on this shard.'
        if self.capture:
            fix=self.capture.poll(context)
            if self.capture.status=='captured':
                capture=self.capture;self.capture=None
                try:
                    body=self.bodies[self.pending['body_id']]
                    if not near_body(fix['xyz_m'],body):raise ValueError('Coordinates are not near that body. Check body/coordinate frame; bookmark not saved.')
                    if self.role=='mark':
                        if self.read_only:raise ValueError('Bookmark storage is unavailable')
                        mark=dict(id=str(uuid.uuid4()),**self.pending,fix=fix,model_fingerprint=body['fingerprint'])
                        self.marks.append(mark);self.selected=mark['id'];self.save();self.fix=fix
                        self.message='Position saved beside the rock. Stay parked and run the stationary check after at least 30 seconds.'
                    else:
                        mark=self.mark();self.fix=fix
                        if self.role=='check':
                            elapsed=fix['received_at']-mark['fix']['received_at']
                            if elapsed<30:raise ValueError('Stationary check needs at least 30 seconds since marking. Stay parked and arm it again.')
                            error=norm(minus(rotated_target(mark,body,fix['received_at']),fix['xyz_m']))
                            mark['rotation_check']=dict(at=fix['received_at'],elapsed_s=elapsed,error_m=error,passed=error<=25)
                            self.save();self.message=f'Stationary check error: {error:.1f} m. '+('Passed at this site.' if error<=25 else 'Not calibrated: check ship motion, body reference, axes and timing before leaving.')
                        else:self.message='Current position captured. Read the bearing and range; update again as you fly.'
                except (ValueError,KeyError,TypeError,OSError) as exc:self.message=str(exc)
            elif self.capture.status!='armed':self.message='Capture ended: '+self.capture.status+'. Arm it again when ready.';self.capture=None
        guide=None
        if self.fix and self.selected:
            try:guide=guidance(self.mark(),self.bodies[self.mark()['body_id']],self.fix,self.clock())
            except (ValueError,KeyError) as exc:guide=dict(unavailable=str(exc))
            if self.mark()['fix']['full_shard_id']!=context.get('full_shard_id'):guide=dict(unavailable='Different shard: this bookmark belongs to '+self.mark()['fix']['full_shard_id'])
        return dict(bodies=[dict(id=k,name=v['name'],system=v['system']) for k,v in sorted(self.bodies.items())],
                    marks=self.marks,selected=self.selected,message=self.message,armed=bool(self.capture),
                    capture_until=self.capture.until if self.capture else None,guidance=guide,result=self.result,revision=self.revision)
