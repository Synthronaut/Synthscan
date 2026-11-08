"""Create a local DPAPI-protected signing key and ship only its public key."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from update_signing import generate_key,protect,private_key,signature


def configure(key_file,output):
    key_file=Path(key_file);public_file=key_file.with_suffix('.public.json')
    if key_file.exists():
        public=base64.b64decode(json.loads(public_file.read_text())['public'],validate=True)
        signature(public,b'SynthScan release key validation',signature(private_key(key_file),b'SynthScan release key validation'))
    else:
        key_file.parent.mkdir(parents=True,exist_ok=True);private,public=generate_key()
        with key_file.open('xb') as stream:stream.write(protect(private))
        public_file.write_text(json.dumps(dict(public=base64.b64encode(public).decode())),encoding='utf-8')
    key_id=hashlib.sha256(public).hexdigest()[:16]
    value=dict(schema=1,manifest_url='https://github.com/Synthronaut/Synthscan/releases/download/update-channel/synthscan-update.json',
               allowed_hosts=['github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'],
               keys={key_id:base64.b64encode(public).decode()})
    Path(output).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(public_key_id=key_id,trust_file=str(Path(output).resolve()),protected_private_key=str(key_file.resolve()))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--key-file',type=Path,default=Path(os.environ['LOCALAPPDATA'])/'SynthScanRelease/signing-key.dpapi')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'update_trust.json');args=parser.parse_args()
    configure(args.key_file,args.output)
