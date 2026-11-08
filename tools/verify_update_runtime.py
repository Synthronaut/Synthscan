"""Headless real-bootstrap routing and detached-runtime checks; no UI/game input."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import prepare_agent


def verify(payload):
    payload=Path(payload).resolve()
    with tempfile.TemporaryDirectory(prefix='SynthScan-update-probe-') as temporary:
        base=Path(temporary);profile=base/'profile';profile.mkdir()
        agent=prepare_agent(payload,profile)
        output=base/'result.json';env=dict(os.environ,SYNTHSCAN_PROBE_OUTPUT=str(output))
        probe="import app_updates,update_agent,update_signing,app_lifecycle,json,os,pathlib;pathlib.Path(os.environ['SYNTHSCAN_PROBE_OUTPUT']).write_text(json.dumps({'stdlib_agent':True}))"
        subprocess.run([str(agent/'runtime/pythonw.exe'),'-I','-B','-c',probe],env=env,check=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        assert json.loads(output.read_text())['stdlib_agent']
        shutil.copy2(payload/'SynthScan.exe',agent/'SynthScan.exe')
        fixture="import json,os,pathlib,sys;pathlib.Path(os.environ['SYNTHSCAN_PROBE_OUTPUT']).write_text(json.dumps({'origin':str(pathlib.Path(__file__).resolve().parent),'argv':sys.argv[1:]}))"
        (agent/'app_launcher.py').write_text(fixture)
        token='a'*64;version=agent/'versions'/token;version.mkdir(parents=True)
        shutil.copytree(agent/'runtime',version/'runtime')
        (version/'app_launcher.py').write_text(fixture)
        def run(expected,*arguments):
            output.unlink(missing_ok=True)
            subprocess.run([str(agent/'SynthScan.exe'),*arguments],env=env,check=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15
            while not output.exists() and time.monotonic()<deadline:time.sleep(.02)
            value=json.loads(output.read_text());assert Path(value['origin'])==expected,value
            return value
        run(agent,'--probe-flat')
        (agent/'active_version.txt').write_text(token+'\n')
        run(version,'--probe-version')
        (agent/'activation_pending.txt').write_text('{}')
        assert '--recover-update' in run(agent,'--probe-interruption')['argv']
        assert '--update-health' in run(version,'--update-health')['argv']
        (agent/'activation_pending.txt').unlink()
        (agent/'active_version.txt').write_text('../invalid')
        assert '--recover-update' in run(agent,'--probe-invalid-pointer')['argv']
    print('Detached stdlib runtime and stable launcher flat/version/recovery/health routing passed')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);verify(parser.parse_args().payload)
