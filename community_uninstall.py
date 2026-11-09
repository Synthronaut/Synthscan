"""Remove this installation's startup entry; keep player records and user edits."""
import json
from pathlib import Path
import subprocess
import time
from installation import ROOT,PROFILE
from app_lifecycle import send_signal
from reputation_strings import annotate_names
from setup_status import read

def cleanup():
    from auto_launch import shortcut_path
    shortcut=shortcut_path()
    # A development checkout or another install may own the shared shortcut.
    from community_startup import owns_shortcut
    if owns_shortcut():shortcut.unlink()
    send_signal('watcher-stop');send_signal('setup-stop')
    result=dict(at=time.time(),player_records_preserved=True,names_restored=False)
    # Versioned app executables are not individual Inno [Files] entries. Stop
    # only this installation's verified native image before removing its tree.
    from update_agent import stop_native
    try:stop_native(ROOT/'dist/native/SynthScan.exe')
    except (OSError,ValueError,TimeoutError) as error:result['app_shutdown_warning']=str(error)
    from game_text_lifecycle import Manager
    channels=set()
    for journal in (PROFILE/'game_text').glob('*/journal.json'):
        state=read(journal,limit=4*1024*1024)
        if state.get('game'):channels.add(state['game'])
    recorded=read(PROFILE/'installation.json').get('game_dir')
    if recorded:channels.add(recorded)
    result['game_text']={}
    for channel in channels:
        try:result['game_text'][channel]=Manager(channel,PROFILE).restore()
        except (OSError,ValueError) as error:result['game_text'][channel]=dict(error=str(error))
    # No before-install baseline exists for old installs. Preserve their text
    # and offer explicit archival in Setup instead of guessing at ownership.
    PROFILE.mkdir(parents=True,exist_ok=True)
    (PROFILE/'uninstall_result.json').write_text(json.dumps(result),encoding='utf-8')
