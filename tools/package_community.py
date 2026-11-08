"""Assemble an allowlisted source tree and self-contained Windows ZIP.

Never copies the development profile, research, screenshots or extracted game cache.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
VERSION='0.1.0-alpha.9'
PRIVATE={'quantum_timer_status.json','quantum_timer_status.json.tmp','quantum_timer_command.json','quantum_timer_command.json.tmp','contract_share_preferences.json','contract_share_preferences.json.tmp','contract_share_status.json','contract_share_status.json.tmp','daylight_preferences.json.tmp','daylight_calibration.json.tmp','daylight_preferences.json','daylight_calibration.json','daylight_catalogue.json.tmp','loginData.json','inventory.json','config.json','region_config.txt','owned_blueprints.txt',
    'blueprints_library.json','blueprints_favorites.json','reputation_snapshot.json','reputation_localization_state.json',
    'server_log.json','shard_history.json','uex_token.dat','uex_key.dat','portable.txt',
    'native_runtime.json','workspace_library.json','launch_target.json','installation.json',
    'reputation_names_preview.json','reputation_labels_status.json','blueprint_strings_status.json','setup_result.json',
    'fabricator_scan_inbox.json','refinery_orders.json','crafting_recipes.json','mining_loadout.json',
    'executive_hangar_sync.json','executive_hangar_verification.json','hangar_hud.json','hangar_hud.png','hangar_hud.png.tmp',
    'compboard_inventory.sqlite3','compboard_inventory.sqlite3-journal',
    'compboard_inventory.sqlite3-wal','compboard_inventory.sqlite3-shm',
    'native_status.json','top_hud_status.json','session_state.json','credentials.json','.env'}
IGNORED={'.git','__pycache__','.venv','node_modules','synthscan-build','build'}
PRIVATE.update({'directory_vehicles.json','item_directory_request.json','item_directory_detail.json','item_directory_catalog.json','data_update_status.json','data_update_command.json','hangar_update_status.json',
    'hangar_update_command.json','hangar_reset_sync.json','catalogue_current.json'})
PRIVATE.update({'update_preferences.json','app_update_status.json','reference_source_status.json','reference_source_current.json',
    'mining_reference.json','mining_reference_status.json','signing-key.dpapi'})
PRIVATE.update({'finder_market_index.json','finder_market_request.json','finder_market_detail.json','finder_market_cache'})
PRIVATE.add('session_ribbon.json')
PRIVATE.add('session_overview.json')
PRIVATE.add('home_status.json')
PRIVATE.update({'refinery_orders.txt','refinery_orders.txt.tmp'})
PRIVATE.add('daylight_embed_request.json')


def copy_tree(source,destination):
    def ignore(folder,names):return [n for n in names if n in IGNORED or n in PRIVATE or n.endswith(('.pyc','.pdb','.obj','.log'))]
    shutil.copytree(source,destination,dirs_exist_ok=True,ignore=ignore)


def stage_source(destination):
    destination=Path(destination).resolve()
    if destination==ROOT or ROOT.is_relative_to(destination):raise ValueError('Unsafe output folder')
    if destination.exists():raise FileExistsError('Choose a new staging directory')
    destination.mkdir(parents=True)
    for file in ROOT.glob('*.py'):
        if file.name.startswith('test_') or file.name=='make_shortcut.py':continue
        shutil.copy2(file,destination/file.name)
    for name in ['LICENSES.md','README.md','CHANGELOG.md','PRIVACY.md','SECURITY.md','BUILDING.md','requirements-release.lock','DISTRIBUTION.md','SERVER_HISTORY.md','update_trust.json','.gitignore']:
        shutil.copy2(ROOT/name,destination/name)
    shutil.copy2(ROOT/'native/synthscan/LICENSE',destination/'LICENSE')
    for name in ['synthscan','mining_worker']:copy_tree(ROOT/'native'/name,destination/'native'/name)
    for name in ['synthscan-upstream.json','launcher.cpp','launcher.rc']:shutil.copy2(ROOT/'native'/name,destination/'native'/name)
    copy_tree(ROOT/'tools',destination/'tools')
    copy_tree(ROOT/'installer',destination/'installer')
    (destination/'tests').mkdir()
    for file in (ROOT/'tests').glob('*.py'):shutil.copy2(file,destination/'tests'/file.name)
    for name in ['bedrock','starbreaker','game_artwork','presentmon','executive_hangar','versetime']:copy_tree(ROOT/'third_party'/name,destination/'third_party'/name)
    for name in ['opencv_download.json','zstd_source.json','vc_runtime.json','vc_runtime_NOTICE.txt']:
        target=destination/'third_party/build_tools'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'third_party/build_tools'/name,target)
    (destination/'data').mkdir()
    for file in (ROOT/'data').iterdir():
        if file.is_file() and file.name not in PRIVATE and not file.name.startswith('local_'):shutil.copy2(file,destination/'data'/file.name)
    (destination/'assets').mkdir()
    (destination/'docs').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'docs/material-quality-values.md',destination/'docs/material-quality-values.md')
    shutil.copy2(ROOT/'docs/shopping-list-plan.md',destination/'docs/shopping-list-plan.md')
    shutil.copy2(ROOT/'assets/snare_watch.wav',destination/'assets/snare_watch.wav')
    copy_tree(ROOT/'assets/branding',destination/'assets/branding')
    if (ROOT/'.github').exists():copy_tree(ROOT/'.github',destination/'.github')
    (destination/'release.json').write_text(json.dumps(dict(version=VERSION,channel='community-alpha',updater_schema=1,setup_schema=1)),encoding='utf-8')
    audit(destination)
    return destination


def audit(destination):
    import re
    files=list(destination.rglob('*'))
    for file in files:
        if not file.is_file():continue
        if file.name in PRIVATE or file.suffix.lower()=='.dpapi':raise ValueError('Private file included: '+str(file.relative_to(destination)))
        relative=file.relative_to(destination)
        if relative.parts[0] in ('research','backups','release-validation','voice_cache'):
            raise ValueError('Development data included: '+str(relative))
        if file.suffix.lower() in ('.py','.json','.md','.txt','.yml','.yaml','.ini','.cfg'):
            text=file.read_text(encoding='utf-8',errors='replace')
            if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})',text):
                raise ValueError('Potential credential in '+str(relative))
    return len([p for p in files if p.is_file()])


def archive_package(destination):
    destination=Path(destination).resolve()
    audit(destination)
    integrity=destination/'release_integrity.json'
    manifest={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(destination.rglob('*')) if p.is_file() and p!=integrity}
    integrity.write_text(json.dumps(dict(version=VERSION,files=manifest),indent=2),encoding='utf-8')
    zip_path=destination.with_suffix('.zip')
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(destination.rglob('*')):
            if file.is_file():archive.write(file,Path('SynthScan')/file.relative_to(destination))
    digest=hashlib.sha256(zip_path.read_bytes()).hexdigest()
    zip_path.with_suffix('.zip.sha256').write_text(digest+'  '+zip_path.name+'\n',encoding='ascii')
    print(json.dumps(dict(archive=str(zip_path),sha256=digest,bytes=zip_path.stat().st_size)))


def package(source,destination,runtime,native):
    source,destination,runtime,native=map(lambda p:Path(p).resolve(),(source,destination,runtime,native))
    if destination.exists():raise FileExistsError('Choose a fresh package folder')
    copy_tree(source,destination)
    # No developer site-packages, pip caches, user site or PATH dependency.
    for folder in ['Lib','DLLs','tcl']:
        def ignore(directory,names):return [n for n in names if n in ('site-packages','__pycache__','test','tests','idle_test') or n.endswith('.pyc')]
        shutil.copytree(runtime/folder,destination/'runtime'/folder,ignore=ignore)
    for name in ['python.exe','pythonw.exe','python3.dll','python314.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt']:
        shutil.copy2(runtime/name,destination/'runtime'/name)
    (destination/'runtime/python314._pth').write_text('..\n.\nLib\nDLLs\nLib/site-packages\nimport site\n',encoding='utf-8')
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-compile','--require-hashes',
                    '--target',str(destination/'runtime/Lib/site-packages'),'-r',str(source/'requirements-release.lock')],check=True)
    target=destination/'dist/native';target.mkdir(parents=True)
    for file in native.iterdir():
        if file.is_file() and file.name not in ('native_runtime.json','workspace_library.json'):
            shutil.copy2(file,target/file.name)
    from tools.build_native_app import MSVC,SDK,VERSION as SDK_VERSION
    env=__import__('os').environ.copy()
    env['PATH']=str(MSVC/'bin/Hostx64/x64')+__import__('os').pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[MSVC/'include',SDK/'Include'/SDK_VERSION/'ucrt',SDK/'Include'/SDK_VERSION/'shared',SDK/'Include'/SDK_VERSION/'um']))
    env['LIB']=';'.join(map(str,[MSVC/'lib/x64',SDK/'Lib'/SDK_VERSION/'ucrt/x64',SDK/'Lib'/SDK_VERSION/'um/x64']))
    obj=destination/'launcher.obj'
    resource=destination/'launcher.res'
    subprocess.run([str(SDK/'bin'/SDK_VERSION/'x64/rc.exe'),'/nologo','/fo',str(resource),str(source/'native/launcher.rc')],env=env,check=True,cwd=source/'native')
    subprocess.run([str(MSVC/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++17','/EHsc','/MT','/O2',
        str(source/'native/launcher.cpp'),str(resource),'/Fo'+str(obj),'/Fe'+str(destination/'SynthScan.exe'),
        '/link','/SUBSYSTEM:WINDOWS','/LIBPATH:'+str(MSVC/'lib/x64'),'user32.lib'],env=env,check=True,cwd=destination)
    obj.unlink(missing_ok=True)
    resource.unlink(missing_ok=True)
    from tools.fetch_vc_runtime import bundle
    bundle(destination)
    # Integrity checks cover everything that will be distributed (not private runtime files).
    archive_package(destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--package',type=Path)
    parser.add_argument('--python-home',type=Path,default=Path(sys.base_prefix))
    parser.add_argument('--native',type=Path,default=ROOT/'dist/community-stage')
    args=parser.parse_args()
    source=stage_source(args.source)
    if args.package:package(source,args.package,args.python_home,args.native)
