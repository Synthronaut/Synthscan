"""Exercise real native module controls with synthetic, isolated profiles.

No updater, account calls, installer registration or player records are used.
The native UI fixture refuses to run while Star Citizen is open.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_lifecycle import game_process_ids
from feature_modules import FEATURES
from tools.verify_modules import selection_matrix


ACTIONS={'synthstrings':['strings_settings','strings_details'],
         'mining_tools':['planner','diary','refinery','bookmarks'],
         'mining_recognition':['hud_mining','mining'],
         'blueprints':['blueprints'],'item_finder':['directory','hud_finder'],
         'server_history':['servers'],'people':['people'],'piracy':['hud_piracy'],
         'missions':['mission_log','hud_missions'],'hangars':['executive_hangar','hud_hangars'],
         'daylight':['daylight'],'acceptance':['acceptance']}


def verify(standard,full,output):
    if game_process_ids():raise RuntimeError('Close Star Citizen before UI fixtures')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);report=[]
    for number,selected in enumerate(selection_matrix()):
        case=output/f'case-{number:02d}';native=case/'dist/native';native.mkdir(parents=True)
        source=Path(full if 'mining_recognition' in selected else standard).resolve()
        for file in source.iterdir():
            if file.suffix.lower() not in ('.exe','.dll'):continue
            try:os.link(file,native/file.name)
            except OSError:shutil.copy2(file,native/file.name)
        (case/'release.json').write_text(json.dumps(dict(module_schema=1,modules=selected,edition='full' if 'mining_recognition' in selected else 'standard')))
        profile=case/'data';profile.mkdir()
        # Simulate an existing player removing features, with stale warnings and
        # an unavailable saved mode. Never copy records from the normal profile.
        (profile/'native_settings.json').write_text(json.dumps(dict(hud_mode='mining',scan_on_launch=True,activity_expanded=True,session_strip=True,snare_alerts=True)))
        record=profile/'retained_record.json';record.write_bytes(b'{"fixture":"keep after feature removal"}')
        modes=[i for i,name in enumerate(('mining_recognition','piracy','missions','hangars','item_finder')) if name in selected]
        absent=[action for name,actions in ACTIONS.items() if name not in selected for action in actions]
        (case/'module_test_model.json').write_text(json.dumps(dict(expected_modes=modes,absent_actions=absent)))
        env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(profile))
        result=subprocess.run([str(native/'SynthScan.exe'),'--ui-test',str(case)],env=env,cwd=native,capture_output=True,text=True,timeout=90,creationflags=0x08000000)
        path=case/'module_ui_test.json';checks=json.loads(path.read_text()) if path.exists() else {}
        passed=result.returncode==0 and checks and all(value is True for value in checks.values()) and record.read_bytes()==b'{"fixture":"keep after feature removal"}'
        report.append(dict(modules=selected,passed=bool(passed),checks=checks,exit=result.returncode))
        (output/'validation.json').write_text(json.dumps(dict(cases=report),indent=2))
        if not passed:raise RuntimeError(f'Module UI case {number} failed: {checks}\n{result.stdout[-1000:]}{result.stderr[-1000:]}')
        print(f'Passed native module UI case {number+1}: {selected or ["Core"]}',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--standard',required=True);parser.add_argument('--full',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();verify(args.standard,args.full,args.output)
