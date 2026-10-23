"""One-shot, explicitly requested permission repair; never reads credentials."""
import ctypes
import json
from pathlib import Path
import re
import subprocess
import sys
from installation import ROOT,valid_game,game_directory

def grant(game,sid):
    game=Path(game).resolve()
    if not valid_game(game) or not re.fullmatch(r'S-1-\d+(?:-\d+)+',sid):raise ValueError('Invalid game or Windows identity')
    folder=game/'Data/Localization/english';folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['icacls.exe',str(folder),'/grant','*'+sid+':(OI)(CI)M'],check=True,capture_output=True,creationflags=0x08000000)
    cfg=game/'user.cfg'
    if not cfg.exists():cfg.write_text('',encoding='utf-8')
    for file in [cfg,folder/'global.ini']:
        if file.exists():subprocess.run(['icacls.exe',str(file),'/grant','*'+sid+':M'],check=True,capture_output=True,creationflags=0x08000000)

def request():
    identity=subprocess.check_output(['whoami.exe','/user','/fo','csv','/nh'],creationflags=0x08000000)
    sid=re.search(rb'S-1-\d+(?:-\d+)+',identity).group().decode('ascii')
    parameters=subprocess.list2cmdline([str(ROOT/'game_text_access.py'),str(game_directory(True)),sid])
    shell=ctypes.windll.shell32.ShellExecuteW
    shell.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_int];shell.restype=ctypes.c_void_p
    code=shell(None,'runas',str(Path(sys.executable).with_name('pythonw.exe')),parameters,str(ROOT),0)
    if not code or code<=32:raise PermissionError('Windows permission request was cancelled')

if __name__=='__main__':grant(sys.argv[1],sys.argv[2])
