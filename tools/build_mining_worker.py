"""Build the pinned native mining readers using the installed MSVC and SDK.

No system installation, account files, game input, or upstream reporting service.
OpenCV's official SDK is downloaded separately and verified by release digest.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'native/mining_worker'
MSVC=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\14.29.30133')
SDK=Path(r'C:\Program Files (x86)\Windows Kits\10')
VERSION='10.0.19041.0'
OPENCV=ROOT/'third_party/build_tools/opencv412/opencv/build'


def main():
    build=SOURCE/'build';build.mkdir(exist_ok=True)
    out=ROOT/'third_party/mining_core';out.mkdir(exist_ok=True)
    provenance=json.loads((SOURCE/'vendor/UPSTREAM.json').read_text())
    for name,digest in provenance['files'].items():
        if hashlib.sha256((SOURCE/'vendor'/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Vendored source changed: '+name)
    def adapter_hashes():
        return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*') if p.is_file()}
    adapters=adapter_hashes()
    env=os.environ.copy()
    env['PATH']=str(MSVC/'bin/Hostx64/x64')+os.pathsep+str(SDK/'bin'/VERSION/'x64')+os.pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[MSVC/'include',SDK/'Include'/VERSION/'ucrt',SDK/'Include'/VERSION/'shared',SDK/'Include'/VERSION/'um',SDK/'Include'/VERSION/'winrt']))
    env['LIB']=';'.join(map(str,[MSVC/'lib/x64',SDK/'Lib'/VERSION/'ucrt/x64',SDK/'Lib'/VERSION/'um/x64']))
    logs=[]
    def run(args,cwd=build):
        p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,errors='replace',timeout=300,creationflags=0x08004000)
        logs.append(dict(args=list(map(str,args)),exit=p.returncode,output=p.stdout+p.stderr))
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-12000:])
    flags=['/nologo','/std:c++20','/EHsc','/MD','/O2','/utf-8','/D_CRT_SECURE_NO_WARNINGS','/DNOMINMAX','/Gy',
           '/I'+str(SOURCE/'vendor/include'),'/I'+str(OPENCV/'include')]
    files=list((SOURCE/'vendor/src').glob('*.cpp'))+list(SOURCE.glob('*.cpp'))
    def compile(path):
        obj=build/(path.stem+'.obj')
        run([MSVC/'bin/Hostx64/x64/cl.exe',*flags,'/c',path,'/Fo'+str(obj)])
        print('Compiled '+path.name,flush=True)
        return obj
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile,files))
        resource=build/'worker.res'
        run([SDK/'bin'/VERSION/'x64/rc.exe','/nologo','/fo',resource,SOURCE/'worker.rc'],SOURCE)
        binary=build/'synthscan-mining.exe'
        run([MSVC/'bin/Hostx64/x64/link.exe','/nologo','/OUT:'+str(binary),'/SUBSYSTEM:CONSOLE','/OPT:REF',
             *objects,resource,OPENCV/'x64/vc16/lib/opencv_world4120.lib','gdi32.lib','user32.lib','d3d11.lib','dxgi.lib','dwmapi.lib'])
        if adapter_hashes()!=adapters:
            raise ValueError('Adapter source changed during compilation; rebuild before publishing')
        for name,digest in provenance['files'].items():
            if hashlib.sha256((SOURCE/'vendor'/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Vendored source changed during compilation: '+name)
        shutil.copy2(binary,out/binary.name)
        shutil.copy2(OPENCV/'x64/vc16/bin/opencv_world4120.dll',out)
        shutil.copy2(OPENCV/'LICENSE',out/'LICENSE-OpenCV')
        for name in ('LICENSE','NOTICE.txt','THIRD-PARTY-NOTICES.txt'):
            shutil.copy2(SOURCE/'vendor'/name,out/name)
        provenance['adapter_files']=adapters
        provenance['toolchain']=dict(msvc=str(MSVC),sdk=VERSION,opencv='4.12.0',flags=flags)
        provenance['binary_files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in ('.exe','.dll')}
        provenance['opencv']=json.loads((ROOT/'third_party/build_tools/opencv_download.json').read_text())
        (out/'build_manifest.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
        print('Built '+str(out/binary.name),flush=True)
    finally:
        (build/'build_log.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')


if __name__=='__main__':main()
