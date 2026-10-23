"""Prepare or start an opt-in, process-scoped snare trace experiment.

Never modifies game files, the registry, or live game processes. The launcher
must be closed normally first so its child can inherit the diagnostic settings.
This is a diagnostic candidate, not an operational catch detector.
"""
import argparse,copy,csv,hashlib,io,json,os,re,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE')
LAUNCHER=Path(r'C:\Program Files\Roberts Space Industries\RSI Launcher\RSI Launcher.exe')
PROFILE=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'SynthScan/snare-trace-probe'
EVENTS=['Interdiction','SnareActivated','SUCCESS: ESS TagEntities','FAILURE: ESS TagEntities',
        'CSCPlayer::RmAuthorityPropagateQuantumSnareMarkerToParty','SynthScanSnareProbe',
        'Local Trace Config loaded']

def default_filter(raw):
    found=[]
    for m in re.finditer(rb'\{"Version": \d+, "Log": ',raw):
        try:
            value=json.loads(raw[m.start():].split(b'\0',1)[0])
            if isinstance(value.get('Publish'),list) and isinstance(value.get('Log'),list):found.append(value)
        except (ValueError,TypeError):pass
    if not found:raise ValueError('No known embedded trace-filter schema found; refusing to guess')
    return max(found,key=lambda x:x['Version'])

def diagnostic_filter(base):
    result=copy.deepcopy(base)
    severity=['Emergency','Alert','Critical','Error','Warning','Notice','Info','Debug']
    result['Publish']=[dict(Severity=severity,**{'Include Events':EVENTS}),
                       dict(Severity=severity,**{'Include Tags':['LegacyAnalytics']})]
    return result

def diagnostic_environment(profile):
    return dict(SYSTEM_TRACE_ENABLED='1',SYSTEM_TRACE_ENABLE_LOG='1',SYSTEM_TRACE_ENABLE_PUBLISH='1',
                SYSTEM_TRACE_SERVICE_ENABLED='0',SYSTEM_TRACE_FILTER_USER_FILENAME=str(profile/'trace_filter.json'),
                SYSTEM_TRACE_OUTPUT_DIRECTORY=str(profile/'events'),SYSTEM_TRACE_OUTPUT_FILENAME='SynthScanSnareTrace',
                SYSTEM_TRACE_OUTPUT_ROTATION_MB='8',SYSTEM_TRACE_OUTPUT_AUTO_DELETE='1')

def running_names():
    result=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return {row[0].casefold() for row in csv.reader(io.StringIO(result.stdout)) if row}

def prepare(profile=PROFILE):
    raw=(GAME/'Bin64/StarCitizen.exe').read_bytes();base=default_filter(raw);probe=diagnostic_filter(base)
    profile.mkdir(parents=True,exist_ok=True);(profile/'events').mkdir(exist_ok=True)
    (profile/'trace_filter.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
    environment=diagnostic_environment(profile);environment['SYSTEM_TRACE_OUTPUT_FILENAME']+='_'+uuid.uuid4().hex[:10]
    manifest=dict(schema=1,exe_sha256=hashlib.sha256(raw).hexdigest(),filter_version=base['Version'],
                  environment=environment,events=EVENTS,local_only=True,runtime_verified=False)
    (profile/'probe_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def launch():
    names=running_names()
    if 'starcitizen.exe' in names:raise RuntimeError('Star Citizen is running. This probe waits for your next normal game restart; it never closes the game.')
    if 'rsi launcher.exe' in names:raise RuntimeError('Quit RSI Launcher from its tray menu first. A fresh launcher is required to inherit the one-session settings.')
    if not LAUNCHER.is_file():raise FileNotFoundError(str(LAUNCHER))
    manifest=prepare();env=os.environ.copy();env.update(manifest['environment'])
    subprocess.Popen([str(LAUNCHER)],env=env,cwd=LAUNCHER.parent,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    print('Diagnostic launcher started. Click Launch Game normally. This does not prove catch detection works.')
    print('Private local trace folder:',PROFILE/'events')

def status(profile=PROFILE):
    files=[];candidates={};loaded=0;lines=0
    folder=profile/'events';prefix='SynthScanSnareTrace'
    try:prefix=json.loads((profile/'probe_manifest.json').read_text(encoding='utf-8'))['environment']['SYSTEM_TRACE_OUTPUT_FILENAME']
    except (OSError,ValueError,KeyError):pass
    if folder.exists():
        for path in folder.iterdir():
            if not path.is_file() or not path.name.startswith(prefix):continue
            files.append(dict(name=path.name,bytes=path.stat().st_size))
            if path.stat().st_size>20*1024*1024:continue
            with path.open(encoding='utf-8',errors='replace') as stream:
                for line in stream:
                    lines+=1
                    if 'Local Trace Config loaded' in line and re.sub(r'[\\/]+','/',str(profile/'trace_filter.json')).casefold() in re.sub(r'[\\/]+','/',line).casefold():loaded+=1
                    for event in EVENTS:
                        if event in line:candidates[event]=candidates.get(event,0)+1
    return dict(files=files,lines_checked=lines,local_filter_load_records=loaded,candidate_mentions=candidates,
                catch_detection_verified=False,note='Counts are diagnostic mentions, not verified catches. A new operator catch must still be compared.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launch',action='store_true');p.add_argument('--status',action='store_true');args=p.parse_args()
    if args.launch:launch()
    elif args.status:print(json.dumps(status(),indent=2))
    else:
        m=prepare();print(json.dumps(dict(prepared=True,profile=str(PROFILE),filter_version=m['filter_version'],runtime_verified=False)))

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError) as exc:
        print('Snare trace probe was not started:',exc);raise SystemExit(1)
