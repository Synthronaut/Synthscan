"""Lifecycle for the full native app: readiness, bounded recovery and user quit."""
import argparse,ctypes,hashlib,json,logging,os,subprocess,time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app_lifecycle import ROOT,SingleInstance,Signal,game_process_ids,launcher_process_ids,instance_running,send_signal,kernel,LaunchPolicy
from refinery_orders import atomic_json

BINARY=ROOT/'dist/native/SynthScan.exe'
from installation import PROFILE,RELEASE,reference_paths,output_root
DATA=PROFILE
TARGET=ROOT/'launch_target.json'

def native_running():
    api=kernel();handle=api.OpenMutexW(0x100000,False,'Local\\SynthScan.Native.App')
    if not handle:return False
    api.CloseHandle(handle);return True

def native_ready():
    api=kernel();handle=api.OpenEventW(0x100000,False,'Local\\SynthScan.Native.Ready')
    if not handle:return False
    try:return api.WaitForSingleObject(handle,0)==0
    finally:api.CloseHandle(handle)

def validate_binary():
    manifest=json.loads((BINARY.parent/'build_manifest.json').read_text())
    for name in ['SynthScan.exe','opencv_world4120.dll']:
        if hashlib.sha256((BINARY.parent/name).read_bytes()).hexdigest()!=manifest['binary_files'][name]:
            raise ValueError('Native application does not match its build manifest: '+name)

def launch(automatic=False):
    validate_binary()
    # Re-anchor generated paths after an installer, move or version switch.
    # These contain no credentials and are excluded from signed payload files.
    import sys
    atomic_json(BINARY.parent/'native_runtime.json',dict(workspace=str(ROOT),pythonw=str(Path(sys.executable).with_name('pythonw.exe'))))
    atomic_json(TARGET,dict(schema=1,target='native',binary=str(BINARY)))
    if RELEASE:
        from setup_status import ready
        if not ready():
            return subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-I',str(ROOT/'app_launcher.py')],
                cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen([str(BINARY)]+(['--autostart'] if automatic else []),cwd=BINARY.parent,
                            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW)

class RecoveryPolicy:
    def __init__(self):
        self.games=frozenset();self.attempts=0;self.next_try=0;self.started_at=None;self.suppressed=False;self.ready_since=None
    def update(self,games,running,ready,quit_at=0,now=None):
        now=time.time() if now is None else now;games=frozenset(games)
        if games!=self.games:
            self.games=games;self.attempts=0;self.next_try=0;self.started_at=None;self.suppressed=False;self.ready_since=None
        if quit_at and self.started_at and quit_at>=self.started_at:self.suppressed=True
        if ready:
            # Reopening the app revokes an earlier quit. The old watcher kept
            # suppression latched even after a successful manual restart.
            if self.suppressed and not quit_at:
                self.suppressed=False;self.started_at=now;self.ready_since=None
            # A genuinely ready app may later be reopened by hand; future crashes
            # get a fresh recovery budget, while a user exit stays suppressed.
            if self.ready_since is None:self.ready_since=now
            if now-self.ready_since>=30:self.attempts=0
            if self.started_at is None:self.started_at=now
            return False
        self.ready_since=None
        if not games or running or self.suppressed or self.attempts>=3 or now<self.next_try:return False
        self.started_at=now;self.attempts+=1;self.next_try=now+[5,15,45][self.attempts-1]
        return True

def read_quit(games):
    try:
        data=json.loads((DATA/'native_exit.json').read_text())
        status=json.loads((DATA/'native_status.json').read_text())
        # A marker from an older app instance cannot suppress recovery of a
        # newer one, even when Star Citizen has stayed open throughout.
        if data.get('pid') and data['pid']!=status.get('pid'):return 0
        if float(data['at'])<float(status.get('at',0)):return 0
        return float(data['at']) if set(data['game_pids'])==set(games) and data['reason']=='user' else 0
    except (OSError,ValueError,KeyError,TypeError):return 0

def setup_busy():
    if not instance_running('setup'):return False
    from setup_status import ready
    return not ready()

