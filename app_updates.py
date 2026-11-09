"""Signed, staged application updates. Activation switches a version pointer."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import uuid
import zipfile

from update_signing import strict_json,verify
from edition_payload import validate_edition,check_update_edition,forbidden_standard_path

SCHEMA=1
INTERVAL=6*3600
RETRY=300
MAX_ARCHIVE=768*1024*1024
MAX_UNPACKED=2*1024*1024*1024
HEX=re.compile(r'[0-9a-f]{64}')
GENERATED={'dist/native/native_runtime.json','dist/native/workspace_library.json','launch_target.json'}
class UpdateDeferred(Exception):pass


def load(path,default=None):
    try:return strict_json(Path(path).read_bytes())
    except (OSError,ValueError,TypeError):return {} if default is None else default


def replace_file(source,target):
    if os.name=='nt':
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.MoveFileExW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32];api.MoveFileExW.restype=ctypes.c_int
        if not api.MoveFileExW(str(source),str(target),9):raise ctypes.WinError(ctypes.get_last_error())
    else:os.replace(source,target)


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        for attempt in range(6):
            try:replace_file(name,path);return
            except PermissionError:
                if attempt==5:raise
                time.sleep(.02)
    finally:
        if os.path.exists(name):os.unlink(name)


def version_key(value):
    found=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:[-.]([A-Za-z0-9.-]+))?',str(value))
    if not found:raise ValueError('Unsupported application version')
    suffix=found[4]
    return (*map(int,found.groups()[:3]),int(suffix is None),tuple((1,int(p)) if p.isdigit() else (0,p.lower()) for p in re.split('[.-]',suffix or '')))


def config(root):
    value=load(Path(root)/'update_trust.json')
    if value.get('schema')!=SCHEMA or not value.get('keys') or not value.get('manifest_url'):
        raise ValueError('No trusted application update channel is configured')
    if load(Path(root)/'release.json').get('edition','full')=='standard':
        value=dict(value,manifest_url=value.get('standard_manifest_url',''))
        if not value['manifest_url']:raise ValueError('No Standard update channel configured')
    return value


def allowed_url(url,trust):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in trust.get('allowed_hosts',[]) or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None,443):
        raise ValueError('Update URL is outside the trusted HTTPS hosts')
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self,trust):self.trust=trust
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        allowed_url(newurl,self.trust)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def request(url,trust):
    allowed_url(url,trust)
    return urllib.request.build_opener(Redirects(trust)).open(urllib.request.Request(url,headers={
        'User-Agent':'SynthScan-Updater/1.0','Accept':'application/octet-stream, application/json','Cache-Control':'no-cache'}),timeout=15)


def manifest(raw,trust,now=None):
    now=time.time() if now is None else now
    value=verify(raw,trust)
    if value.get('schema')!=SCHEMA or value.get('kind')!='application' or value.get('platform')!='windows-x64':
        raise ValueError('Unsupported application update schema or platform')
    validate_edition(value.get('edition','full'))
    version_key(value.get('version'))
    for key in ('sequence','size','unpacked_size'):
        if not isinstance(value.get(key),int) or isinstance(value[key],bool) or value[key]<=0:raise ValueError('Invalid update '+key)
    if value['size']>MAX_ARCHIVE or value['unpacked_size']>MAX_UNPACKED:raise ValueError('Application update exceeds size limits')
    if not HEX.fullmatch(str(value.get('sha256',''))):raise ValueError('Invalid archive digest')
    if value.get('minimum_updater',1)>SCHEMA:raise ValueError('This update needs a newer bootstrap protocol')
    if not isinstance(value.get('issued_at'),(int,float)) or not isinstance(value.get('expires_at'),(int,float)) or not 0<value['issued_at']<=now+300 or not now<value['expires_at']<=value['issued_at']+2*366*86400:
        raise ValueError('Update manifest is expired or has an invalid date')
    allowed_url(value.get('url',''),trust)
    return value


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(1024*1024):h.update(block)
    return h.hexdigest()


def safe_member(name):
    if '\\' in name or not name.startswith('SynthScan/'):raise ValueError('Unexpected update archive root')
    relative=name[len('SynthScan/'):];parts=PurePosixPath(relative).parts
    if not parts or relative.startswith('/') or any(p in ('.','..') or p.endswith(('.',' ')) or re.search(r'[<>:"|?*\x00-\x1f]',p) or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p,re.I) for p in parts):
        raise ValueError('Unsafe application archive path')
    # PurePosixPath normalizes away empty/dot segments; reject before that too.
    if any(p in ('','.','..') for p in relative.split('/')):raise ValueError('Non-canonical archive path')
    return '/'.join(parts)


def inspect_archive(archive,value,destination=None):
    """Validate the complete payload, not just the native executable."""
    with zipfile.ZipFile(archive) as zipped:
        files={};folded=set();total=0
        for member in zipped.infolist():
            if member.is_dir():continue
            relative=safe_member(member.filename);key=relative.casefold()
            if key in folded:raise ValueError('Duplicate application archive path')
            if stat.S_IFMT(member.external_attr>>16) not in (0,stat.S_IFREG) or member.external_attr&0x400 or member.flag_bits&1:
                raise ValueError('Links, reparse points and encrypted ZIP members are not supported')
            folded.add(key);files[relative]=member;total+=member.file_size
        if len(files)>50000 or total>MAX_UNPACKED or total!=value['unpacked_size']:raise ValueError('Invalid unpacked update size')
        if 'release_integrity.json' not in files:raise ValueError('No application integrity manifest')
        if files['release_integrity.json'].file_size>8*1024*1024:raise ValueError('Integrity manifest exceeds limit')
        integrity=strict_json(zipped.read(files['release_integrity.json']))
        if integrity.get('version')!=value['version'] or not isinstance(integrity.get('files'),dict):raise ValueError('Payload version mismatch')
        if set(files)!=(set(integrity['files'])|{'release_integrity.json'}):raise ValueError('Application payload is incomplete or has unlisted files')
        required={'SynthScan.exe','app_launcher.py','app_updates.py','update_agent.py','update_signing.py','update_trust.json','release.json',
                  'runtime/pythonw.exe','runtime/python314.dll','runtime/Lib/encodings/__init__.py','dist/native/SynthScan.exe','dist/native/build_manifest.json'}
        if not required.issubset(files):raise ValueError('Required application files are missing')
        release=strict_json(zipped.read(files['release.json']))
        if release.get('version')!=value['version'] or release.get('updater_schema')!=SCHEMA:raise ValueError('Unsupported packaged application')
        if 'edition' in release and 'edition_payload.py' not in files:raise ValueError('Edition validation module is missing')
        edition=check_update_edition(release,value)
        if edition=='standard' and any(forbidden_standard_path(p) for p in files):raise ValueError('Standard payload contains screen-reading components')
        for relative,member in files.items():
            h=hashlib.sha256();target=None
            if destination is not None:
                path=Path(destination)/relative;path.parent.mkdir(parents=True,exist_ok=True);target=path.open('xb')
            try:
                with zipped.open(member) as stream:
                    while block:=stream.read(1024*1024):
                        h.update(block)
                        if target:target.write(block)
            finally:
                if target:target.close()
            if relative!='release_integrity.json' and h.hexdigest()!=integrity['files'][relative]:raise ValueError('Payload checksum mismatch: '+relative)
    return integrity


def stage(root,directory,trust=None,opener=request,now=None):
    now=time.time() if now is None else now;root=Path(root);directory=Path(directory);trust=trust or config(root)
    if load(root/'release.json').get('module_schema')==1:
        from module_distribution import prepare
        pending=load(directory/'updates/pending.json')
        if pending.get('kind')=='modules':return dict(status='staged',version=pending.get('version'),detail='Selected features are verified and waiting for safe activation.')
        return prepare(root,directory,trust=trust,opener=opener,now=now)
    with opener(trust['manifest_url'],trust) as response:raw=response.read(256*1024+1)
    value=manifest(raw,trust,now);installed_release=load(root/'release.json');check_update_edition(installed_release,value);installed=installed_release.get('version','development')
    if installed=='development':return dict(status='development',detail='Development checkout: automatic replacement is disabled.')
    if version_key(value['version'])<=version_key(installed):return dict(status='current',version=installed,detail='Installed application matches or is newer than the signed channel.')
    folder=directory/'updates';folder.mkdir(parents=True,exist_ok=True)
    for partial in folder.glob('download-*.part'):
        if not partial.is_symlink() and now-partial.stat().st_mtime>86400:partial.unlink(missing_ok=True)
    seen=load(folder/'verified.json')
    if value['sequence']<seen.get('sequence',0) or (value['sequence']==seen.get('sequence') and seen.get('sha256')!=value['sha256']):raise ValueError('Update rollback or sequence reuse rejected')
    if load(folder/'failed.json').get('sha256')==value['sha256']:
        return dict(status='rejected',version=value['version'],detail='This payload failed an earlier activation. Keeping the working application and waiting for a corrected release.')
    archive=folder/(value['sha256']+'.zip');signed=folder/(value['sha256']+'.json')
    if not archive.exists() or archive.stat().st_size!=value['size'] or digest(archive)!=value['sha256']:
        fd,name=tempfile.mkstemp(prefix='download-',suffix='.part',dir=folder);h=hashlib.sha256();received=0
        try:
            with os.fdopen(fd,'wb') as stream,opener(value['url'],trust) as response:
                while block:=response.read(1024*1024):
                    received+=len(block)
                    if received>value['size']:raise ValueError('Update download exceeds declared size')
                    h.update(block);stream.write(block)
                stream.flush();os.fsync(stream.fileno())
            if received!=value['size'] or h.hexdigest()!=value['sha256']:raise ValueError('Update download size or checksum mismatch')
            os.replace(name,archive)
        finally:
            if os.path.exists(name):os.unlink(name)

    inspect_archive(archive,value)
    write(signed,strict_json(raw));write(folder/'verified.json',dict(sequence=value['sequence'],sha256=value['sha256']))
    write(folder/'pending.json',dict(schema=SCHEMA,sha256=value['sha256'],version=value['version']))
    return dict(status='staged',version=value['version'],sha256=value['sha256'],detail='Verified update downloaded. It will install when the game is closed and SynthScan windows are idle.')


def active_token(root):
    path=Path(root)/'active_version.txt'
    if not path.exists():return None
    value=path.read_text(encoding='ascii').strip()
    if not HEX.fullmatch(value):raise ValueError('Invalid active application pointer')
    return value


def set_active(root,token):
    path=Path(root)/'active_version.txt'
    if token is None:path.unlink(missing_ok=True);return
    if not HEX.fullmatch(token):raise ValueError('Invalid application version directory')
    temporary=path.with_suffix('.pending')
    with temporary.open('w',encoding='ascii') as stream:stream.write(token+'\n');stream.flush();os.fsync(stream.fileno())
    replace_file(temporary,path)


def safe_remove(path,base):
    path=Path(path);base=Path(base).resolve()
    if path.is_symlink() or path.resolve()==base or not path.resolve().is_relative_to(base):raise ValueError('Unsafe update cleanup target')
    shutil.rmtree(path)


def module_maintenance(target,current,directory,prune=False,install=None):
    args=['--root',str(install or current),'--profile',str(directory)]
    args+=['--prune',str(target)] if prune else ['--deactivate-removed',str(current)]
    subprocess.run([str(Path(target)/'runtime/python.exe'),'-I','-B',str(Path(target)/'module_setup.py'),*args],
        cwd=target,check=True,timeout=360,creationflags=0x08000000 if os.name=='nt' else 0)


def activate(root,current,directory,health,launch,trust=None,can_activate=lambda:True):
    """File-system transaction. Tests inject health/launch without opening UI."""
    root=Path(root).resolve();current=Path(current).resolve();directory=Path(directory).resolve()
    if root==directory or root.is_relative_to(directory) or directory.is_relative_to(root):raise ValueError('Application and profile paths must be separate')
    if not (root/'SynthScan.exe').is_file() or not (current/'release.json').is_file():raise ValueError('Not an installed SynthScan application')
    trust=trust or config(current);updates=directory/'updates';pending=load(updates/'pending.json');token=pending.get('sha256','')
    if not HEX.fullmatch(token):raise ValueError('No verified staged update')
    is_modules=pending.get('kind')=='modules'
    if is_modules:
        from module_distribution import activation_payload
        value,unpack=activation_payload(current,directory,pending,trust)
    else:
        if load(current/'release.json').get('module_schema')==1:raise ValueError('A modular installation requires a module-preserving update')
        value=manifest((updates/(token+'.json')).read_bytes(),trust)
        check_update_edition(load(current/'release.json'),value)
        if value['sha256']!=token or version_key(value['version'])<=version_key(load(current/'release.json').get('version')):raise ValueError('Staged update no longer applies')
        archive=updates/(token+'.zip')
        if archive.stat().st_size!=value['size'] or digest(archive)!=token:raise ValueError('Staged application archive changed')
        unpack=lambda destination:inspect_archive(archive,value,destination)
    versions=root/'versions';versions.mkdir(exist_ok=True)
    if versions.is_symlink():raise ValueError('Version directory must not be a link')
    target=versions/token;temporary=versions/('.incoming-'+uuid.uuid4().hex)
    old=active_token(root);setup_path=directory/'setup_result.json';old_setup=setup_path.read_bytes() if setup_path.exists() else None
    if current!=(root/'versions'/old if old else root):raise ValueError('Active application changed during update preparation')
    journal=dict(schema=1,phase='preparing',previous=old,active=token,version=value['version'],at=time.time())
    if shutil.disk_usage(root).free<value['unpacked_size']+128*1024*1024:raise OSError('Not enough free disk space to keep the current app and prepare an update')
    if old_setup is not None:write(updates/'setup_before.json',strict_json(old_setup))
    else:(updates/'setup_before.json').unlink(missing_ok=True)
    write(updates/'transaction.json',journal)
    try:
        temporary.mkdir();unpack(temporary)
        for name in ('workspace_library.json',):
            source=directory/name
            if not source.exists():source=current/'dist/native'/name
            if source.exists() and source.stat().st_size<=64*1024*1024:
                model=load(source)
                if isinstance(model.get('rows'),list):shutil.copy2(source,temporary/'dist/native'/name)
        write(temporary/'dist/native/native_runtime.json',dict(workspace=str(target),pythonw=str(target/'runtime/pythonw.exe')))
        write(temporary/'launch_target.json',dict(schema=1,target='native',binary=str(target/'dist/native/SynthScan.exe')))
        if target.exists():safe_remove(target,versions)
        temporary.rename(target)
        if old_setup is not None:
            setup=strict_json(old_setup);old_release=load(current/'release.json');new_release=load(target/'release.json')
            if setup.get('complete') and old_release.get('setup_schema',1)==new_release.get('setup_schema',1):
                write(updates/'setup_before.json',setup);setup['app_version']=value['version'];write(setup_path,setup)
        journal['phase']='prepared';write(updates/'transaction.json',journal)
        if not can_activate():raise UpdateDeferred('Game or application activity resumed; update remains staged.')
        if is_modules:module_maintenance(target,current,directory,install=root)
        write(root/'activation_pending.txt',dict(schema=1))
        set_active(root,token);journal['phase']='activated';write(updates/'transaction.json',journal)
        launch(target,True)
        if not health(target):raise RuntimeError('Updated application did not report healthy readiness')
        if is_modules:module_maintenance(target,current,directory,prune=True,install=root)
        journal.update(phase='applied',applied_at=time.time());write(updates/'transaction.json',journal)
        (root/'activation_pending.txt').unlink(missing_ok=True);(updates/'pending.json').unlink(missing_ok=True)
        # Only version folders created by this protocol are eligible for pruning.
        for path in versions.iterdir():
            if HEX.fullmatch(path.name) and path.name not in {old,token} and (path/'release_integrity.json').is_file():
                try:safe_remove(path,versions)
                except OSError:logging.warning('Old application version cleanup deferred')
        for path in updates.glob('*.zip'):
            if HEX.fullmatch(path.stem) and path.stem!=token:
                try:path.unlink();path.with_suffix('.json').unlink(missing_ok=True)
                except OSError:logging.warning('Old update archive cleanup deferred')
        return journal
    except Exception as error:
        set_active(root,old)
        if old_setup is not None:
            current_setup=load(setup_path)
            if current_setup.get('app_version')==value['version']:write(setup_path,strict_json(old_setup))
        journal.update(phase='deferred' if isinstance(error,UpdateDeferred) else 'rolled_back',failed_at=time.time());write(updates/'transaction.json',journal)
        if not isinstance(error,UpdateDeferred):
            write(updates/'failed.json',dict(sha256=token,reason=str(error),at=time.time()));(updates/'pending.json').unlink(missing_ok=True)
        (root/'activation_pending.txt').unlink(missing_ok=True)
        raise
    finally:
        if temporary.exists():safe_remove(temporary,versions)


def recover(root,directory):
    """The stable bootstrap calls its original runtime after an interrupted switch."""
    root=Path(root);directory=Path(directory);journal=load(directory/'updates/transaction.json')
    if journal.get('schema')!=1:raise ValueError('Cannot recover an unknown update transaction')
    applied=journal.get('active')
    if journal.get('phase')=='applied' and isinstance(applied,str) and HEX.fullmatch(applied) and (root/'versions'/applied/'release.json').is_file():
        set_active(root,applied)
    else:
        previous=journal.get('previous')
        if previous is not None and (not HEX.fullmatch(previous) or not (root/'versions'/previous/'release.json').is_file()):raise ValueError('Previous application version is unavailable')
        set_active(root,previous)
        before=load(directory/'updates/setup_before.json')
        if before and load(directory/'setup_result.json').get('app_version')==journal.get('version'):write(directory/'setup_result.json',before)
        journal.update(phase='rolled_back',reason='Interrupted activation recovered');write(directory/'updates/transaction.json',journal)
    (root/'activation_pending.txt').unlink(missing_ok=True)
    return journal


def prepare_agent(root,directory):
    root=Path(root);directory=Path(directory);runtime=root/'runtime'
    if not (runtime/'pythonw.exe').is_file():raise ValueError('The installed updater runtime is unavailable')
    agents=directory.parent/'update-agent';agents.mkdir(parents=True,exist_ok=True)
    for old in agents.iterdir():
        if re.fullmatch('[0-9a-f]{32}',old.name) and time.time()-old.stat().st_mtime>7*86400:
            try:safe_remove(old,agents)
            except OSError:pass
    folder=agents/uuid.uuid4().hex;folder.mkdir()
    target=folder/'runtime';target.mkdir()
    for name in ('pythonw.exe','python3.dll','python314.dll','vcruntime140.dll','vcruntime140_1.dll'):
        if (runtime/name).exists():shutil.copy2(runtime/name,target/name)
    for name in ('Lib','DLLs'):
        shutil.copytree(runtime/name,target/name,ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','idlelib'))
    (target/'python314._pth').write_text('..\n.\nLib\nDLLs\nimport site\n',encoding='ascii')
    for name in ('app_updates.py','update_signing.py','update_agent.py','app_lifecycle.py','edition_payload.py','feature_modules.py','module_distribution.py'):
        if (root/name).is_file():shutil.copy2(root/name,folder/name)
    return folder


class AppUpdateService:
    def __init__(self,directory,root=None):
        from installation import ROOT,RELEASE,INSTALL_ROOT
        self.directory=Path(directory);self.root=Path(root or ROOT);self.install=INSTALL_ROOT if root is None else self.root
        self.enabled=RELEASE if root is None else (self.root/'release.json').exists()
        self.path=self.directory/'app_update_status.json';self.state=load(self.path)
        self.future=None;self.preparing=None;self.agent=None;self.started=False;self.agent_process=None
        self.prepare_after=0;self.force_after=0
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='app-updates');self.next_check=0

    def tick(self,game_running=True,force=False):
        now=time.time()
        if self.started and self.agent_process is not None and self.agent_process.poll() is not None:
            self.started=False;self.agent_process=None;self.prepare_after=now+RETRY
            self.state=dict(status='staged',detail='Update activation was deferred; it will retry automatically when idle.')
        from app_lifecycle import instance_running
        if not self.enabled:
            self.state=dict(status='development',detail='Development checkout: automatic application replacement is disabled. Packaged installations update automatically.')
        elif load(self.directory/'update_preferences.json').get('automatic_app',True) is not True:
            self.state=dict(status='disabled',detail='Automatic application updates are disabled in Data updates.')
        elif instance_running('updating'):
            self.state=dict(status='applying',detail='A verified application update is being activated.')
        else:
            if self.future is not None and self.future.done():
                try:self.state=dict(self.future.result(),checked_at=now);self.next_check=now+INTERVAL
                except Exception as error:
                    self.state=dict(status='unavailable',detail=str(error),checked_at=now);self.next_check=now+RETRY
                self.future=None
            if self.future is None and (now>=self.next_check or (force and now>=self.force_after)) and not self.started:
                self.state=dict(self.state,status='checking',detail='Checking the signed application update channel.')
                self.future=self.pool.submit(stage,self.root,self.directory)
                self.force_after=now+30
            if self.preparing is not None and self.preparing.done():
                try:self.agent=self.preparing.result()
                except Exception as error:self.state=dict(status='staged',detail='Update preparation deferred: '+str(error));self.prepare_after=now+RETRY
                self.preparing=None
            if not game_running and not self.started and load(self.directory/'updates/pending.json'):
                from app_lifecycle import instance_running
                from update_agent import idle_windows
                if not instance_running('setup') and idle_windows(self.install):
                    if self.agent is None and self.preparing is None and now>=self.prepare_after:self.preparing=self.pool.submit(prepare_agent,self.root,self.directory)
                    elif self.agent is not None:
                        if now>=self.prepare_after:
                            try:
                                self.agent_process=subprocess.Popen([str(self.agent/'runtime/pythonw.exe'),'-I','-B',str(self.agent/'update_agent.py'),
                                    '--root',str(self.install),'--current',str(self.root),'--profile',str(self.directory)],
                                    cwd=self.agent,creationflags=subprocess.CREATE_NO_WINDOW|0x01000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                                self.started=True;self.state=dict(status='applying',detail='Applying the verified update outside the game; previous version retained.')
                            except OSError as error:
                                self.prepare_after=now+RETRY;self.state=dict(status='staged',detail='Detached updater could not start: '+str(error))
        write(self.path,dict(self.state,at=now,installed_version=load(self.root/'release.json').get('version','development'),last_install=load(self.directory/'updates/transaction.json')))
        return self.state

    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
