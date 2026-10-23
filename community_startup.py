"""Honor the installer's per-user startup choice in the current Windows session."""
from pathlib import Path
import subprocess
import sys
from installation import ROOT

def owns_shortcut():
    from auto_launch import shortcut_path
    shortcut=shortcut_path()
    if not shortcut.exists():return False
    literal=lambda s:"'"+str(s).replace("'","''")+"'"
    script="[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding;$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+literal(shortcut)+");$s.TargetPath"
    try:
        target=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],text=True,encoding='utf-8',creationflags=0x08000000,timeout=10).strip()
        return bool(target) and Path(target).resolve().is_relative_to(ROOT.resolve())
    except (OSError,subprocess.SubprocessError):return False

def ensure_watcher():
    from app_lifecycle import instance_running
    if owns_shortcut() and not instance_running('watcher'):
        subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-B',str(ROOT/'native_control.py'),'--watch'],
            cwd=ROOT,creationflags=0x08000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
