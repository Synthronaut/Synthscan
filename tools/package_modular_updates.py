"""Create migration ZIPs for existing update channels from signed module assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import config,write
from feature_modules import FEATURES
from module_distribution import catalog,selection_token,activation_payload,check_sequence
from tools.package_community import archive_package


def build(payload,output):
    payload=Path(payload).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError('Choose a fresh output folder')
    output.mkdir(parents=True);trust=config(payload/'core');raw=(payload/'synthscan-modules.json').read_bytes();value=catalog(raw,trust)
    catalog_hash=hashlib.sha256(raw).hexdigest();profile=output/'build-profile';folder=profile/'updates';folder.mkdir(parents=True)
    cache=folder/'modules-cache';cache.mkdir()
    for name,item in value['packages'].items():shutil.copy2(payload/('SynthScan-module-'+name+'.zip'),cache/(item['sha256']+'.zip'))
    (folder/('catalog-'+catalog_hash+'.json')).write_bytes(raw);write(folder/'catalog-sequence.json',check_sequence(folder,value,raw))
    result=[]
    for edition in ('standard','full'):
        selected=[name for name in FEATURES if edition=='full' or name!='mining_recognition']
        pending=dict(kind='modules',sha256=selection_token(catalog_hash,selected),catalog=catalog_hash,modules=selected)
        target=output/('SynthScan-'+edition+'-Windows-x64');target.mkdir()
        _,unpack=activation_payload(payload/'core',profile,pending,trust);unpack(target);archive_package(target)
        result.append(str(target.with_suffix('.zip')))
    # This is generated release metadata/cache, not a player profile.
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(build(args.payload,args.output),indent=2))
