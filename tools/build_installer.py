"""Compile the per-user Windows installer using a verified Inno Setup compiler."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import sys

ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe'
DIGEST='0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f'

def compiler():
    folder=ROOT/'third_party/build_tools/innosetup';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'setup.exe'
    if not path.exists():urllib.request.urlretrieve(URL,path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=DIGEST:raise ValueError('Installer compiler checksum mismatch')
    executable=folder/'compiler/ISCC.exe'
    if not executable.exists():subprocess.run([str(path),'/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/DIR='+str(folder/'compiler')],check=True,timeout=120)
    return executable

def build(payload,output):
    payload=Path(payload).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    from package_community import audit
    audit(payload)
    subprocess.run([str(compiler()),'/Qp','/DPayload='+str(payload),'/DOutput='+str(output),str(ROOT/'installer/SynthScan.iss')],check=True)
    file=output/'SynthScan-Setup-Windows-x64.exe'
    digest=hashlib.sha256(file.read_bytes()).hexdigest()
    file.with_suffix('.exe.sha256').write_text(digest+'  '+file.name+'\n',encoding='ascii')
    print(json.dumps(dict(installer=str(file),sha256=digest,bytes=file.stat().st_size)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--payload',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    build(a.payload,a.output)
