"""Compare independently built unsigned native artifacts, not private config files."""
import argparse
import hashlib
import json
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def compare(first,second):
    first,second=Path(first),Path(second)
    a=json.loads((first/'build_manifest.json').read_text());b=json.loads((second/'build_manifest.json').read_text())
    if a.get('source_files')!=b.get('source_files'):raise ValueError('Builds do not describe the same native sources')
    if a.get('toolchain')!=b.get('toolchain'):raise ValueError('Builds use different toolchains')
    names=set(a['binary_files'])
    if names!=set(b['binary_files']) or not names:raise ValueError('Build artifact sets differ')
    hashes={}
    for name in sorted(names):
        if Path(name).name!=name:raise ValueError('Invalid artifact name')
        left=digest(first/name);right=digest(second/name)
        if left!=a['binary_files'][name] or right!=b['binary_files'][name]:raise ValueError('Artifact differs from its manifest: '+name)
        if left!=right:raise ValueError('Build is not byte-for-byte reproducible: '+name)
        hashes[name]=left
    return dict(schema=1,reproduced=True,binary_sha256=hashes,scope='unsigned native artifacts; runtime path/configuration files are intentionally excluded',independent_review=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('first',type=Path);parser.add_argument('second',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    result=compare(args.first,args.second);raw=json.dumps(result,indent=2)
    if args.report:args.report.write_text(raw+'\n',encoding='utf-8')
    print(raw)
if __name__=='__main__':main()
