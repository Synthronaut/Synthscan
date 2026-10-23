"""Isolated test-window render and bridge spool check; never uses real fixes."""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rock_navigation import RockNavigation
from native_bridge import SessionService

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--output',required=True);p.add_argument('--with-session-timeline',action='store_true');a=p.parse_args()
    out=Path(a.output).resolve()
    if out.exists():raise ValueError('Use a new isolated output directory')
    out.mkdir(parents=True);profile=out/'navigation_fixture';profile.mkdir()
    nav=RockNavigation(profile);body=nav.bodies['Nyx/Space test'];now=time.time()
    fix=dict(xyz_m=[1e10,2e10,3e10],received_at=now,full_shard_id='DEMO-shard',frame='system_global_unverified',units='m',source='/showlocation clipboard')
    mark=dict(id='fixture',body_id=body['id'],name='DEMO · Station return test',stand_off_m=50,fix=fix,model_fingerprint=body['fingerprint'],rotation_check=dict(at=now,elapsed_s=60,error_m=1.2,passed=True))
    nav.marks=[mark];nav.selected='fixture';nav.fix=dict(fix,xyz_m=[1e10+1000,2e10,3e10]);nav.message='SYNTHETIC FIXTURE · no real player coordinates or field success'
    view=nav.tick(dict(session_token='fixture',game_pids=[42],full_shard_id='DEMO-shard'))
    (out/'navigation_test_model.json').write_text(json.dumps(view),encoding='utf-8');nav.close()
    if a.with_session_timeline:
        from session_timeline import timeline
        records=[]
        for key,joined,left,shard in [('a','2026-10-20T07:00:00Z',None,'020'),('b','2026-10-21T07:00:00.123Z','2026-10-21T10:00:00.987Z','020'),('c','2026-10-21T13:00:00Z',None,'042')]:
            records.append(dict(id=key,joined_at=joined,left_at=left,full_shard_id='pub_use1b_100_'+shard,shard_id=shard,
                                region_raw='use1b',region_display='US-EAST',server_name='DEMO · Example shard',active=key=='c',
                                joined_time_source='game_log_timestamp',left_time_source='game_log_timestamp',locations=[],notes='Synthetic session fixture only'))
        model=timeline(records,time.time())
        (out/'session_test_model.json').write_text(json.dumps(dict(session_log=model,session_rows=model['rows'])),encoding='utf-8')
    (out/"piracy_test_model.json").write_text(json.dumps(dict(session_token="fixture",identity="DEMO SHARD · US-EAST · FIRST VISIT",interdictions=dict(current_count=2,current=[dict(target="DEMO PILOT · synthetic",at=time.time()-45),dict(target="DEMO SECOND PILOT",at=time.time()-120)]))),encoding="utf-8")
    piracy_path=out/'piracy_test_model.json'
    piracy=json.loads(piracy_path.read_text(encoding='utf-8'));at=time.time()
    piracy['piracy_watch']=dict(fresh=True,observed_at=at,status='DEMO · synthetic DisplayInfo readings',metrics=dict(shard_pop=483,srv_pop=86,server_fps=26.5,ping_ms=42.3),delta_5m=12,delta_15m=-4,waiting_s=923,waiting_active=False,points=[dict(at=at-900+i*5,value=480+i%12) for i in range(181)])
    piracy_path.write_text(json.dumps(piracy),encoding='utf-8')
    subprocess.run([sys.executable,'-B',str(ROOT/'tools/verify_mining_diary.py'),'--binary',a.binary,'--output',str(out)],check=True,timeout=180)
    result=json.loads((out/'ui_test.json').read_text());assert result['navigation_arm_route'],result
    if "piracy_mode_pauses_scanner" in result:assert result["piracy_mode_pauses_scanner"] and result["mining_mode_restores_scanner"] and result["piracy_blocks_mining_diary"],result
    if 'piracy_compact_wide_opaque' in result:
        assert result['piracy_compact_wide_opaque'] and result['piracy_details_expand'],result
    assert result['automatic_attach_starts_topmost_overlay'],result
    assert result['automatic_placement_loaded_without_activation'],result
    assert result['activity_topmost_restored_without_activation'],result
    assert result['activity_collapse_preserves_server_setting'] and result['activity_expand_restores_position_and_tab'] and result['activity_tabs_visible'],result
    assert result['hud_drag_while_game_active'] and result['hud_lock_clickthrough'],result
    if a.with_session_timeline:assert result['session_columns']==7 and result['session_rows']==3 and result['session_filter_route'],result
    service=SessionService(out/'spool_profile',out/'Game.log')
    try:
        service.navigation_context=dict(session_token='test',game_pids=[42],full_shard_id='DEMO-shard')
        service.navigation.clipboard_factory=lambda:(_ for _ in ()).throw(ValueError('Synthetic no-clipboard fixture'))
        folder=out/'spool_profile/diary_commands';folder.mkdir()
        for i,command in enumerate([dict(id='arm-test',action='nav_arm',session_token='test',body_id='Nyx/Space test'),dict(id='cancel-test',action='nav_cancel')]):
            (folder/f'{i:03}.json').write_text(json.dumps(command))
        service.diary_commands();assert not list(folder.glob('*.json'))
        assert service.navigation.result['command_id']=='cancel-test' and not service.navigation.result['error']
        assert 'arm-test' in service.seen_commands
    finally:service.close()
    (out/'navigation_verification.json').write_text(json.dumps(dict(native_arm_route=True,ordered_bridge_commands=True,synthetic_only=True,at=time.time()),indent=2))
    print('Navigation window and ordered bridge commands verified with isolated fixtures.')

if __name__=='__main__':main()
