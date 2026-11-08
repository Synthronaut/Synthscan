"""Update existing SynthScan shortcut artwork without changing its launch target."""
from pathlib import Path
import subprocess
import ctypes

ROOT=Path(__file__).resolve().parents[1]


def main():
    icon=ROOT/'assets/branding/SynthScan-Blue.ico'
    if not icon.is_file():raise FileNotFoundError(icon)
    literal=lambda value:"'"+str(value).replace("'","''")+"'"
    script="\n".join([
        "$ErrorActionPreference='Stop'",
        "$desktop=[Environment]::GetFolderPath('Desktop')",
        "$path=Join-Path $desktop 'SynthScan.lnk'",
        "if(-not(Test-Path -LiteralPath $path)){throw 'SynthScan desktop shortcut not found'}",
        "$shell=New-Object -ComObject WScript.Shell",
        "$link=$shell.CreateShortcut($path)",
        f"$link.IconLocation={literal(str(icon)+',0')}",
        "$link.Save()",
        "$check=$shell.CreateShortcut($path)",
        "$check.IconLocation",
    ])
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if str(icon).casefold() not in result.stdout.casefold():raise RuntimeError('Shortcut icon was not saved')
    ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
    print('SynthScan desktop shortcut icon updated; launch target preserved.')


if __name__=='__main__':main()
