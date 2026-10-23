"""Build the complete pinned native SynthScan application, with local SDKs."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'native/synthscan'
BUILD=ROOT/'native/synthscan-build'
OUT=Path(os.environ.get('SYNTHSCAN_BUILD_OUT',str(ROOT/'dist/native')))
MSVC=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\14.29.30133')
SDK=Path(r'C:\Program Files (x86)\Windows Kits\10')
VERSION='10.0.19041.0'
if os.environ.get('SYNTHSCAN_MSVC'):MSVC=Path(os.environ['SYNTHSCAN_MSVC'])
elif not MSVC.exists():
    vswhere=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    base=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    MSVC=sorted((Path(base)/'VC/Tools/MSVC').iterdir(),key=lambda p:tuple(map(int,p.name.split('.'))))[-1]
if os.environ.get('SYNTHSCAN_SDK'):SDK=Path(os.environ['SYNTHSCAN_SDK'])
if not (SDK/'Include'/VERSION).exists():
    VERSION=sorted((SDK/'Include').iterdir(),key=lambda p:tuple(map(int,p.name.split('.'))))[-1].name
OPENCV=ROOT/'third_party/build_tools/opencv412/opencv/build'
ZSTD=ROOT/'third_party/build_tools/zstd157/zstd-v1.5.7-win64'
ZSTD_SOURCE=ROOT/'third_party/build_tools/zstd-1.5.7/lib'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    BUILD.mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env['PATH']=str(MSVC/'bin/Hostx64/x64')+os.pathsep+str(SDK/'bin'/VERSION/'x64')+os.pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[MSVC/'include',SDK/'Include'/VERSION/'ucrt',SDK/'Include'/VERSION/'shared',SDK/'Include'/VERSION/'um',SDK/'Include'/VERSION/'winrt']))
    env['LIB']=';'.join(map(str,[MSVC/'lib/x64',SDK/'Lib'/VERSION/'ucrt/x64',SDK/'Lib'/VERSION/'um/x64']))
    flags=['/nologo','/std:c++20','/EHsc','/MD','/O2','/utf-8','/bigobj','/D_CRT_SECURE_NO_WARNINGS','/DNOMINMAX','/Gy',
           '/I'+str(SOURCE/'include'),'/I'+str(OPENCV/'include'),'/I'+str(ZSTD_SOURCE),'/FI'+str(SOURCE/'include/SynthCompatibility.h')]
    cmake=(SOURCE/'CMakeLists.txt').read_text()
    files=[]
    for group in ['CORE_SOURCES','SOURCES']:
        body=re.search(r'set\('+group+r'\s+(.*?)\n\)',cmake,re.S)[1]
        files.extend(SOURCE/name for name in re.findall(r'src/[A-Za-z_0-9]+\.cpp',body))
    files=list(dict.fromkeys(files))+[p for p in (SOURCE/'src').glob('Synth*.cpp') if p not in files]
    def dependencies(path,seen=None):
        seen=set() if seen is None else seen
        if path in seen:return ''
        seen.add(path);value=digest(path)
        for name in re.findall(r'#include\s+"([^"]+)"',path.read_text(encoding='utf-8')):
            target=SOURCE/'include'/name
            if target.exists():value+=dependencies(target,seen)
        return value
    signature=hashlib.sha256((digest(SOURCE/'include/SynthCompatibility.h')+str(flags)).encode()).hexdigest()
    cache_path=BUILD/'cache.json'
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    next_cache={};logs=[]
    def run(args,cwd=BUILD):
        p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,errors='replace',timeout=600,creationflags=0x08004000)
        logs.append(dict(args=list(map(str,args)),exit=p.returncode,output=p.stdout+p.stderr))
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-18000:])
    def compile(path):
        obj=BUILD/(path.stem+'.obj');key=signature+dependencies(path)
        if not obj.exists() or cache.get(path.name)!=key:
            run([MSVC/'bin/Hostx64/x64/cl.exe',*flags,'/c',path,'/Fo'+str(obj)])
            print('Compiled '+path.name,flush=True)
        next_cache[path.name]=key
        return obj
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile,files))
        def compile_zstd(path):
            obj=BUILD/('zstd_'+path.stem+'.obj');key=digest(path)+'msvc-md-o2-noasm'
            if not obj.exists() or cache.get('zstd_'+path.name)!=key:
                run([MSVC/'bin/Hostx64/x64/cl.exe','/nologo','/TC','/MD','/O2','/W0','/DZSTD_DISABLE_ASM',
                     '/D_CRT_SECURE_NO_WARNINGS','/I'+str(ZSTD_SOURCE),'/c',path,'/Fo'+str(obj)])
                print('Compiled zstd/'+path.name,flush=True)
            next_cache['zstd_'+path.name]=key
            return obj
        zstd_files=[p for folder in ['common','compress','decompress','dictBuilder'] for p in (ZSTD_SOURCE/folder).glob('*.c')]
        with ThreadPoolExecutor(max_workers=2) as pool:zstd_objects=list(pool.map(compile_zstd,zstd_files))
        cache_path.write_text(json.dumps(next_cache,indent=2))
        resource=BUILD/'app.res'
        run([SDK/'bin'/VERSION/'x64/rc.exe','/nologo','/fo',resource,SOURCE/'resources/bedrock.rc'],SOURCE/'resources')
        binary=BUILD/'SynthScan.exe'
        run([MSVC/'bin/Hostx64/x64/link.exe','/nologo','/OUT:'+str(binary),'/SUBSYSTEM:WINDOWS','/OPT:REF',*objects,resource,
             OPENCV/'x64/vc16/lib/opencv_world4120.lib',*zstd_objects,
             'gdi32.lib','gdiplus.lib','user32.lib','comctl32.lib','dwmapi.lib','d3d11.lib','dxgi.lib',
             'comdlg32.lib','shell32.lib','ole32.lib','winhttp.lib','bcrypt.lib','advapi32.lib'])
        shutil.copy2(binary,OUT/binary.name)
        shutil.copy2(OPENCV/'x64/vc16/bin/opencv_world4120.dll',OUT)
        for name in ['LICENSE','NOTICE.txt','THIRD-PARTY-NOTICES.txt']:
            shutil.copy2(SOURCE/name,OUT/name)
        shutil.copy2(OPENCV/'LICENSE',OUT/'LICENSE-OpenCV')
        shutil.copy2(ROOT/'LICENSES.md',OUT/'LICENSES.md')
        (OUT/'native_runtime.json').write_text(json.dumps(dict(workspace=str(ROOT),pythonw=str(Path(sys.executable).with_name('pythonw.exe'))),indent=2))
        shutil.copy2(ZSTD_SOURCE.parent/'LICENSE',OUT/'LICENSE-zstd')
        manifest=dict(upstream=json.loads((ROOT/'native/synthscan-upstream.json').read_text())['commit'],
                      source_files={p.relative_to(SOURCE).as_posix():digest(p) for p in files+list((SOURCE/'include').glob('*.h'))+[SOURCE/'resources/bedrock.rc']},
                      binary_files={p.name:digest(p) for p in OUT.glob('*') if p.suffix in ('.exe','.dll')},toolchain=dict(msvc=str(MSVC),sdk=VERSION),
                      zstd=json.loads((ROOT/'third_party/build_tools/zstd_source.json').read_text()))
        (OUT/'build_manifest.json').write_text(json.dumps(manifest,indent=2))
        print('Built '+str(OUT/binary.name),flush=True)
    finally:
        cache.update(next_cache);cache_path.write_text(json.dumps(cache,indent=2))
        (BUILD/'build_log.json').write_text(json.dumps(logs,indent=2))

if __name__=='__main__':main()
