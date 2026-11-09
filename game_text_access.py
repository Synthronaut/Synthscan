"""One-shot, explicitly requested permission repair; never reads credentials."""
import ctypes
import json
from pathlib import Path
import re
import subprocess
import sys
from installation import ROOT,PROFILE,valid_game,game_directory

def text_targets(game):
    from installation import ISOLATED_TEST
    if ISOLATED_TEST:raise ValueError('Game permission changes are disabled in the isolated installer test')
    game=Path(game).resolve()
    if not valid_game(game):raise ValueError('Star Citizen installation was not found')
    folder=(game/'Data/Localization/english').resolve()
    if not folder.is_relative_to(game):raise ValueError('Linked game text folders cannot be repaired automatically')
    cfg=game/'user.cfg'
    for file in [cfg,folder/'global.ini']:
        if file.resolve()!=file or (file.exists() and file.stat().st_nlink>1):
            raise ValueError('Linked game text files cannot be repaired automatically')
    return folder,cfg

def grant(game,sid,profile=PROFILE):
    game=Path(game).resolve()
    if not valid_game(game) or not re.fullmatch(r'S-1-\d+(?:-\d+)+',sid):raise ValueError('Invalid game or Windows identity')
    folder,cfg=text_targets(game)
    # Refuse alternate-administrator credentials: journal belongs to the player.
    identity=subprocess.check_output(['whoami.exe','/user','/fo','csv','/nh'],creationflags=0x08000000)
    if re.search(rb'S-1-\d+(?:-\d+)+',identity).group().decode('ascii')!=sid:raise ValueError('Run permission repair as the same Windows account')
    from game_text_lifecycle import Manager,INI,CFG,read_dacl
    from localization_lock import localization_lock
    manager=Manager(game,profile)
    with localization_lock(game/INI):
        state=manager.state();manager.capture(state,INI);manager.capture(state,CFG)
        folder.mkdir(parents=True,exist_ok=True)
        if not cfg.exists():manager.write(CFG,b'')
        state=manager.state()
        for file in [folder,cfg,folder/'global.ini']:
            if not file.exists():continue
            relative=file.relative_to(game).as_posix()
            entry=state['permissions'].setdefault(relative,dict(original=read_dacl(file)))
            if entry.get('applied') and read_dacl(file)!=entry['applied']:raise ValueError('Permissions changed; review before granting access again')
            manager.store(state)
            # No inheritable/recursive grant to unrelated localization content.
            subprocess.run(['icacls.exe',str(file),'/grant','*'+sid+':M'],check=True,capture_output=True,creationflags=0x08000000)
            entry['applied']=read_dacl(file);manager.store(state)

def request(restore=False):
    game=game_directory(True);text_targets(game)
    identity=subprocess.check_output(['whoami.exe','/user','/fo','csv','/nh'],creationflags=0x08000000)
    sid=re.search(rb'S-1-\d+(?:-\d+)+',identity).group().decode('ascii')
    parameters=subprocess.list2cmdline([str(ROOT/'game_text_access.py'),str(game),sid,str(PROFILE)]+(['--restore'] if restore else []))
    shell=ctypes.windll.shell32.ShellExecuteW
    shell.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_int];shell.restype=ctypes.c_void_p
    code=shell(None,'runas',str(Path(sys.executable).with_name('pythonw.exe')),parameters,str(ROOT),0)
    if not code or code<=32:raise PermissionError('Windows permission request was cancelled')

if __name__=='__main__':
    if '--restore' in sys.argv:
        from game_text_lifecycle import Manager
        identity=subprocess.check_output(['whoami.exe','/user','/fo','csv','/nh'],creationflags=0x08000000)
        if re.search(rb'S-1-\d+(?:-\d+)+',identity).group().decode('ascii')!=sys.argv[2]:raise ValueError('Use the same Windows account')
        Manager(sys.argv[1],Path(sys.argv[3])).restore()
    else:grant(sys.argv[1],sys.argv[2],Path(sys.argv[3]))
