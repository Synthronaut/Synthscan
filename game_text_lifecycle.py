"""Journaled game-text changes. Recovery copies stay in the Windows profile."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from installation import PROFILE,ROOT
from localization_lock import localization_lock

INI='Data/Localization/english/global.ini'
CFG='user.cfg'
ALLOWED=(INI,CFG)
MARKERS=(b'bedrock_game_texts=',b'<EM4>BLUEPRINTS</EM4>')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def atomic(path,raw,on_temp=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.synthscan-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            if on_temp:on_temp(Path(name),os.fstat(stream.fileno()).st_ino)
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)
def load(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:return {} if default is None else default
def save(path,value):atomic(path,(json.dumps(value,indent=2)+'\n').encode())

def read_dacl(path):
    """Read only the discretionary ACL, never credentials or SACL privileges."""
    import ctypes as c
    from ctypes import wintypes as w
    adv=c.WinDLL('advapi32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
    adv.GetNamedSecurityInfoW.argtypes=[w.LPWSTR,w.DWORD,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.POINTER(c.c_void_p)]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes=[c.c_void_p,w.DWORD,w.DWORD,c.POINTER(w.LPWSTR),c.c_void_p]
    kernel.LocalFree.argtypes=[c.c_void_p]
    descriptor=c.c_void_p();text=w.LPWSTR()
    error=adv.GetNamedSecurityInfoW(str(path),1,4,None,None,None,None,c.byref(descriptor))
    if error:raise c.WinError(error)
    try:
        if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor,1,4,c.byref(text),None):raise c.WinError(c.get_last_error())
        try:return text.value
        finally:kernel.LocalFree(c.cast(text,c.c_void_p))
    finally:kernel.LocalFree(descriptor)

def write_dacl(path,sddl):
    import ctypes as c
    from ctypes import wintypes as w
    adv=c.WinDLL('advapi32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.c_void_p]
    adv.SetFileSecurityW.argtypes=[w.LPCWSTR,w.DWORD,c.c_void_p];kernel.LocalFree.argtypes=[c.c_void_p]
    descriptor=c.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,c.byref(descriptor),None):raise c.WinError(c.get_last_error())
    try:
        flags=4|(0x80000000 if 'P' in sddl.partition(':')[2].partition('(')[0] else 0x20000000)
        if not adv.SetFileSecurityW(str(path),flags,descriptor):raise c.WinError(c.get_last_error())
    finally:kernel.LocalFree(descriptor)
def enabled(game,profile=PROFILE):
    from installation import ISOLATED_TEST
    if ISOLATED_TEST:return False
    return Manager(game,profile).read().get('enabled',True)

class Manager:
    def __init__(self,game,profile=PROFILE):
        self.game=Path(game).resolve();self.profile=Path(profile).resolve()
        key=digest(os.path.normcase(str(self.game)).encode())
        self.folder=self.profile/'game_text'/key;self.journal=self.folder/'journal.json'
    def target(self,name):
        from installation import ISOLATED_TEST
        if ISOLATED_TEST:raise ValueError('Isolated installer test: changes to game text are disabled. Your regular SynthScan text is protected.')
        if name not in ALLOWED:raise ValueError('Unmanaged game-text target')
        path=self.game/name
        if path.resolve()!=path or not path.resolve().is_relative_to(self.game) or (path.exists() and path.stat().st_nlink>1):raise ValueError('Linked game text cannot be changed automatically')
        return path
    def recovery(self,name):
        path=self.folder/name
        if Path(name).name!=name or path.resolve()!=path:raise ValueError('Invalid recovery path')
        return path
    def read(self):
        value=load(self.journal)
        if value and (value.get('schema')!=1 or value.get('game')!=str(self.game)):raise ValueError('Invalid game-text ownership journal')
        return value
    def store(self,state):save(self.journal,state)
    def state(self):return self.read() or dict(schema=1,game=str(self.game),enabled=True,files={},directories=[],permissions={},phase='active')
    def set_enabled(self,value):
        from installation import ISOLATED_TEST
        if ISOLATED_TEST and value:raise ValueError('Game-text changes are disabled in the isolated installer test')
        with localization_lock(self.game/INI):
            state=self.state()
            if value and state.get('phase')=='conflict':raise ValueError('Resolve the recorded cleanup conflicts before enabling SynthStrings again')
            state['enabled']=bool(value);self.store(state)
    def capture(self,state,name):
        path=self.target(name)
        if name in state['files']:return state['files'][name]
        raw=path.read_bytes() if path.exists() else None
        identifier=uuid.uuid4().hex
        entry=dict(existed=raw is not None,original_sha256=digest(raw) if raw is not None else None,last_sha256=digest(raw) if raw is not None else None,touched=False)
        if raw is not None:
            entry['original']=identifier+'-original.bin';atomic(self.folder/entry['original'],raw)
            entry['legacy']=name==INI and any(mark in raw for mark in MARKERS)
            if os.name=='nt' and name not in state['permissions']:
                acl=read_dacl(path);state['permissions'][name]=dict(original=acl,applied=acl)
        state['files'][name]=entry
        for folder in list(reversed(path.parent.parents)) + [path.parent]:
            if folder!=self.game and folder.is_relative_to(self.game) and not folder.exists():
                relative=folder.relative_to(self.game).as_posix()
                if relative not in state['directories']:state['directories'].append(relative)
        self.store(state);return entry
    def reconcile(self,state,name):
        entry=state['files'][name]
        if entry.get('pending_suspend'):
            path=self.target(name);current=digest(path.read_bytes()) if path.exists() else None
            if current is None:
                entry.update(last_sha256=None,suspended=True,touched=True)
                if entry.get('pending_replace_original'):entry['patch_quarantined']=True
            elif current!=entry['pending_suspend']:raise ValueError('Game text changed during interrupted quarantine')
            entry.pop('pending_suspend',None);entry.pop('pending_replace_original',None);self.store(state)
        pending=entry.get('pending_sha256')
        if pending is None:return
        path=self.target(name);current=digest(path.read_bytes()) if path.exists() else None
        if current==pending:
            entry.update(last_sha256=pending,touched=True,written=entry.get('pending_written',entry.get('written')),suspended=False,restored=False)
            if entry.get('pending_source'):entry['source']=entry['pending_source']
        elif current!=entry.get('last_sha256'):raise ValueError('Game text changed during an interrupted update')
        temporary=entry.get('pending_temp')
        if temporary:
            name=temporary['name'];leftover=path.parent/name
            if Path(name).name!=name or not re.fullmatch(r'\.synthscan-[\w-]+\.tmp',name):raise ValueError('Invalid temporary recovery path')
            if leftover.exists():
                stat=leftover.stat()
                if leftover.resolve()!=leftover or stat.st_nlink!=1 or stat.st_ino!=temporary['file_id']:raise ValueError('Temporary recovery file changed ownership')
                leftover.unlink()
        entry.pop('pending_temp',None)
        entry.pop('pending_sha256',None);entry.pop('pending_written',None);entry.pop('pending_source',None);self.store(state)
    def write(self,name,raw,source=None):
        with localization_lock(self.game/INI):
            state=self.state()
            if not state.get('enabled',True):raise ValueError('SynthStrings is disabled for this game channel')
            if state.get('phase')=='conflict':raise ValueError('Resolve the recorded cleanup conflicts before rewriting game text')
            if state.get('phase')=='restored':
                state.update(files={},directories=[],permissions={},phase='active');self.store(state)
            entry=self.capture(state,name);self.reconcile(state,name);path=self.target(name)
            if name==INI:
                expected=source or entry.get('source')
                if entry.get('suspended') and not source:raise ValueError('SynthStrings is paused until fresh game text is verified')
                if expected:
                    from synthstrings_guard import snapshot
                    if snapshot(self.game)['fingerprint']!=expected['fingerprint']:raise ValueError('Game build changed before localization could be committed')
            before=path.read_bytes() if path.exists() else None
            if before==raw:
                if source:entry['source']=source;self.store(state)
                return False
            # Capture the exact version being replaced before committing the change.
            if entry.get('last_sha256')!=(digest(before) if before is not None else None):
                raise ValueError('Game text changed outside SynthScan; review it before rewriting')
            after_name=digest(raw)+'-written.bin';atomic(self.folder/after_name,raw)
            entry.update(pending_sha256=digest(raw),pending_written=after_name);self.store(state)
            if source:entry['pending_source']=source;self.store(state)
            def record_temp(path,file_id):
                entry['pending_temp']=dict(name=path.name,file_id=file_id);self.store(state)
            atomic(path,raw,on_temp=record_temp)
            permission=state.get('permissions',{}).get(name)
            if permission:permission['applied']=read_dacl(path)
            entry.update(last_sha256=digest(raw),touched=True,written=after_name,suspended=False,restored=False)
            if source:entry['source']=source
            entry.pop('pending_sha256',None);entry.pop('pending_written',None);entry.pop('pending_temp',None);entry.pop('pending_source',None);self.store(state)
            referenced={e.get(key) for e in state['files'].values() for key in ('written','pending_written')}
            for old in self.folder.glob('*-written.bin'):
                if re.fullmatch(r'[0-9a-f]{64}-written.bin',old.name) and old.name not in referenced:old.unlink(missing_ok=True)
            return True
    def suspend(self,affected=(),replace_sha256=None):
        """Quarantine only our complete generated pack; retain the on preference.

        Never restore an old pre-patch full pack, delete a foreign pack or undo
        another program's edits. The archive and journal stay in AppData.
        """
        with localization_lock(self.game/INI):
            state=self.state();path=self.target(INI)
            if INI in state['files']:self.reconcile(state,INI)
            if not path.exists():
                entry=state['files'].get(INI)
                if entry and (replace_sha256 is not None or entry.get('source')):
                    entry.update(last_sha256=None,suspended=True,touched=True)
                    if replace_sha256 is not None:entry['patch_quarantined']=True
                    self.store(state)
                return False
            raw=path.read_bytes()
            # A whole generated pack has the explicit final ownership key.
            # A blueprint heading alone does not establish exclusive ownership.
            if replace_sha256 is not None and digest(raw)!=replace_sha256:raise ValueError('The language pack changed after you chose to replace it; original preserved')
            if replace_sha256 is None and not re.search(rb'(?m)^bedrock_game_texts=',raw.lstrip(b'\xef\xbb\xbf')):return False
            entry=state['files'].get(INI)
            if entry and entry.get('last_sha256')!=digest(raw) and replace_sha256 is None:return False
            entry=self.capture(state,INI)
            saved=self.backup(INI,raw,'patch-quarantine')
            if saved.read_bytes()!=raw or path.read_bytes()!=raw:raise ValueError('Game text changed during quarantine; original preserved')
            entry['pending_suspend']=digest(raw)
            entry['suspended_game_pids']=sorted(set(entry.get('suspended_game_pids',[]))|set(affected))
            entry['pending_replace_original']=bool(entry.get('legacy') or replace_sha256 is not None)
            self.store(state)
            path.unlink()
            entry.update(last_sha256=None,suspended=True,touched=True)
            if entry.get('pending_replace_original'):entry['patch_quarantined']=True
            entry.pop('pending_suspend',None);entry.pop('pending_replace_original',None);self.store(state)
            return True
    def backup(self,name,raw,kind='recovery'):
        target=self.folder/(time.strftime('%Y%m%d_%H%M%S')+'-'+uuid.uuid4().hex+'-'+kind+'.bin');atomic(target,raw);return target
    def restore(self,archive_legacy=False):
        from installation import ISOLATED_TEST
        if ISOLATED_TEST:return dict(restored=[],preserved=[],conflicts=[],legacy=[],permissions_pending=[],isolated_test=True)
        with localization_lock(self.game/INI,timeout_ms=330000):
            state=self.state();state['enabled']=False;self.store(state);result=dict(restored=[],preserved=[],conflicts=[],legacy=[],permissions_pending=[])
            for name,entry in state['files'].items():
                try:
                    self.reconcile(state,name);path=self.target(name)
                    if entry.get('restored'):continue
                    current=path.read_bytes() if path.exists() else None
                    if entry.get('suspended') and current is None:
                        entry['restored']=True;result['preserved'].append(name);continue
                    original=self.recovery(entry['original']).read_bytes() if entry.get('existed') else None
                    if original is not None and digest(original)!=entry['original_sha256']:raise ValueError('Original recovery copy failed verification')
                    if entry.get('patch_quarantined'):original=None
                    if entry.get('legacy') and not entry.get('patch_quarantined'):
                        result['legacy'].append(name)
                        if not archive_legacy:result['conflicts'].append(name);continue
                        if current is None:entry['restored']=True;continue
                        if name!=INI or not any(mark in current for mark in MARKERS):result['conflicts'].append(name);continue
                        self.backup(name,current,'legacy-archive');path.unlink();entry['restored']=True;result['restored'].append(name);continue
                    if not entry.get('touched'):continue
                    expected=entry.get('last_sha256')
                    if (digest(current) if current is not None else None)==expected:
                        if original is None:path.unlink(missing_ok=True)
                        else:atomic(path,original)
                        entry['restored']=True;result['restored'].append(name)
                    elif current is None:
                        result['preserved'].append(name);entry['restored']=True
                    elif name==CFG:
                        # Only remove our added language line; keep later user settings.
                        previous=original or b''
                        if not re.search(rb'^\s*g_language\s*=',previous,re.I|re.M):
                            updated=re.sub(rb'^[ \t]*g_language[ \t]*=[ \t]*[\"\x27]?english[\"\x27]?[ \t]*(?:\r?\n|$)',b'',current,flags=re.I|re.M)
                            if updated!=current:
                                self.backup(name,current)
                                if not updated and original is None:path.unlink()
                                else:atomic(path,updated)
                        entry['restored']=True;result['preserved'].append(name)
                    elif original is not None and entry.get('written'):
                        written=self.recovery(entry['written']).read_bytes()
                        if digest(written)!=entry['last_sha256']:raise ValueError('Written recovery copy failed verification')
                        restored,conflicts=restore_lines(original,written,current)
                        if restored!=current:self.backup(name,current);atomic(path,restored)
                        if conflicts:result['conflicts'].append(name);entry['conflicted_keys']=conflicts
                        else:entry['restored']=True;result['preserved'].append(name)
                    else:result['conflicts'].append(name)
                except (OSError,ValueError) as error:result['conflicts'].append(name);entry['cleanup_error']=str(error)
                self.store(state)
            if not state['files']:
                path=self.target(INI)
                if path.exists() and any(mark in path.read_bytes() for mark in MARKERS):
                    result['legacy'].append(INI)
                    if archive_legacy:self.backup(INI,path.read_bytes(),'legacy-archive');path.unlink();result['restored'].append(INI)
                    else:result['conflicts'].append(INI)
            for relative,entry in state.get('permissions',{}).items():
                path=self.game/relative
                try:
                    if path.resolve()!=path or not path.is_relative_to(self.game):raise ValueError('Linked permission target')
                    if not path.exists():continue
                    current=read_dacl(path)
                    if current==entry['original']:continue
                    if current!=entry.get('applied'):raise ValueError('Permissions changed outside SynthScan')
                    write_dacl(path,entry['original'])
                except (OSError,ValueError) as error:
                    result['permissions_pending'].append(relative);entry['cleanup_error']=str(error)
            for relative in sorted(state.get('directories',[]),key=lambda value:len(Path(value).parts),reverse=True):
                directory=self.game/relative
                if directory.resolve()!=directory or not directory.is_relative_to(self.game):continue
                try:directory.rmdir()
                except OSError:pass
            state['phase']='conflict' if result['conflicts'] or result['permissions_pending'] else 'restored';state['cleanup']=result;self.store(state);return result

def restore_lines(original,written,current):
    """Undo unchanged owned INI lines while keeping unrelated later edits."""
    def index(raw):
        rows=raw.splitlines(keepends=True);keys={}
        for i,line in enumerate(rows):
            if b'=' not in line:continue
            key=line.partition(b'=')[0].lstrip(b'\xef\xbb\xbf').lower()
            if key in keys:raise ValueError('Duplicate localization key needs manual review')
            keys[key]=i
        return rows,keys
    base,bkeys=index(original);last,lkeys=index(written);rows,keys=index(current);conflicts=[];remove=set()
    for key in set(bkeys)|set(lkeys):
        before=base[bkeys[key]] if key in bkeys else None;after=last[lkeys[key]] if key in lkeys else None
        if before==after:continue
        at=keys.get(key);present=rows[at] if at is not None else None
        if present==before:continue
        if present!=after:conflicts.append(key.decode('utf-8',errors='replace'));continue
        if before is None:remove.add(at)
        elif at is not None:rows[at]=before
        else:rows.append(before)
    return b''.join(line for i,line in enumerate(rows) if i not in remove),conflicts

def write_text(game,name,raw,profile=PROFILE):return Manager(game,profile).write(name,raw)

def write_localization(path,raw,profile=PROFILE):
    path=Path(path).resolve()
    if not path.as_posix().lower().endswith('/data/localization/english/global.ini'):raise ValueError('Select the game localization file')
    return write_text(path.parents[3],INI,raw,profile)

def archive_legacy_artifacts(game,profile=PROFILE):
    """Explicit cleanup of our named old artifacts; never glob generic backups."""
    from installation import ISOLATED_TEST
    if ISOLATED_TEST:raise ValueError('Legacy game-text cleanup is disabled in the isolated installer test')
    manager=Manager(game,profile);result=[]
    with localization_lock(manager.game/INI):
        for name in [INI+'.synthscan-blueprints.bak',INI+'.synthscan_bak','synthscan_pulse_test.cfg']:
            path=manager.game/name
            if not path.exists():continue
            if path.resolve()!=path or path.stat().st_nlink>1:raise ValueError('Linked legacy artifact requires review')
            raw=path.read_bytes();saved=manager.backup(name,raw,'legacy-artifact')
            if saved.read_bytes()!=raw or path.read_bytes()!=raw:raise ValueError('Legacy artifact changed during archival; original preserved')
            item=dict(path=name,archive=saved.name,sha256=digest(raw),bytes=len(raw))
            manifest=manager.folder/'legacy_archives.json';records=load(manifest,[]);records.append(item);save(manifest,records)
            path.unlink();result.append(item)
    return result

def _run_text_renderer(command,env,cancel=None):
    if cancel is None:
        return subprocess.run(command,env=env,check=True,creationflags=0x08000000,timeout=300)
    if cancel.is_set():raise ValueError('SynthStrings preparation was stopped')
    # Only this owned renderer is stopped, never the game or launcher.
    with subprocess.Popen(command,env=env,creationflags=0x08000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) as process:
        deadline=time.monotonic()+300
        while True:
            try:
                code=process.wait(timeout=.25);break
            except subprocess.TimeoutExpired:
                if cancel.is_set() or time.monotonic()>=deadline:
                    process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
                    raise ValueError('SynthStrings preparation was stopped before activation')
        if code:raise subprocess.CalledProcessError(code,command)

def apply_native(game,bits,profile=PROFILE,native=None,cancel=None):
    # Serialize renders independently of the short file-transaction lock. A
    # patch guard must be able to quarantine a pack during a slow archive read.
    with localization_lock(str(Path(game)/INI)+'.render',timeout_ms=1000 if cancel is not None else 330000):
        return _apply_native(game,bits,profile,native,cancel)

def _apply_native(game,bits,profile,native,cancel):
    manager=Manager(game,profile)
    from installation import valid_game
    from synthstrings_guard import snapshot,validate_render,record,current_pids
    if not valid_game(game):raise ValueError('The selected Star Citizen installation is unavailable')
    pids=current_pids();removed=False;source=None;ini=manager.target(INI)
    manager.folder.mkdir(parents=True,exist_ok=True);render=manager.folder/('render-'+uuid.uuid4().hex+'.ini');baseline=Path(str(render)+'.base')
    try:
        with localization_lock(Path(game)/INI):
            if not enabled(game,profile):return dict(written=False,note='SynthStrings is disabled for this channel')
            entry=manager.read().get('files',{}).get(INI,{})
            if ini.exists() and not any(mark in ini.read_bytes() for mark in MARKERS):return dict(written=False,note="Existing localization pack preserved; its annotations can be synchronized separately")
            source=snapshot(game)
            changed_build=entry.get('source',{}).get('fingerprint')!=source['fingerprint']
            missing_pack=not ini.exists()
            if changed_build or missing_pack:removed=manager.suspend(pids)
            if ini.exists() and changed_build:
                raise ValueError('Externally edited localization needs review before adaptation')
            if changed_build and time.time()-source['archive_mtime']<120:raise ValueError('Waiting for the game patch to settle before adaptation')
        env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(profile))
        _run_text_renderer([str(native or ROOT/'dist/native/SynthScan.exe'),'--render-texts',str(game),str(render),bits],env,cancel)
        raw=render.read_bytes();validation=validate_render(baseline.read_bytes(),raw)
        source.update(validation)
        with localization_lock(Path(game)/INI):
            if not enabled(game,profile):return dict(written=False,note='SynthStrings was disabled during preparation; no text was activated')
            if cancel is not None and cancel.is_set():raise ValueError('SynthStrings preparation was stopped before activation')
            if snapshot(game)['fingerprint']!=source['fingerprint']:raise ValueError('Game files changed while SynthStrings was adapting')
            # Read config at commit, so settings changed during extraction survive.
            cfg=manager.target(CFG);existing=cfg.read_bytes() if cfg.exists() else b''
            match=re.search(rb'^\s*g_language\s*=\s*[\"\x27]?([\w-]+)',existing.lstrip(b'\xef\xbb\xbf'),re.I|re.M)
            if match and match[1].lower()!=b'english':raise ValueError('SynthStrings requires the English game language')
            written=manager.write(INI,raw,source=source)
            if not match:
                ending=b'\r\n' if b'\r\n' in existing or not existing else b'\n'
                manager.write(CFG,existing+(ending if existing and not existing.endswith(b'\n') else b'')+b'g_language = english'+ending)
            if snapshot(game)['fingerprint']!=source['fingerprint']:raise ValueError('Game files changed during localization activation')
            status=load(manager.folder/'guard_status.json')
            if changed_build or missing_pack or status.get('state') not in ('ready','adapted'):
                record(manager,'adapted','SynthStrings adapted successfully',
                       f"Fresh text for this game build was verified: {validation['keys']} game strings preserved. Enhancements will load on the next game start.",
                       source,affected=set(pids)|set(current_pids()) if written or removed else ())
            return dict(written=True,changed=written,note='SynthStrings prepared from verified current game text; see Home for patch and restart status')
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        with localization_lock(Path(game)/INI):
            if not enabled(game,profile):return dict(written=False,note='SynthStrings is disabled for this channel')
            try:removed=manager.suspend(set(pids)|set(current_pids())) or removed
            except (OSError,ValueError) as cleanup_error:error=ValueError(str(error)+'; automatic quarantine could not complete: '+str(cleanup_error))
            defaults=not ini.exists()
            record(manager,'fallback' if defaults else 'attention',
                   'SynthStrings is temporarily using game defaults' if defaults else 'The existing language file was preserved',
                   ('The text update could not be verified. Game defaults will be used; choose Check now in Text settings to retry. ' if defaults else
                    'The text update stopped without replacing the existing file. Open Text settings to review it. ')+str(error),
                   source,affected=set(pids)|set(current_pids()) if removed else ())
            return dict(written=False,error=True,note=str(error),fallback=defaults)
    finally:
        render.unlink(missing_ok=True);baseline.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['apply-native','remove','enable','disable']);p.add_argument('--game',type=Path,required=True);p.add_argument('--profile',type=Path,default=PROFILE);p.add_argument('--native',type=Path);p.add_argument('--owned',default='');p.add_argument('--result',type=Path,required=True);a=p.parse_args()
    manager=Manager(a.game,a.profile)
    try:
        if a.action=='apply-native':result=apply_native(a.game,a.owned,a.profile,a.native)
        elif a.action=='remove':
            cleanup=manager.restore();result=dict(written=False,note='SynthStrings removed; restart the game' if not cleanup['conflicts'] else 'Some older or externally edited text needs review in Setup',cleanup=cleanup)
        else:manager.set_enabled(a.action=='enable');result=dict(written=False,note='Game-text preference saved')
    except Exception as error:result=dict(written=False,note=str(error),error=True)
    save(a.result,result)
    return 1 if result.get('error') else 0
if __name__=='__main__':raise SystemExit(main())
