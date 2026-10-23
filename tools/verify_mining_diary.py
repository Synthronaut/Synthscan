"""Isolated native diary rendering and capture/bridge checks. No game input.

All records/photos here are synthetic fixtures, never the player's achievements.
"""
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mining_diary import MiningDiary,render_card
from native_bridge import SessionService

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binary',default=str(ROOT/'dist/diary-stage/SynthScan.exe'));parser.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'data').exists():raise ValueError('Use a new output directory for each isolated run')
    binary=Path(args.binary).resolve()
    if not (binary.parent/'workspace_library.json').exists():shutil.copy2(ROOT/'dist/native/workspace_library.json',binary.parent/'workspace_library.json')
    diary=MiningDiary(out/'fixture_profile')
    try:
        rock=diary.save(dict(kind='scanned',title='DEMO · The Wala giant',material='Quantanium',mass_kg=98000,quality=900,
                            system='Stanton',location='Wala',ship='MOLE',crew='Example crew',patch='4.10.2',
                            notes='Synthetic UI fixture, not a real discovery. A memory worth sharing with the crew.'))
        for kind,material,scu,mass,proceeds in [('mined','Gold',None,75000,None),('haul','Gold + Bexalite',126,None,None),('refined','Gold',109,None,None),('sale','Gold',None,None,3200000)]:
            diary.save(dict(kind=kind,title='DEMO · '+kind,material=material,scu=scu,mass_kg=mass,proceeds=proceeds,system='Stanton',location='Wala',ship='MOLE',patch='4.10.2'))
        (out/'diary_test_model.json').write_text(json.dumps(diary.view(),ensure_ascii=False),encoding='utf-8')
        render_card(rock,out/'share_fixture.png',dict(location=True,crew=True,notes=True,name='Example Captain'))
    finally:diary.close()
    env=dict(os.environ,SYNTHSCAN_DATA_DIR=str(out/'selftest_profile'))
    r=subprocess.run([str(binary),'--selftest'],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    (out/'selftest.json').write_text(json.dumps(dict(exit=r.returncode,passed=r.stdout.count('[PASS]'),stdout=r.stdout,stderr=r.stderr),indent=2),encoding='utf-8')
    assert r.returncode==0,r.stderr
    ui=subprocess.run([str(binary),'--ui-test',str(out)],env=env,capture_output=True,timeout=60)
    assert ui.returncode==0,ui.stderr
    result=json.loads((out/'ui_test.json').read_text(encoding='utf-8'))
    assert result['diary_native_encounters']==1,result
    assert result['diary_editor_route'] and result['diary_share_route'],result
    from PIL import Image,ImageStat
    with Image.open(out/'workspace_6.png') as image:
        assert max(ImageStat.Stat(image.convert('RGB')).mean)<180,'Native share preview rendered blank'
    log=out/'Game.log';log.write_text('')
    service=SessionService(out/'data',log)
    try:
        state=service.tick(False)
        assert state['diary']['count']==1
        entry=state['diary']['rows'][0]['entry']
        assert entry['mass_kg']==98000 and entry['kind']=='scanned'
        # Exercise the production ordered-command spool, including a duplicate.
        folder=out/'data/diary_commands';folder.mkdir()
        command=dict(id='spooled-save',action='diary_save',entry=dict(kind='haul',title='DEMO spool',material='Gold',scu=42))
        for i in range(2):(folder/f'{i:03}.json').write_text(json.dumps(command),encoding='utf-8')
        service.diary_commands();state=service.tick(False)
        assert state['diary']['count']==2
        assert state['diary']['records'][2]['value']=='42 SCU'
        assert not list(folder.glob('*.json'))
    finally:service.close()
    result.update(native_selftests=r.stdout.count('[PASS]'),capture_bridge=True,ordered_command_spool=True,
                  synthetic_fixtures_only=True,at=time.time())
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
