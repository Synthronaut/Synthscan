"""Remove this installation's startup entry; keep player records and user edits."""
import json
from pathlib import Path
import subprocess
import time
from installation import ROOT,PROFILE,game_directory
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
    state=read(PROFILE/'reputation_localization_state.json',limit=1024*1024)
    if state.get('entries'):
        try:
            game=game_directory(True);file=game/'Data/Localization/english/global.ini'
            before=file.read_bytes()
            snapshot=dict(own_character_verified=True,complete=True,read_at=time.time(),character_key=state.get('character_key'),records=[])
            text,_=annotate_names(before.decode('utf-8'),snapshot,{}, {},state)
            temporary=file.with_name('global.ini.synthscan-uninstall.tmp');temporary.write_bytes(text.encode('utf-8'))
            if file.read_bytes()!=before:raise ValueError('Game text changed during cleanup')
            temporary.replace(file);result['names_restored']=True
        except (OSError,ValueError):result['game_text_preserved']=True
    PROFILE.mkdir(parents=True,exist_ok=True)
    (PROFILE/'uninstall_result.json').write_text(json.dumps(result),encoding='utf-8')
