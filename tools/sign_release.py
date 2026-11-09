"""Sign a complete packaged application; private key material is never printed."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_updates import config,inspect_archive,allowed_url
from update_signing import envelope,private_key,signature


def sign_release(archive,url,output,key_file=None,sequence=None):
    root=Path(__file__).resolve().parents[1];trust=config(root);allowed_url(url,trust)
    archive=Path(archive)
    with zipfile.ZipFile(archive) as stream:
        release=json.loads(stream.read('SynthScan/release.json'))
        unpacked=sum(member.file_size for member in stream.infolist() if not member.is_dir())
    now=time.time();value=dict(schema=1,kind='application',platform='windows-x64',version=release['version'],
        sequence=sequence or time.time_ns()//1000000,issued_at=now,expires_at=now+365*86400,
        edition=release.get('edition','full'),minimum_updater=1,size=archive.stat().st_size,unpacked_size=unpacked,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),url=url)
    inspect_archive(archive,value)
    if os.environ.get('SYNTHSCAN_SIGNING_PRIVATE_B64'):
        private=base64.b64decode(os.environ['SYNTHSCAN_SIGNING_PRIVATE_B64'],validate=True)
    else:private=private_key(key_file or Path(os.environ['LOCALAPPDATA'])/'SynthScanRelease/signing-key.dpapi')
    public=None
    for encoded in trust['keys'].values():
        candidate=base64.b64decode(encoded,validate=True)
        try:signature(candidate,b'SynthScan release key validation',signature(private,b'SynthScan release key validation'));public=candidate;break
        except ValueError:continue
    if public is None:raise ValueError('Release signing key does not match the pinned public key')
    Path(output).write_text(json.dumps(envelope(value,private,public),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(version=value['version'],manifest=str(Path(output).resolve()),sha256=value['sha256'],bytes=value['size'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True);parser.add_argument('--url',required=True);parser.add_argument('--output',required=True);parser.add_argument('--key-file')
    args=parser.parse_args();sign_release(args.archive,args.url,args.output,args.key_file)
