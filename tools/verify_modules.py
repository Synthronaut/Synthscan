"""Validate real packaged module assemblies in their own isolated profiles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import config,write
from feature_modules import FEATURES,installed,resolve
from module_distribution import catalog,check_sequence,selection_token,activation_payload
from module_setup import verify_runtime


def selection_matrix():
    """Every single feature and every removal, including dependency removal."""
    cases=[[],['server_hud','hangars'],['people'],['synthstrings'],list(FEATURES)]
    for name in FEATURES:
        cases.append(resolve([name]))
        removed={name}
        while True:
            dependents={key for key,row in FEATURES.items() if set(row[1])&removed}
            if dependents<=removed:break
            removed.update(dependents)
        cases.append([key for key in FEATURES if key not in removed])
    unique={tuple(sorted(row)):sorted(row) for row in cases}
    return list(unique.values())


def startup(target,profile):
    """Run the real native host and bridge with a synthetic game, never user data."""
    from app_lifecycle import game_process_ids
    if game_process_ids():raise ValueError('Close Star Citizen before native startup verification')
    from native_control import native_running
    if native_running():raise ValueError('Another SynthScan app is running; packaged startup checks will not stop it')
    target=Path(target).resolve();profile=Path(profile).resolve();game=profile/'fixture-game';(game/'Bin64').mkdir(parents=True,exist_ok=True)
    (game/'Data.p4k').write_bytes(b'not-a-game-archive')
    (game/'Bin64/StarCitizen.exe').write_bytes(b'fixture')
    (game/'Game.log').write_text('',encoding='utf-8')
    write(game/'build_manifest.id',dict(Data=dict(BuildId='00000000-0000-4000-8000-000000000001',Branch='fixture',RequestedP4ChangeNum=1)))
    write(profile/'installation.json',dict(game_dir=str(game)))
    write(profile/'capture_privacy.json',dict(schema=1,paused=True,pause_unfocused=True,account_access=False))
    (profile/'region_config.txt').write_text('gamelog='+str(game/'Game.log')+'\ngametexts=0\nlive=0\n',encoding='utf-8')
    env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(profile),SYNTHSCAN_GAME_DIR=str(game))
    (target/'validation-install.txt').write_text(str(profile),encoding='utf-8')
    if 'synthstrings' not in installed(target):
        write(profile/'game_text/retained/guard_status.json',dict(schema=1,state='attention',title='Removed module stale warning',detail='Synthetic retained record'))
    retained=profile/'retained_record.json';retained.write_bytes(b'{"fixture":"keep"}')
    write(target/'dist/native/native_runtime.json',dict(workspace=str(target),pythonw=str(target/'runtime/pythonw.exe')))
    from update_agent import ready,stop_native
    process=subprocess.Popen([str(target/'dist/native/SynthScan.exe'),'--autostart'],env=env,cwd=target/'dist/native',creationflags=0x08000000)
    try:
        if not ready(target,profile,timeout=75):
            log=profile/'bridge.log'
            detail=log.read_text(encoding='utf-8',errors='replace')[-5000:] if log.exists() else 'No bridge log. Native exit: '+str(process.poll())
            raise ValueError('Native host/bridge did not become ready for '+str(target)+'\n'+detail)
        state=json.loads((profile/'session_state.json').read_text(encoding='utf-8'))
        assert state['owner_pid']==process.pid
        assert state['game_pids']==[]
        selected=installed(target)
        if 'synthstrings' not in selected:
            assert not state['home'].get('synthstrings')
            assert not list((profile/'game_text/requests').glob('*.json'))
        if not selected&{'synthstrings','missions'}:assert not state.get('reputation_notice')
        if 'mining_tools' not in selected:assert not state['home'].get('refinery_notice')
        if 'server_hud' in selected:
            deadline=time.monotonic()+12;top={}
            while time.monotonic()<deadline:
                try:top=json.loads((profile/'top_hud_status.json').read_text(encoding='utf-8'))
                except (OSError,ValueError):pass
                if top.get('owner_pid')==process.pid:break
                time.sleep(.1)
            assert top.get('owner_pid')==process.pid,'Server HUD failed to report readiness'
            assert top['region_history_available']==('server_history' in selected)
        assert retained.read_bytes()==b'{"fixture":"keep"}'
    finally:
        stop_native(target/'dist/native/SynthScan.exe');process.wait(timeout=30)


def verify(payload,output=None):
    payload=Path(payload).resolve();trust=config(payload/'core');raw=(payload/'synthscan-modules.json').read_bytes();value=catalog(raw,trust)
    catalog_hash=hashlib.sha256(raw).hexdigest();report=[]
    with tempfile.TemporaryDirectory(prefix='SynthScan-module-validation-') as temporary:
        base=Path(temporary);profile=base/'profile';folder=profile/'updates';folder.mkdir(parents=True)
        # Cache only verified release assets, never a user's profile or settings.
        cache=folder/'modules-cache';cache.mkdir()
        for name,item in value['packages'].items():shutil.copy2(payload/('SynthScan-module-'+name+'.zip'),cache/(item['sha256']+'.zip'))
        (folder/('catalog-'+catalog_hash+'.json')).write_bytes(raw)
        write(folder/'catalog-sequence.json',check_sequence(folder,value,raw))
        selections=selection_matrix()
        for number,selected in enumerate(selections):
            target=base/('selection-'+str(number));target.mkdir()
            pending=dict(kind='modules',sha256=selection_token(catalog_hash,selected),catalog=catalog_hash,modules=selected)
            _,unpack=activation_payload(payload/'core',profile,pending,trust);unpack(target)
            write(target/'dist/native/native_runtime.json',dict(workspace=str(target),pythonw=str(target/'runtime/pythonw.exe')))
            env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(profile))
            # Running this verifier as a separate interpreter keeps its imports
            # anchored to each assembly and avoids the developer's site packages.
            probe="import sys;sys.path.insert(0,sys.argv[1]);import module_ui;from module_setup import verify_runtime;verify_runtime(sys.argv[1])"
            subprocess.run([str(target/'runtime/python.exe'),'-I','-B','-c',probe,str(target)],env=env,check=True,timeout=90,creationflags=0x08000000)
            if not selected or set(selected)==set(FEATURES):
                result=subprocess.run([str(target/'dist/native/SynthScan.exe'),'--selftest'],env=env,cwd=target/'dist/native',capture_output=True,text=True,timeout=180,creationflags=0x08000000)
                if result.returncode:raise ValueError('Native selftest failed for '+str(selected)+': '+result.stdout[-6000:])
            assert installed(target)==set(selected)
            # The actual capture stack must import and infer in the Full tree;
            # it must be undiscoverable in every screen-free selection.
            probe="""
import sys,importlib.util
sys.path.insert(0,sys.argv[1])
from feature_modules import enabled
for name in ('windows_capture','mss','onnxruntime','rapidocr_onnxruntime','PIL','native_mining','textline_ocr','screen_readers'):
 assert importlib.util.find_spec(name) is None,name
"""
            subprocess.run([str(target/'runtime/python.exe'),'-I','-B','-c',probe,str(target)],env=env,cwd=target,check=True,timeout=90,creationflags=0x08000000)
            startup(target,base/('startup-profile-'+str(number)))
            report.append(dict(modules=selected,edition='full' if 'mining_recognition' in selected else 'standard',runtime_verified=True,native_bridge_ready=True))
            print(f'Verified packaged selection {number+1}/{len(selections)}: {selected or ["Core"]}',flush=True)
    if output:Path(output).write_text(json.dumps(dict(version=value['version'],selections=report),indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);parser.add_argument('--output');args=parser.parse_args()
    print(json.dumps(verify(args.payload,args.output),indent=2))
