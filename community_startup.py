"""Honor the installer's per-user startup choice in the current Windows session."""
from pathlib import Path
import json
import subprocess
import sys
from installation import ROOT

def owns_shortcut():
    from auto_launch import shortcut_path
    shortcut=shortcut_path()
    if not shortcut.exists():return False
    literal=lambda s:"'"+str(s).replace("'","''")+"'"
    script="[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding;$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+literal(shortcut)+");[PSCustomObject]@{target=$s.TargetPath;arguments=$s.Arguments}|ConvertTo-Json -Compress"
    try:
        value=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],text=True,encoding='utf-8',creationflags=0x08000000,timeout=10))
        from installation import RELEASE,INSTALL_ROOT
        if RELEASE:
            return Path(value.get('target','')).resolve()==(INSTALL_ROOT/'SynthScan.exe').resolve() and value.get('arguments','').strip()=='--watch'
        from auto_launch import python_windowless
        expected=subprocess.list2cmdline(['-B',str(ROOT/'auto_launch.py'),'--watch'])
        return Path(value.get('target','')).resolve()==Path(python_windowless()).resolve() and value.get('arguments')==expected
    except (OSError,ValueError,TypeError,subprocess.SubprocessError):return False

def ensure_watcher():
    from app_lifecycle import instance_running
    if owns_shortcut() and not instance_running('watcher'):
        subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-B',str(ROOT/'native_control.py'),'--watch'],
            cwd=ROOT,creationflags=0x08000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
