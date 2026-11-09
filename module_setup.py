"""Offline installer configuration and safe optional-feature cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

from app_updates import (activate,active_token,config,digest,load,safe_member,
                         safe_remove,write)
from feature_modules import installed,resolve
from module_distribution import (catalog,check_sequence,inspect_package,
                                 selection_token)


def refresh_recovery_core(root,profile,active):
    """Keep the stable recovery tree screen-free, including legacy migrations.

    Only recorded app files may be replaced/removed. A failed copy restores
    their original bytes before the outer activation rolls its pointer back.
    """
    root=Path(root).resolve();active=Path(active).resolve();folder=Path(profile)/'updates'
    lock=load(active/'module_lock.json');catalog_hash=lock.get('catalog','')
    if len(catalog_hash)!=64:raise ValueError('No verified module receipt for recovery refresh')
    raw=(folder/('catalog-'+catalog_hash+'.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=catalog_hash:raise ValueError('Recovery catalog changed')
    value=catalog(raw,config(active));item=value['packages']['core'];archive=folder/'modules-cache'/(item['sha256']+'.zip')
    inventory=inspect_package(archive,item)['files'];previous=load(root/'release_integrity.json').get('files',{})
    if not previous:raise ValueError('Existing app recovery tree has no ownership inventory; run the unified installer to repair it')
    if shutil.disk_usage(root).free<item['unpacked_size']*2+128*1024*1024:raise OSError('Not enough free space to safely refresh recovery files')
    incoming=root/('.recovery-incoming-'+uuid.uuid4().hex);backup=root/('.recovery-backup-'+uuid.uuid4().hex)
    incoming.mkdir();backup.mkdir();changed=[];removed=[];safe_cleanup=False
    try:
        inspect_package(archive,item,incoming)
        targets=dict(inventory)
        write(incoming/'release_integrity.json',dict(version=value['version'],files=inventory))
        targets['release_integrity.json']=digest(incoming/'release_integrity.json')
        # Preflight every replacement/deletion before the first mutation.
        for relative,expected in {**previous,**targets}.items():
            safe_member('SynthScan/'+relative);path=root/relative
            if path.exists() and (path.is_symlink() or not path.resolve().is_relative_to(root)):raise ValueError('Linked app file preserved: '+relative)
            if path.exists() and relative!='release_integrity.json':
                actual=digest(path)
                if actual not in {previous.get(relative),targets.get(relative)}:raise ValueError('Externally changed app file preserved: '+relative)
        entrypoints={'app_launcher.py','app_updates.py','module_setup.py','release.json','release_integrity.json'}
        order=sorted(targets,key=lambda name:(name in entrypoints,name=='release_integrity.json',name))
        for relative in order:
            path=root/relative
            if path.exists() and digest(path)==targets[relative]:continue
            saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():shutil.copy2(path,saved)
            changed.append(relative);path.parent.mkdir(parents=True,exist_ok=True)
            from app_updates import replace_file
            replace_file(incoming/relative,path)
        for relative in previous.keys()-inventory.keys():
            if relative=='release_integrity.json':continue
            path=root/relative
            if path.exists():
                saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,saved)
                removed.append(relative);path.unlink()
        safe_cleanup=True
    except Exception:
        from app_updates import replace_file
        for relative in reversed(changed+removed):
            saved=backup/relative;path=root/relative
            if saved.exists():replace_file(saved,path)
            else:path.unlink(missing_ok=True)
        safe_cleanup=True
        raise
    finally:
        safe_remove(incoming,root)
        if safe_cleanup:safe_remove(backup,root)


def deactivate_strings(profile):
    from game_text_lifecycle import Manager
    channels=set()
    for journal in (Path(profile)/'game_text').glob('*/journal.json'):
        state=load(journal)
        if state.get('game'):channels.add(state['game'])
    recorded=load(Path(profile)/'installation.json').get('game_dir')
    if recorded:channels.add(recorded)
    results={}
    for channel in channels:results[channel]=Manager(channel,profile).restore()
    write(Path(profile)/'module_text_cleanup.json',dict(at=time.time(),channels=results))
    failures=[name for name,result in results.items() if result.get('conflicts') or result.get('permissions_pending')]
    if failures:raise ValueError('SynthStrings removal preserved externally edited text or permissions. Open Setup → Remove SynthStrings to review before removing this module.')
    path=Path(profile)/'region_config.txt'
    if path.exists():
        lines=path.read_text(encoding='utf-8').splitlines()
        path.write_text('\n'.join([v for v in lines if not v.startswith('gametexts=')]+['gametexts=0'])+'\n',encoding='utf-8')
    setup=load(Path(profile)/'setup_result.json')
    if setup:
        setup.update(strings_enabled=False,strings_installed=False)
        write(Path(profile)/'setup_result.json',setup)


def deactivate_removed(previous,profile):
    from feature_modules import ROOT
    from app_lifecycle import game_process_ids
    if game_process_ids():raise ValueError('Close Star Citizen before changing installed features')
    if 'synthstrings' in installed(previous) and 'synthstrings' not in installed(ROOT):deactivate_strings(profile)


def cleanup_legacy_root(root,previous_inventory):
    """Remove only publisher-owned obsolete app files, never player records."""
    root=Path(root).resolve();current=load(root/'release_integrity.json').get('files',{})
    previous=load(previous_inventory).get('files',{}) if previous_inventory else {}
    from native_workspace_data import PLAYER_FILES
    protected=set(PLAYER_FILES)|{'region_config.txt','credentials.json','config.json','loginData.json','owned_blueprints.txt','personal_notes.txt','notes.txt'}
    for relative,expected in previous.items():
        safe_member('SynthScan/'+relative)
        if relative in current or any(p in protected for p in Path(relative).parts):continue
        path=root/relative
        if path.exists():
            if path.is_symlink() or not path.resolve().is_relative_to(root) or digest(path)!=expected:
                raise ValueError('An older app file has external changes and was preserved: '+relative)
            path.unlink()


def prune_removed_readers(root,profile,active):
    """A removed reader must not remain in a previous Full app or download cache."""
    root=Path(root).resolve();active=Path(active).resolve()
    refresh_recovery_core(root,profile,active)
    write(Path(profile)/'module_selection.json',dict(schema=1,modules=sorted(installed(active))))
    if 'mining_recognition' in installed(active):return
    versions=root/'versions'
    if versions.exists():
        for path in versions.iterdir():
            if path.resolve()!=active and len(path.name)==64 and load(path/'release.json').get('edition')=='full' and (path/'release_integrity.json').is_file():safe_remove(path,versions)
    folder=Path(profile)/'updates'
    for path in folder.glob('catalog-*.json'):
        try:
            value=catalog(path.read_bytes(),config(active));item=value['packages']['mining_recognition']
            (folder/'modules-cache'/(item['sha256']+'.zip')).unlink(missing_ok=True)
        except (OSError,ValueError):pass


def verify_runtime(target):
    """No windows or game input: import the selected services in bundled Python."""
    script="""
