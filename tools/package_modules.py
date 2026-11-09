"""Split verified Standard/Full builds into one selectable offline installer.

Shared native UI/calculations and catalog infrastructure stay in Core. Feature
providers/resources install separately. Recognition exclusively owns the Full
engine and capture/OCR dependencies; it is never in the screen-free Core.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import config, digest
from feature_modules import FEATURES
from module_distribution import inspect_package, catalog, REPLACEMENTS
from update_signing import envelope, private_key, signature

# Runtime entry points/resources, rather than copies of player data. Some
# algorithms are deliberately shared by multiple features and remain in Core.
OWNERS = {
    'synthstrings': {'strings_settings.py','blueprint_strings.py'},
    'mining_tools': {'mining_diary.py','rock_navigation.py','position_capture.py','mining_planner_ui.py','mining_planner.py','mining_setup_ui.py'},
    'blueprints': {'crafting_db.py'},
    'item_finder': {'game_library_ui.py'},
    'server_hud': {'native_session_hud.py','region_history_hud.py','native_timing.py','frame_telemetry.py','network_protocol.py',
        'tools/live_network_probe.py','tools/analyze_game_network.py','third_party/presentmon/PresentMon-2.6.0-x64.exe','third_party/presentmon/LICENSE.txt','third_party/presentmon/provenance.json'},
    'server_history': {'server_log_manager.py','SERVER_HISTORY.md'},
    'people': {'companion_features.py','companion_toasts.py','party_invites.py'},
    'piracy': {'piracy_watch.py','snare_alert_ui.py','assets/snare_watch.wav'},
    'missions': {'mission_hud.py','mission_log.py','mission_log_service.py','mission_log_report.py','mission_capture.py'},
    'hangars': {'executive_hangar.py','executive_hangar_hud.py','hangar_card.py','hangar_verification.py','hangar_reset_feed.py','compboard_inventory.py','data/executive_hangar_schedule.json'},
    'daylight': {'daylight.py','daylight_catalogue.py','daylight_planner.py','data/daylight_catalogue.json'},
    'acceptance': {'contract_share.py','contract_share_helper.py'},
    # Notes are implemented in the shared native UI, with no background process.
    # Their pack carries its signed capability declaration; no dedicated native
    # DLL or resource-saving claim is made for this small feature.
    'notes': set(),
}
RETIRED = {'main.py','detector.py','telemetry_hud.py','blueprint_library_ui.py',
    'telemetry_hud.py','overlay.py','performance_lab_ui.py','performance_lab.py',
    'terminal_tracking_ui.py','radar_db.py','voice.py','native_displayinfo_bindings.py',
    'mining_planner_ui.py','mining_setup_ui.py','game_library_ui.py'}


def production_file(relative):
    parts=Path(relative).parts
    if relative=='tools/live_network_probe.py':return True # Explicit optional runtime timing helper.
    if relative=='tools/release_downloads.py':return False # Publisher-only public counter report.
    if relative in RETIRED or parts[0] in ('tests','.github','installer'):return False
    if relative.startswith(('native/synthscan/','native/mining_worker/','third_party/build_tools/')):return False
    if relative in ('native/launcher.cpp','native/launcher.rc'):return False
    # Public source is published separately. Runtime reference/extraction tools
    # are retained; developer capture probes and benchmarks are not shipped.
    if parts[0]=='tools' and (any(s in Path(relative).stem.lower() for s in ('probe','benchmark','test_','build_','package_','sign_','configure_','verify_','fetch_','trace_'))):return False
    return True


def write_component(folder,name,version,output,url_base):
    files={p.relative_to(folder).as_posix():digest(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    manifest=dict(schema=1,id=name,version=version,files=files)
    (folder/'component.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':')),encoding='utf-8')
    path=output/('SynthScan-module-'+name+'.zip')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(folder.rglob('*')):
            if p.is_file():archive.write(p,'SynthScan/'+p.relative_to(folder).as_posix())
    with zipfile.ZipFile(path) as archive:unpacked=sum(i.file_size for i in archive.infolist())
    item=dict(id=name,version=version,size=path.stat().st_size,unpacked_size=unpacked,
        sha256=digest(path),inventory_sha256=digest(folder/'component.json'),url=url_base+'/'+path.name,
        requires=[] if name=='core' else list(FEATURES[name][1]))
    inspect_package(path,item)
    return item


def build(standard,full,output,url_base,key_file=None,sequence=None):
    standard=Path(standard).resolve();full=Path(full).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError('Choose a fresh module output folder')
    for path in (standard,full):
        from tools.package_community import audit
        audit(path)
        inventory=json.loads((path/'release_integrity.json').read_text())['files']
        for relative,expected in inventory.items():
            if digest(path/relative)!=expected:raise ValueError('Input build changed: '+relative)
    a=json.loads((standard/'release.json').read_text());b=json.loads((full/'release.json').read_text())
    if a['version']!=b['version'] or a.get('edition')!='standard' or b.get('edition')!='full':raise ValueError('Matched Standard and Full builds are required')
    output.mkdir(parents=True);version=a['version'];trees=output/'trees';trees.mkdir()
    destinations={name:trees/name for name in ('core',*FEATURES)}
    for folder in destinations.values():folder.mkdir()
    reverse={relative:name for name,files in OWNERS.items() for relative in files}
    standard_files={p.relative_to(standard).as_posix() for p in standard.rglob('*') if p.is_file()}
    full_files={p.relative_to(full).as_posix() for p in full.rglob('*') if p.is_file()}
    core_release=dict(a,module_schema=1,modules=[],selection_configured=False)
    for relative in sorted(standard_files):
        if relative in ('release_integrity.json','release.json','edition.txt') or not production_file(relative):continue
        name=reverse.get(relative,'core');target=destinations[name]/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(standard/relative,target)
    # The completed native application performs recognition directly using its
    # embedded model and shared OpenCV DLL. Legacy Python OCR/capture stacks are
    # not part of this runtime: shipping a second reader adds size and attack
    # surface without supplying an active feature.
    for relative in sorted(REPLACEMENTS):
        if relative in ('release_integrity.json','release.json','edition.txt') or not production_file(relative):continue
        target=destinations['mining_recognition']/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(full/relative,target)
    (destinations['core']/'release.json').write_text(json.dumps(core_release),encoding='utf-8')
    for name,(label,requires,capabilities,detail) in FEATURES.items():
        path=destinations[name]/'features'/(name+'.json');path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(dict(schema=1,id=name,label=label,requires=requires,capabilities=capabilities,description=detail,shared_native_ui=True)),encoding='utf-8')
    packages={name:write_component(folder,name,version,output,url_base) for name,folder in destinations.items()}
    trust=config(standard);now=time.time()
    payload=dict(schema=1,kind='modules',platform='windows-x64',version=version,sequence=sequence or time.time_ns()//1000000,
        minimum_manager=1,issued_at=now,expires_at=now+365*86400,packages=packages)
    private=base64.b64decode(os.environ['SYNTHSCAN_SIGNING_PRIVATE_B64'],validate=True) if os.environ.get('SYNTHSCAN_SIGNING_PRIVATE_B64') else private_key(key_file or Path(os.environ['LOCALAPPDATA'])/'SynthScanRelease/signing-key.dpapi')
    public=None
    for encoded in trust['keys'].values():
        candidate=base64.b64decode(encoded,validate=True)
        try:signature(candidate,b'SynthScan module catalog',signature(private,b'SynthScan module catalog'));public=candidate;break
        except ValueError:continue
    if public is None:raise ValueError('Signing key does not match this build')
    raw=(json.dumps(envelope(payload,private,public),indent=2)+'\n').encode('utf-8');catalog(raw,trust)
    (output/'synthscan-modules.json').write_bytes(raw)
    # The stable bootstrap's recovery runtime is screen-free Core only.
    core=output/'core';shutil.copytree(destinations['core'],core);(core/'component.json').unlink()
    integrity={p.relative_to(core).as_posix():digest(p) for p in sorted(core.rglob('*')) if p.is_file()}
    (core/'release_integrity.json').write_text(json.dumps(dict(version=version,files=integrity)),encoding='utf-8')
    report=dict(version=version,core_bytes=packages['core']['size'],all_download_bytes=sum(p['size'] for p in packages.values()),packages=packages)
    (output/'module-build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--standard',required=True);parser.add_argument('--full',required=True);parser.add_argument('--output',required=True);parser.add_argument('--url-base',required=True);args=parser.parse_args()
    print(json.dumps(build(args.standard,args.full,args.output,args.url_base),indent=2))
