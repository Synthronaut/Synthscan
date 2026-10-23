"""Owned, headless services for the native SynthScan UI. No Tk or game input."""
import argparse,ctypes,json,logging,os,time,sqlite3,subprocess,sys
from pathlib import Path
from telemetry_core import IncrementalGameLog,ShardHistory,SHARD_RE
from session_store import ServerLogManager,format_duration
from refinery_orders import atomic_json
from displayinfo_reader import translate_region
from network_source import read_network_ping
from frame_source import read_client_fps
from native_workspace_data import migrate,plan_rows
from app_lifecycle import game_process_ids
from mining_diary import MiningDiary
from rock_navigation import RockNavigation
from session_timeline import timeline,export_timeline,date_bounds
from telemetry_ipc import publish_json,read_shared_json
from interdiction_watch import InterdictionJournal

ROOT=Path(__file__).resolve().parent

def poll_latest(reader):
    """Publish only the end-of-file state, including after a process/log restart."""
    reader.poll()
    while True:
        try:size=Path(reader.log_path).stat().st_size
        except OSError:break
        if reader.last_pos>=size:break
        before=reader.last_pos;reader.poll()
        if reader.last_pos==before:break

class SessionService:
    def __init__(self,data_dir,game_log=None):
        self.directory=Path(data_dir);self.directory.mkdir(parents=True,exist_ok=True)
        self.reader=IncrementalGameLog(game_log) if game_log else IncrementalGameLog()
        # Establish the end-of-log state before publishing/recording a current
        # visit. Intermediate historical joins are not new server hops.
        poll_latest(self.reader)
        for event in self.reader.events:event['replayed']=True
        self.interdictions=InterdictionJournal(self.directory)
        self.history=ShardHistory(self.directory/'shard_history.json')
        self.sessions=ServerLogManager(self.directory/'server_log.json')
        self.plans=[];self.last_command='';self.seen_commands=set();self.note='';self.last_token=None
        self.frame_collector=None;self.frame_pid=None
        self.diary=MiningDiary(self.directory);self.diary_filters={};self.diary_result={}
        self.navigation=RockNavigation(self.directory);self.navigation_context={};self.game_pids=[]
        self.session_filters={};self.session_offset=0;self.last_game_running=None

    def diary_inbox(self):
        folder=self.directory/'diary_inbox'
        for path in sorted(folder.glob('*.json'))[:64]:
            try:
                if path.stat().st_size>1024*1024:raise ValueError('Oversized diary observation')
                self.diary.observe(json.loads(path.read_text(encoding='utf-8')))
                path.unlink()
            except (ValueError,KeyError,TypeError) as exc:
                logging.warning('Invalid diary observation %s: %s',path.name,exc)
                path.replace(path.with_suffix('.invalid'))

    def diary_commands(self):
        for path in sorted((self.directory/'diary_commands').glob('*.json'))[:64]:
            try:
                if path.stat().st_size>128*1024:raise ValueError('Oversized diary command')
                command=json.loads(path.read_text(encoding='utf-8'))
                if not str(command.get('action','')).startswith(('diary_','nav_','session_')):raise ValueError('Invalid queued command')
                self.command(command);path.unlink()
            except (ValueError,KeyError,TypeError,OSError) as exc:
                self.note=str(exc);path.replace(path.with_suffix('.invalid'))

    def tick(self,game_running=True,now=None):
        now=time.time() if now is None else now
        r=self.reader
        if game_running:poll_latest(r)
        else:
            was=r.connection_status!='game_closed';r.reset('game_closed',now,'process_observation' if self.last_game_running else 'absence_on_startup')
            if was:r.rewind()
        for e in r.drain_events():
            if e['type']=='left':self.sessions.end_session(e['at'],e.get('reason','disconnected'),e.get('time_source','observation'))
            elif e['type']=='joined':
                match=SHARD_RE.fullmatch(e['full_shard_id'])
                if match:
                    from telemetry_core import timestamp
                    known_closed=not game_running and any(s.get('full_shard_id')==e['full_shard_id'] and s.get('left_at') and abs((timestamp(s.get('joined_at')) or 0)-e['at'])<.002 for s in self.sessions.sessions)
                    if not known_closed:self.sessions.start_new_session(*match.groups(),joined_at=e['at'],ip=e.get('ip',''),time_source=e.get('time_source','observation'))
            elif e['type']=='location':self.sessions.record_location(e['name'],observed_at=e['at'])
            elif e['type']=='interdiction':self.interdictions.observe(e,now)
        token=r.session_token if game_running and r.connected else None
        if token:
            hop,_=self.history.observe_shard(r.region_raw,r.shard_id,full_shard_id=r.full_shard_id,join_token=token)
            name=self.history.get_known_name(r.region_raw,r.shard_id,r.full_shard_id) or 'Shard '+r.shard_id
        else:
            self.history.leave_current();self.sessions.end_session(reason='disconnected')
            hop='';name='Game closed' if not game_running else 'Main menu'
        ping=read_network_ping(r,now) if token else None
        frames=read_client_fps(now) if game_running else None
        metrics=[]
        if frames:metrics.append(f"Player {frames['client_fps']:.0f} FPS")
        if ping:metrics.append(f"Net RTT {ping['ping_ms']:.1f} ms")
        region=translate_region(r.region_raw) if token else ''
        identity=' · '.join(x for x in [name,region,hop] if x)
        summary=' · '.join(x for x in [name,region,hop,*metrics] if x)
        if token:self.sessions.confirm_seen(now)
        self.sessions.flush()
        sessions=self.sessions.get_sessions()
        session_view=timeline(self.sessions.sessions,now,self.session_filters,self.history,self.interdictions.entries)
        offset=max(0,min(self.session_offset,max(0,((session_view['count']-1)//100)*100)))
        session_rows=session_view.pop('rows')[offset:offset+100]
        session_view.update(offset=offset,limit=100)
        state=dict(schema=1,written_at=now,session_token=token,full_shard_id=r.full_shard_id if token else '',
                   summary=summary,identity=identity,region=region,shard_name=name,hop=hop,location=r.location_hint if token else '',
                   metrics=metrics,cooldowns=self.history.active_cooldowns(r.full_shard_id) if token else [],
                   sessions=sessions[:100],session_count=len(sessions),session_rows=session_rows,session_log=session_view,plans=self.plans,note=self.note,
                   storage_warning=self.history.read_only or self.sessions.read_only)
        self.diary_inbox()
        state['diary']=self.diary.view(**self.diary_filters)
        state['diary_result']=self.diary_result
        state['interdictions']=self.interdictions.view(token,now,r.full_shard_id,r.joined_at)
        state['hud_state']=dict(region_raw=r.region_raw,server_name='--',srv_id='--',metric_meta={})
        for key,value in [('ping_ms',ping),('client_fps',frames)]:
            if value:
                state['hud_state'][key]=value[key]
                state['hud_state']['metric_meta'][key]=dict(source=value['source'],observed_at=value['observed_at'])
        self.navigation_context=dict(session_token=token,full_shard_id=state['full_shard_id'],game_pids=list(self.game_pids))
        state['navigation']=self.navigation.tick(self.navigation_context)
        self.last_token=token
        self.last_game_running=bool(game_running)
        return state

    def command(self,command):
        key=str(command.get('id',''))
        if not key or key in self.seen_commands:return
        self.last_command=key;self.seen_commands.add(key)
        action=command.get('action')
        if action in ('session_view','session_export'):
            filters={k:str(command.get(k,'')) for k in ('query','region','date_from','date_to')}
            date_bounds(filters['date_from'],filters['date_to'])
            if action=='session_view':self.session_filters=filters;self.session_offset=max(0,int(command.get('offset',0)));self.note='Session timeline updated.'
            else:
                destination=Path(command['path']).resolve()
                if destination in {self.directory.resolve()/name for name in ('server_log.json','shard_history.json','session_state.json','native_settings.json','rock_bookmarks.json')}:raise ValueError('Choose an export filename outside the application data files')
                view=timeline(self.sessions.sessions,time.time(),filters,self.history,self.interdictions.entries)
                count=export_timeline(command['path'],view,command.get('format','csv'))
                self.note=f'Exported {count} shard visits to {command["path"]}'
        elif action and action.startswith('nav_'):
            self.navigation.command(command,self.navigation_context)
        elif action=='diary_view':
            self.diary_filters={k:command[k] for k in ['query','system','patch','mode','offset'] if k in command}
        elif action and action.startswith('diary_'):
            try:self.diary_result=dict(self.diary.execute(command),command_id=key)
            except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as exc:
                self.diary_result=dict(note=str(exc),command_id=key,error=True)
            self.note=self.diary_result['note']
        elif action=='plan':
            targets=[x.strip() for x in command.get('targets','').split(',') if x.strip()]
            self.plans=plan_rows(targets,command.get('system','All'),command.get('family','Ship'))
            self.note=f'{len(self.plans)} matching mining destinations.'
        elif action=='cooldown':
            if not self.last_token or command.get('session_token')!=self.last_token:raise ValueError('Join changed; choose the current shard again')
            self.history.mark_cooldown(command.get('label','')[:120],float(command.get('minutes',60)))
            self.note='Reminder saved for this shard.'
        elif action=='name':
            if not self.last_token or command.get('session_token')!=self.last_token:raise ValueError('Join changed; choose the current shard again')
            r=self.reader;name=command.get('name','').strip()[:80]
            if not name:raise ValueError('Enter a shard name')
            self.history.set_shard_name(r.region_raw,r.shard_id,name,r.full_shard_id)
            self.sessions.set_shard_name(r.shard_id,r.region_raw,name,r.full_shard_id)
            self.note='Shard name saved.'
        elif action=='session_note':
            if not self.sessions.set_session_note(command['session_id'],command.get('text','')[:5000]):raise ValueError('That session is no longer available')
            self.note='Session note saved.'
        elif action=='fabricator_file':
            from screen_readers import read_image,fabricator_candidates
            from fabricator_inbox import FabricatorInbox
            path=Path(command['path']).resolve()
            if path.parent!=self.directory.resolve() or path.suffix.lower()!='.png':raise ValueError('Invalid frame path')
            candidates=fabricator_candidates(read_image(str(path)))
            inbox=FabricatorInbox(self.directory/'fabricator_scan_inbox.json');inbox.add(candidates)
            self.note=f'{len(candidates)} blueprint candidates saved for review; ownership was not granted.'
        else:raise ValueError('Unknown workspace command')

    def close(self):
        self.navigation.close()
        if self.frame_collector:self.frame_collector.stop()
        self.sessions.flush()
        self.diary.close()

def owner_alive(pid):
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];api.OpenProcess.restype=ctypes.c_void_p
    api.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    api.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=api.OpenProcess(0x100000,False,pid)
    if not handle:return False
    try:return api.WaitForSingleObject(handle,0)==258
    finally:api.CloseHandle(handle)

def run(data_dir,owner):
    directory=Path(data_dir);directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=directory/'bridge.log',level=logging.INFO)
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    migrate(directory)
    service=SessionService(directory)
    service.navigation.start()
    from questing import Questing
    quests=Questing(directory,service.reader.log_path)
    from piracy_watch import PiracyReader
    piracy=PiracyReader(directory)
    top_hud=subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-B',str(ROOT/'native_session_hud.py'),'--owner',str(owner)],
                             cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        while owner_alive(owner):
            try:
                if json.loads((directory/'bridge_stop.json').read_text()).get('owner_pid')==owner:break
            except (OSError,ValueError):pass
            games=game_process_ids()
            service.game_pids=sorted(games)
            try:
                # Refresh the join before applying a command tagged by the UI.
                state=service.tick(bool(games))
                command=directory/'workspace_command.json'
                if command.exists():
                    try:service.command(json.loads(command.read_text(encoding='utf-8')))
                    except (ValueError,KeyError,TypeError,OSError) as exc:service.note=str(exc)
                quest_command=directory/'questing_command.json'
                if quest_command.exists():
                    value=read_shared_json(quest_command) or {}
                    if value.get('action')=='next' and value.get('owner_pid')==owner:
                        quests.next_contract()
                    quest_command.unlink(missing_ok=True)
                service.diary_commands()
                state=service.tick(bool(games));state['game_pids']=sorted(games);state['owner_pid']=owner
                inbox=directory/'fabricator_scan_inbox.json'
                state['review_revision']=inbox.stat().st_mtime if inbox.exists() else 0
                quest_settings=read_shared_json(directory/'native_settings.json') or {}
                pirate_mode=quest_settings.get('hud_mode')=='piracy'
                state['piracy_watch']=piracy.tick(pirate_mode,state.get('session_token'))
                pirate_command=directory/'piracy_command.json'
                if pirate_command.exists():
                    value=read_shared_json(pirate_command)
                    if value.get('owner_pid')==owner and 0<=time.time()-value.get('at',0)<15 and pirate_mode:
                        piracy.watch.command(value.get('action'),time.time())
                        state['piracy_watch']=piracy.watch.view(time.time(),pirate_mode)
                    pirate_command.unlink(missing_ok=True)
                from installation import RELEASE
                state['questing']=quests.tick(RELEASE or quest_settings.get('hud_mode')=='questing',bool(games))
                state['fps_permission_required']=bool(games and not read_client_fps(time.time()))
                if not publish_json(directory/'session_state.json',state):logging.warning('Session snapshot is temporarily locked; consumers will expire the old reading')
            except Exception:
                logging.exception('Native bridge tick failed')
            time.sleep(1)
    finally:
        piracy.close()
        quests.close()
        service.close()
        if top_hud.poll() is None:top_hud.terminate();top_hud.wait(timeout=5)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--owner',type=int,required=True)
    args=parser.parse_args();run(args.data_dir,args.owner)
