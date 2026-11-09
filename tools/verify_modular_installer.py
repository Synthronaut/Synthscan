"""Exercise a real per-user installer, upgrades and uninstall with synthetic data.

Use the validation-identity build locally. The production identity is only safe
on a fresh CI runner with no existing SynthScan installation.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import winreg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_modules import FEATURES


def verify(installer,validation=False,output=None):
    installer=Path(installer).resolve();suffix='C30' if validation else 'C20'
    key='Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{6278A3F4-6738-4AE9-84CF-12B477780'+suffix+'}_is1'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key):raise ValueError('A matching app identity is already installed. Use a fresh runner or a separate validation build.')
    except FileNotFoundError:pass
    result=[]
    with tempfile.TemporaryDirectory(prefix='SynthScan-installer-validation-',ignore_cleanup_errors=True) as temporary:
        base=Path(temporary);root=base/'app';profile=base/'profile';profile.mkdir()
        marker=b'{"fixture":"ownership and player records must survive"}'
        (profile/'inventory.json').write_bytes(marker)
        env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(profile))
        sequences=[['server_hud','hangars'],list(FEATURES),[name for name in FEATURES if name!='mining_recognition']]
        for number,selected in enumerate(sequences):
            log=base/('install-'+str(number)+'.log')
            process=subprocess.run([str(installer),'/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
                '/DIR='+str(root),'/SYNTHSCANPROFILE='+str(profile),'/COMPONENTS=core,'+','.join(selected),'/TASKS=','/LOG='+str(log)],
                env=env,timeout=360,creationflags=0x08000000)
            if process.returncode:raise RuntimeError('Installer failed: '+str(process.returncode)+'\n'+log.read_text(encoding='utf-8',errors='replace')[-5000:])
            token=(root/'active_version.txt').read_text().strip();active=root/'versions'/token
            release=json.loads((active/'release.json').read_text())
            assert set(release['modules'])==set(selected),release
            assert (profile/'inventory.json').read_bytes()==marker
            probe="import sys;sys.path.insert(0,sys.argv[1]);from module_setup import verify_runtime;verify_runtime(sys.argv[1])"
            subprocess.run([str(active/'runtime/python.exe'),'-I','-B','-c',probe,str(active)],env=env,check=True,timeout=90,creationflags=0x08000000)
            if 'mining_recognition' not in selected:
                for path in root.rglob('release.json'):
                    value=json.loads(path.read_text())
                    assert value.get('edition')!='full',str(path)
                assert not any(root.rglob('*.onnx'))
                assert not any(root.rglob('onnxruntime'))
            result.append(dict(case=number,modules=selected,installer_passed=True,records_preserved=True))
        log=base/'uninstall.log'
        try:
            subprocess.run([str(root/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SYNTHSCANPROFILE='+str(profile),'/LOG='+str(log)],env=env,check=True,timeout=120,creationflags=0x08000000)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            tail=log.read_text(encoding='utf-8',errors='replace')[-6000:] if log.exists() else 'No uninstall log'
            raise RuntimeError('Uninstaller did not complete: '+str(error)+'\n'+tail) from error
        # Inno may finish cleanup in its temporary process after the original
        # executable returns; observe removal before cleaning the fixture.
        deadline=time.monotonic()+30
        while (root/'versions').exists() and time.monotonic()<deadline:time.sleep(.2)
        assert (profile/'inventory.json').read_bytes()==marker
        assert not (root/'versions').exists()
        assert (profile/'uninstall_result.json').is_file()
        result.append(dict(uninstall_passed=True,records_preserved=True))
    report=dict(validation_identity=validation,production_installer=not validation,cases=result)
    if output:Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--installer',required=True);parser.add_argument('--validation',action='store_true');parser.add_argument('--output');args=parser.parse_args()
    print(json.dumps(verify(args.installer,args.validation,args.output),indent=2))