def watch():
    lock=SingleInstance('watcher')
    if not lock.acquired:return
    stop=Signal('watcher-stop');policy=RecoveryPolicy();DATA.mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger('synthscan.native_watcher');logger.setLevel(logging.INFO);logger.propagate=False
    handler=RotatingFileHandler(DATA/'launcher.log',maxBytes=1024*1024,backupCount=2,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logger.addHandler(handler)
    logger.info('Recovery watcher started')
    from synthstrings_guard import GuardService
    from feature_modules import enabled
    from feature_services import IdleProvider
    strings_guard=GuardService(DATA,BINARY) if enabled('synthstrings') else IdleProvider()
    from launcher_activity import LauncherActivity
    launcher_activity=LauncherActivity(DATA);launcher_launch=LaunchPolicy()
    last_error='';process=None
    try:
        while True:
            try:
                games=game_process_ids();running=native_running();ready=native_ready()
                launchers=launcher_process_ids()
                launcher_activity.update(launchers,games)
                strings_guard.tick()
                if launcher_launch.needs_launch(launchers,running or setup_busy() or instance_running('updating')):
                    process=launch(False);launcher_launch.mark_launched()
                    logger.info('Started SynthScan for RSI Launcher')
                    running=True
                if process is not None and process.poll() is not None:
                    code=process.returncode
                    atomic_json(DATA/'native_process_exit.json',dict(at=time.time(),pid=process.pid,
                        exit_code=code,exit_hex=f'0x{code & 0xffffffff:08X}',app_running=running))
                    logger.info('Launched process pid=%s exited code=%s (0x%08X), app_running=%s',process.pid,code,code & 0xffffffff,running)
                    process=None
                if policy.update(games,running or setup_busy() or instance_running('updating'),ready,read_quit(games)):
                    process=launch(True);logger.info('Started native SynthScan pid=%s for game pids=%s',process.pid,sorted(games))
                if running and not ready and policy.started_at and time.time()-policy.started_at>60:
                    last_error='Native application has not reported ready. Open SynthScan manually to inspect startup.'
                elif policy.attempts>=3 and not running:last_error='Native startup failed three times; automatic retries stopped for this game run.'
                elif ready:last_error=''
                atomic_json(DATA/'watcher_status.json',dict(at=time.time(),running=True,app_running=running,ready=ready,
                            error=last_error,attempts=policy.attempts,voluntary_exit=policy.suppressed))
            except Exception as exc:
                last_error=str(exc);logger.exception('Native game watcher poll failed')
            if stop.wait(3):break
    finally:
        launcher_activity.close()
        strings_guard.close()
        stop.close();lock.close();logger.removeHandler(handler);handler.close()

def install():
    validate_binary();atomic_json(TARGET,dict(schema=1,target='native',binary=str(BINARY)))
    from auto_launch import install as install_shortcut
    send_signal('watcher-stop')
    deadline=time.monotonic()+5
    while instance_running('watcher') and time.monotonic()<deadline:time.sleep(.05)
    if instance_running('watcher'):raise RuntimeError('Existing watcher did not stop; startup target was not duplicated')
    # Clear only this application's per-user Task Manager startup-disable entry.
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder',0,winreg.KEY_SET_VALUE) as key:
            try:winreg.DeleteValue(key,'SynthScan Game Watcher.lnk')
            except FileNotFoundError:pass
    except FileNotFoundError:pass
    install_shortcut()

def main():
    p=argparse.ArgumentParser();p.add_argument('--launch',action='store_true');p.add_argument('--autostart',action='store_true')
    p.add_argument('--watch',action='store_true');p.add_argument('--install',action='store_true');p.add_argument('--uninstall',action='store_true');p.add_argument('--status',action='store_true')
    p.add_argument('--timing',type=int,metavar='OWNER_PID')
    p.add_argument('--network',type=int,metavar='OWNER_PID')
    args=p.parse_args()
    DATA.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'native_control.log',level=logging.INFO)
    try:
        if args.watch:watch()
        elif args.install:install()
        elif args.uninstall:
            from auto_launch import uninstall
            uninstall()
        elif args.launch:launch(args.autostart)
        elif args.timing or args.network:
            import sys
            if instance_running('network-probe' if args.network else 'native-timing'):return
            pythonw=Path(sys.executable).with_name('pythonw.exe')
            script=ROOT/'tools/live_network_probe.py' if args.network else ROOT/'native_timing.py'
            fields=[str(script),'--owner',str(args.network or args.timing)]
            if args.network:fields+=['--seconds','0']
            parameters=subprocess.list2cmdline(fields)
            shell=ctypes.windll.shell32.ShellExecuteW
            shell.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_int];shell.restype=ctypes.c_void_p
            code=shell(None,'runas',str(pythonw),parameters,str(ROOT),0)
            if not code or code<=32:raise RuntimeError('Windows timing permission was not granted')
        else:
            from auto_launch import shortcut_path
            print(json.dumps(dict(installed=shortcut_path().exists(),watcher_running=instance_running('watcher'),app_running=native_running(),ready=native_ready(),game_pids=sorted(game_process_ids()),native_status=read_status())))
        if args.install or args.uninstall:atomic_json(DATA/'control_status.json',dict(at=time.time(),ok=True))
    except Exception as exc:
        logging.exception('Native lifecycle action failed')
        atomic_json(DATA/'control_status.json',dict(at=time.time(),ok=False,error=str(exc)))
        if args.launch and not args.autostart:ctypes.windll.user32.MessageBoxW(None,str(exc),'SynthScan could not start',0x10)
        raise SystemExit(1)

def read_status():
    try:
        state=json.loads((DATA/'native_status.json').read_text())
        return state if native_running() and 0<=time.time()-state['at']<4 else {}
    except (OSError,ValueError,KeyError,TypeError):return {}

if __name__=='__main__':main()
