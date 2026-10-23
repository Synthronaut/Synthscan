"""Per-user paths and local game discovery. Never contains a developer profile."""
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PROFILE=Path(os.environ.get('SYNTHSCAN_DATA_DIR',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'SynthScan/native')))
RELEASE=(ROOT/'release.json').exists() or os.environ.get('SYNTHSCAN_RELEASE')=='1'

def valid_game(path):
    path=Path(path)
    return all((path/name).is_file() for name in ('Data.p4k','build_manifest.id','Bin64/StarCitizen.exe'))

def game_directory(required=False):
    candidates=[]
    if os.environ.get('SYNTHSCAN_GAME_DIR'):candidates.append(Path(os.environ['SYNTHSCAN_GAME_DIR']))
    try:candidates.append(Path(json.loads((PROFILE/'installation.json').read_text(encoding='utf-8'))['game_dir']))
    except (OSError,ValueError,KeyError):pass
    log=Path(os.environ.get('APPDATA',''))/'rsilauncher/logs/log.log'
    try:
        text=log.read_text(encoding='utf-8',errors='replace')[-4*1024*1024:]
        paths=re.findall(r'Launching Star Citizen [^\r\n]*? from \(([^)]+)\)',text)
        candidates.extend(Path(p.replace('\\\\','\\')) for p in reversed(paths))
    except OSError:pass
    for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        for folder in ('Program Files/Roberts Space Industries/StarCitizen/LIVE','Roberts Space Industries/StarCitizen/LIVE','RSI/StarCitizen/LIVE','StarCitizen/LIVE'):
            candidates.append(Path(drive+':/')/folder)
    for path in candidates:
        if valid_game(path):return path.resolve()
    if required:raise FileNotFoundError('Select the Star Citizen channel folder containing Data.p4k.')
    return Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE')

def reference_paths():
    game=game_directory(True)
    manifest=json.loads((game/'build_manifest.id').read_text(encoding='utf-8'))
    build=manifest['Data']['BuildId']
    if not re.fullmatch(r'[a-fA-F0-9-]{36}',build):raise ValueError('Invalid game build identity')
    local=PROFILE.parent/'reference'/build
    if RELEASE or (local/'ready.json').exists():
        return dict(game=game,root=local,records=local/'records',career=local/'records',
                    localization=local/'localization/Data/Localization/english/global.ini',audit=local/'reputation_audit.json',
                    schemas=local/'game_services.pb',schema_manifest=local/'game_services_manifest.json')
    return dict(game=game,root=ROOT/'research',records=ROOT/'research/reputation_12913470/records',
                career=ROOT/'research/questing_definitions_12913470',localization=ROOT/'research/local_game_12913470/localization/Data/Localization/english/global.ini',
                audit=ROOT/'research/reputation_12913470/audit.json',schemas=ROOT/'research/game_services.pb',schema_manifest=ROOT/'research/game_services_manifest.json')

def output_root():
    return PROFILE.parent/'reference/active' if RELEASE else ROOT
