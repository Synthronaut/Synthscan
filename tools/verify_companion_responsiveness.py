"""Build and run the real People controls in a bounded, synthetic offscreen host."""
import json, os, shutil, subprocess, sys
from pathlib import Path
from build_native_app import ROOT, SOURCE, MSVC, SDK, VERSION

def run(args, **kwargs):
    result=subprocess.run(args, capture_output=True, text=True, errors="replace", **{k:v for k,v in kwargs.items() if k!="check"})
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result

def main():
    out=ROOT/'release-validation/companion-responsiveness'
    out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env['PATH']=str(MSVC/'bin/Hostx64/x64')+os.pathsep+str(SDK/'bin'/VERSION/'x64')+os.pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[MSVC/'include',SDK/'Include'/VERSION/'ucrt',SDK/'Include'/VERSION/'shared',SDK/'Include'/VERSION/'um']))
    env['LIB']=';'.join(map(str,[MSVC/'lib/x64',SDK/'Lib'/VERSION/'ucrt/x64',SDK/'Lib'/VERSION/'um/x64']))
    objects=[]
    for source in [ROOT/'tools/companion_responsiveness_probe.cpp',SOURCE/'src/SynthWebView.cpp',SOURCE/'src/SynthPages.cpp',SOURCE/'src/MiniJson.cpp',SOURCE/'src/SynthHome.cpp',SOURCE/'src/AppPaths.cpp']:
        obj=out/(source.stem+'.obj');objects.append(obj)
        if obj.exists() and obj.stat().st_mtime>=source.stat().st_mtime and (source.stem!='companion_responsiveness_probe' or obj.stat().st_mtime>=(SOURCE/'src/SynthCompanion.cpp').stat().st_mtime):continue
        run([str(MSVC/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++20','/EHsc','/MD','/O2','/utf-8','/DNOMINMAX','/FI'+str(SOURCE/'include/SynthCompatibility.h'),'/I'+str(SOURCE/'include'),'/c',str(source),'/Fo'+str(obj)],env=env,check=True,timeout=90,creationflags=0x08004000)
    binary=out/'companion_responsiveness_probe.exe'
    run([str(MSVC/'bin/Hostx64/x64/link.exe'),'/nologo','/OUT:'+str(binary),*map(str,objects),'user32.lib','gdi32.lib','gdiplus.lib','comctl32.lib','uxtheme.lib','shell32.lib','dwmapi.lib','ole32.lib','advapi32.lib','bcrypt.lib'],env=env,check=True,timeout=30,creationflags=0x08004000)
    shutil.rmtree(out/'fixture',ignore_errors=True);shutil.rmtree(out/'preview',ignore_errors=True)
    result=subprocess.run([str(binary),str(out/'fixture'),*sys.argv[1:]],capture_output=True,text=True,timeout=24,creationflags=0x08004000)
    print(result.stdout);print(result.stderr)
    if result.returncode:return result.returncode
    if sys.argv[1:]:return 0
    result=subprocess.run([str(binary),str(out/'preview'),'--preview'],capture_output=True,text=True,timeout=24,creationflags=0x08004000)
    if result.returncode:
        print(result.stdout+result.stderr);return result.returncode
    report=json.loads((out/'fixture/responsiveness.json').read_text())
    checks=json.loads((out/'preview/ui_validation.json').read_text())
    assert all(v for v in checks.values() if isinstance(v,bool)),checks
    assert checks['outgoing_requests_sent']==0
    webview_checks=None
    manifest_path=ROOT/'dist/native/build_manifest.json'
    exe_path=ROOT/'dist/native/SynthScan.exe'
    if exe_path.exists() and manifest_path.exists() and 'src/SynthWebView.cpp' in json.loads(manifest_path.read_text()).get('source_files',{}):
        shutil.rmtree(out/'webview',ignore_errors=True)
        wv=subprocess.run([str(exe_path),'--webview-preview',str(out/'webview')],capture_output=True,text=True,timeout=60,creationflags=0x08004000)
        if wv.returncode:
            print(wv.stdout+wv.stderr);return wv.returncode
        webview_checks=json.loads((out/'webview/webview_validation.json').read_text(encoding='utf-8'))
        assert webview_checks.get('suite_500_roster_passed') and webview_checks.get('forged_and_unconfirmed_rejected') and webview_checks.get('authenticated_stage_routed'),webview_checks
    (out/'validation.json').write_text(json.dumps(dict(passed=True,responsiveness=report,interaction=checks,webview=webview_checks),indent=2))
    print('Existing People selection, scroll and action-routing checks passed; no outgoing requests.')
    return 0

if __name__=='__main__':sys.exit(main())
