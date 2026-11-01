"""Link an offline image-reader probe against the already-built native objects."""
import os,re,subprocess
from pathlib import Path
from build_native_app import ROOT,SOURCE,BUILD,MSVC,SDK,VERSION,OPENCV,ZSTD_SOURCE

def main():
    out=ROOT/'dist/mining-frame-probe';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env['PATH']=str(MSVC/'bin/Hostx64/x64')+os.pathsep+str(SDK/'bin'/VERSION/'x64')+os.pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[MSVC/'include',SDK/'Include'/VERSION/'ucrt',SDK/'Include'/VERSION/'shared',SDK/'Include'/VERSION/'um',SDK/'Include'/VERSION/'winrt']))
    env['LIB']=';'.join(map(str,[MSVC/'lib/x64',SDK/'Lib'/VERSION/'ucrt/x64',SDK/'Lib'/VERSION/'um/x64']))
    obj=out/'mining_frame_probe.obj'
    subprocess.run([str(MSVC/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++20','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX',
        '/FI'+str(SOURCE/'include/SynthCompatibility.h'),'/I'+str(SOURCE/'include'),'/I'+str(OPENCV/'include'),
        '/c',str(ROOT/'tools/mining_frame_probe.cpp'),'/Fo'+str(obj)],env=env,check=True)
    cmake=(SOURCE/'CMakeLists.txt').read_text();objects=[]
    for group in ['CORE_SOURCES','SOURCES']:
        body=re.search(r'set\('+group+r'\s+(.*?)\n\)',cmake,re.S)[1]
        objects.extend(BUILD/(Path(n).stem+'.obj') for n in re.findall(r'src/[A-Za-z_0-9]+\.cpp',body) if Path(n).stem!='main')
    objects=list(dict.fromkeys(objects))+[BUILD/(p.stem+'.obj') for p in (SOURCE/'src').glob('Synth*.cpp')]
    objects=list(dict.fromkeys(objects))+list(BUILD.glob('zstd_*.obj'))
    if os.environ.get('SYNTHSCAN_PROBE_TRACE'):
        trace_obj=out/'RockContentsTrace.obj'
        subprocess.run([str(MSVC/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++20','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/DBEDROCK_DEV_TOOLS',
            '/FI'+str(SOURCE/'include/SynthCompatibility.h'),'/I'+str(SOURCE/'include'),'/I'+str(OPENCV/'include'),
            '/c',str(SOURCE/'src/RockContents.cpp'),'/Fo'+str(trace_obj)],env=env,check=True)
        objects=[trace_obj if p.name=='RockContents.obj' else p for p in objects]
    subprocess.run([str(MSVC/'bin/Hostx64/x64/link.exe'),'/nologo','/SUBSYSTEM:CONSOLE','/OPT:REF',
        '/OUT:'+str(out/'mining_frame_probe.exe'),str(obj),*map(str,objects),str(BUILD/'app.res'),
        str(OPENCV/'x64/vc16/lib/opencv_world4120.lib'),'gdi32.lib','gdiplus.lib','user32.lib','comctl32.lib','dwmapi.lib',
        'd3d11.lib','dxgi.lib','comdlg32.lib','shell32.lib','ole32.lib','winhttp.lib','bcrypt.lib','advapi32.lib'],env=env,check=True)
    import shutil
    shutil.copy2(OPENCV/'x64/vc16/bin/opencv_world4120.dll',out)
    print(out/'mining_frame_probe.exe')

if __name__=='__main__':main()
