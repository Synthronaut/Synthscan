"""Fetch only hash-pinned upstream compiler dependencies."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def fetch(metadata):
    info=json.loads(metadata.read_text(encoding='utf-8'))
    archive=metadata.parent/info['url'].rsplit('/',1)[-1]
    if not archive.exists():
        urllib.request.urlretrieve(info['url'],archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=info['sha256']:
        raise ValueError('Dependency checksum mismatch: '+archive.name)
    return archive


def main():
    base=ROOT/'third_party/build_tools';base.mkdir(parents=True,exist_ok=True)
    opencv=fetch(base/'opencv_download.json')
    destination=base/'opencv412'
    if not (destination/'opencv/build/include/opencv2').exists():
        subprocess.run([str(opencv),'-y','-o'+str(destination)],check=True)
    zstd=fetch(base/'zstd_source.json')
    if not (base/'zstd-1.5.7/lib/zstd.h').exists():
        with tarfile.open(zstd) as archive:archive.extractall(base,filter='data')
    print('Verified compiler dependencies ready.')


if __name__=='__main__':main()
