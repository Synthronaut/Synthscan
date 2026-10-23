"""Prepare game references in the Windows user's profile, not in the download."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import time
from installation import ROOT, PROFILE, game_directory, reference_paths, output_root


def prepare_reputation(paths):
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
    from tools.inspect_game_schema import iter_descriptors
    from tools.audit_reputation_data import audit
    game=paths['game']
    manifest=json.loads((game/'build_manifest.id').read_text(encoding='utf-8'))
    raw=(game/'Bin64/StarCitizen.exe').read_bytes()
    descriptors=FileDescriptorSet()
    for descriptor,_ in iter_descriptors(raw):descriptors.file.add().CopyFrom(descriptor)
    if not descriptors.file:raise ValueError('No service definitions found in this game build')
    paths['schemas'].write_bytes(descriptors.SerializeToString())
    paths['schema_manifest'].write_text(json.dumps(dict(build_id=manifest['Data']['BuildId'],
        source='embedded executable protobuf descriptors',credentials=False)),encoding='utf-8')
    report=audit(paths['records'],paths['localization'],manifest)
    if not report['scopes']:raise ValueError('No reputation thresholds found in this game build')
    paths['audit'].write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')


def prepare(progress=print):
    PROFILE.mkdir(parents=True,exist_ok=True)
    game=game_directory(True)
    (PROFILE/'installation.json').write_text(json.dumps(dict(game_dir=str(game))),encoding='utf-8')
    paths=reference_paths();paths['root'].mkdir(parents=True,exist_ok=True)
    marker=paths['root']/'ready.json'
    try:
        active_build=json.loads((output_root()/'data/local_game_library.json').read_text(encoding='utf-8'))['provenance']['build']['BuildId']
    except (OSError,ValueError,KeyError):active_build=None
    refreshed=not marker.exists() or active_build!=paths['root'].name
    if refreshed:
        progress('Reading your installed game: blueprints, mining, artwork and reputation. This can take several minutes.')
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/refresh_game_reference.py'),'--game-dir',str(game)],
                       cwd=ROOT,check=True,creationflags=0x08000000 if os.name=='nt' else 0)
        progress('Building reputation thresholds and read-only account service definitions…')
        prepare_reputation(paths)
        marker.write_text(json.dumps(dict(build_id=json.loads((game/'build_manifest.id').read_text())['Data']['BuildId'])),encoding='utf-8')
    progress('Preparing your searchable item and blueprint library…')
    from native_workspace_data import library_export
    library_export(ROOT/'dist/native/workspace_library.json')
    native=ROOT/'dist/native'
    (native/'native_runtime.json').write_text(json.dumps(dict(workspace=str(ROOT),
        pythonw=str(Path(sys.executable).with_name('pythonw.exe')))),encoding='utf-8')
    config=PROFILE/'region_config.txt'
    lines=config.read_text(encoding='utf-8').splitlines() if config.exists() else []
    lines=[v for v in lines if not v.startswith('gamelog=')]
    lines.append('gamelog='+str(game/'Game.log'))
    config.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    progress('Preparing SynthStrings using your own game text…')
    if not refreshed and (game/'Data/Localization/english/global.ini').exists():
        return 'Existing localization preserved. Reputation labels refresh after account verification.'
    backup=PROFILE/'localization_backups'/('setup_'+time.strftime('%Y%m%d_%H%M%S'))
    for relative in ['Data/Localization/english/global.ini','user.cfg']:
        existing=game/relative
        if existing.exists():
            backup.mkdir(parents=True,exist_ok=True)
            shutil.copy2(existing,backup/existing.name)
    report=PROFILE/'strings_setup.txt'
    result=subprocess.run([str(native/'SynthScan.exe'),'--setup-texts',str(game),str(report)],
                          cwd=native,creationflags=0x08000000,timeout=300)
    note=report.read_text(encoding='utf-8',errors='replace') if report.exists() else 'No setup response'
    if result.returncode not in (0,2):raise RuntimeError('SynthStrings preparation failed')
    progress(note)
    (PROFILE/'setup_result.json').write_text(json.dumps(dict(schema=1,game_dir=str(game),
        strings_installed=result.returncode==0,strings_note=note)),encoding='utf-8')
    return note


if __name__=='__main__':prepare()