import pathlib,sys,json
sys.path.insert(0,sys.argv[1])
import native_bridge,app_updates,module_distribution,feature_modules
from feature_modules import enabled
if enabled('server_hud'):import native_session_hud,hud_controller
if enabled('missions'):import mission_log_service,mission_hud
if enabled('people'):import companion_features
if enabled('hangars'):import hangar_card
if enabled('acceptance'):import contract_share_helper
if enabled('daylight'):import daylight_planner
if enabled('mining_tools'):import mining_planner,rock_navigation
if enabled('item_finder'):import finder_market
from native_control import validate_binary
validate_binary()
"""
    subprocess.run([str(Path(target)/'runtime/python.exe'),'-I','-B','-c',script,str(target)],cwd=target,check=True,timeout=60,
        creationflags=0x08000000 if os.name=='nt' else 0)
    return True


def install_offline(root,profile,source,selected,previous_inventory=None):
    root=Path(root).resolve();profile=Path(profile).resolve();source=Path(source).resolve()
    selected=resolve(selected);trust=config(root);raw=(source/'synthscan-modules.json').read_bytes();value=catalog(raw,trust)
    catalog_hash=hashlib.sha256(raw).hexdigest();folder=profile/'updates';folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'modules-cache';cache.mkdir(exist_ok=True)
    # Check everything before committing a choice or extracting any component.
    for name in ('core',*selected):inspect_package(source/('SynthScan-module-'+name+'.zip'),value['packages'][name])
    sequence=check_sequence(folder,value,raw)
    for name in ('core',*selected):
        item=value['packages'][name];target=cache/(item['sha256']+'.zip')
        if not target.exists() or digest(target)!=item['sha256']:shutil.copy2(source/('SynthScan-module-'+name+'.zip'),target)
    (folder/('catalog-'+catalog_hash+'.json')).write_bytes(raw);write(folder/'catalog-sequence.json',sequence)
    token=selection_token(catalog_hash,selected)
    write(folder/'pending.json',dict(schema=1,kind='modules',sha256=token,catalog=catalog_hash,modules=selected,version=value['version']))
    cleanup_legacy_root(root,previous_inventory)
    if 'synthstrings' not in selected and (profile/'game_text').exists():deactivate_strings(profile)
    result=activate(root,root,profile,verify_runtime,lambda *args:None,trust)
    prune_removed_readers(root,profile,root/'versions'/token)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path);parser.add_argument('--profile',type=Path)
    parser.add_argument('--offline',type=Path);parser.add_argument('--selected',default='');parser.add_argument('--previous-inventory',type=Path)
    parser.add_argument('--deactivate-removed',type=Path);parser.add_argument('--prune',type=Path)
    args=parser.parse_args()
    from installation import PROFILE
    profile=args.profile or PROFILE
    try:
        if args.deactivate_removed:deactivate_removed(args.deactivate_removed,profile)
        elif args.prune:prune_removed_readers(args.root,profile,args.prune)
        else:install_offline(args.root,profile,args.offline,[n for n in args.selected.split(',') if n and n!='core'],args.previous_inventory)
    except Exception as error:
        write(Path(profile)/'module_install_error.json',dict(at=time.time(),detail=str(error)))
        raise


if __name__=='__main__':main()
