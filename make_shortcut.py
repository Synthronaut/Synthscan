import subprocess, os

# Remove old bat if present
old_bat = r"C:\Users\Dev\Documents\SynthScan\Start_StarScan.bat"
if os.path.exists(old_bat):
    os.remove(old_bat)

ps = """
$ws = New-Object -ComObject WScript.Shell
$desktop = [System.Environment]::GetFolderPath('Desktop')
$s = $ws.CreateShortcut([System.IO.Path]::Combine($desktop, 'SynthScan.lnk'))
$s.TargetPath = 'C:\\Users\\Dev\\Documents\\SynthScan\\Start_SynthScan.bat'
$s.WorkingDirectory = 'C:\\Users\\Dev\\Documents\\SynthScan'
$s.Description = 'SynthScan - Star Citizen Radar Scout & Refinery Ore Vault'
$s.Save()
"""
res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
print("Desktop shortcut SynthScan.lnk return code:", res.returncode)
