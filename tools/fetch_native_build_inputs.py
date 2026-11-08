"""Fetch only hash-pinned OpenCV/zstd inputs for a public-source native build."""
import hashlib,json,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def download(spec,target):
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==spec['sha256']:return
    target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(spec['url'],timeout=60) as source,target.open('wb') as output:
        while chunk:=source.read(1024*1024):output.write(chunk)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=spec['sha256']:
        target.unlink(missing_ok=True);raise ValueError('Build input digest mismatch')
def main():
    folder=ROOT/'third_party/build_tools';opencv=json.loads((folder/'opencv_download.json').read_text());zstd=json.loads((folder/'zstd_source.json').read_text())
    archive=folder/'downloads/opencv-4.12.0-windows.exe';download(opencv,archive)
    if not (folder/'opencv412/opencv/build/include/opencv2/core.hpp').exists():subprocess.run(['7z','x','-y','-o'+str(folder/'opencv412'),str(archive)],check=True)
    source=folder/'downloads/zstd-1.5.7.tar.gz';download(zstd,source)
    if not (folder/'zstd-1.5.7/lib/zstd.h').exists():subprocess.run(['tar','-xf',str(source),'-C',str(folder)],check=True)
if __name__=='__main__':main()
