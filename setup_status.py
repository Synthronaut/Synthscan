"""Player-facing setup state; all files belong to this Windows profile."""
import json
import time
from installation import ROOT,PROFILE,game_directory,reference_paths,output_root
from telemetry_ipc import read_shared_json

def read(path,limit=16384):
    try:return read_shared_json(path,limit=limit) or {}
    except (OSError,ValueError,TypeError):return {}

def version():
    try:return json.loads((ROOT/'release.json').read_text(encoding='utf-8'))['version']
    except (OSError,ValueError,KeyError):return 'development'

def ready():
    try:
        p=reference_paths();result=read_shared_json(PROFILE/'setup_result.json')
        runtime=read_shared_json(ROOT/'dist/native/native_runtime.json')
        return (result.get('app_version')==version() and result.get('build_id')==p['root'].name
                and result.get('complete') is True and runtime.get('workspace')==str(ROOT)
                and read(output_root()/'active_build.json').get('build_id')==p['root'].name
                and (p['root']/'ready.json').exists() and (ROOT/'dist/native/workspace_library.json').exists()
                and (output_root()/'data/local_game_library.json').exists())
    except (OSError,ValueError,KeyError,TypeError):return False

def reputation_view(directory=PROFILE,now=None):
    now=time.time() if now is None else now
    status=read(directory/'reputation_labels_status.json')
    session=read(directory/'session_state.json',limit=8*1024*1024)
    running=bool(session.get('game_pids')) and 0<=now-session.get('written_at',0)<10
    if not running:
        return dict(state='waiting',title='Enter Star Citizen to sync your reputation',
                    detail='Log in to your character normally. SynthScan will check your own account automatically.')
    if not status.get('ok'):
        return dict(state='checking',title='Checking your signed-in character…',
                    detail=status.get('help','Stay signed in. No password or account details need to be entered here.'))
    if not 0<=now-status.get('at',0)<120:
        return dict(state='checking',title='Refreshing reputation…',detail='Waiting for a fresh, verified account response.')
    if not status.get('names'):
        return dict(state='checking',title='No corporation balances available yet',detail='Only verified balances are shown. Unknown values are never filled with zero.')
    at_write=set(status.get('written_game_pids',[]))
    current=set(session.get('game_pids',[]))
    pending=not at_write or bool(at_write & current)
    return dict(state='restart' if pending else 'ready',
                title='Your reputation is ready — restart Star Citizen' if pending else 'Your reputation labels are up to date',
                detail=(f"Numbers are prepared for {status['names']} corporation names. Fully exit the game and reopen it when convenient. Logging out alone will not reload the text."
                        if pending else 'The game was started after these labels were written. New reputation changes may require another restart.'),
                written_at=status.get('labels_written_at',0))

def error_message(error):
    if isinstance(error,ValueError) and 'English' in str(error):return str(error)
    if isinstance(error,PermissionError):
        return 'Windows blocked access to the game text folder. Choose Allow game-text access, approve the Windows prompt, then retry.'
    if isinstance(error,FileNotFoundError):
        return 'Star Citizen or a required file could not be found. Use Choose game folder, or finish updating the game in RSI Launcher, then retry.'
    if isinstance(error,OSError) and getattr(error,'winerror',None)==112:
        return 'There is not enough free disk space. Free at least 3 GB, then retry.'
    return 'Setup could not finish. Close SynthScan’s other windows, finish any RSI Launcher update, and retry. Your player records have been preserved.'
