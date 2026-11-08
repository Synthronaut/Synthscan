import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from native_session_hud import hud_state,RibbonSessionState
from native_bridge import ribbon_snapshot

class NativeSessionHUDTests(unittest.TestCase):
    def snapshot(self):
        return dict(owner_pid=42,written_at=100,session_token='join',full_shard_id='pub_use1b_12881860_200',
                    shard_name='TEST NAME',region='US-EAST',hop='RETURN #2',location='',game_pids=[9])
    def test_native_identity_uses_existing_name_and_full_shard(self):
        state=hud_state(self.snapshot(),42,101)
        self.assertEqual(state['callsign'],'TEST NAME');self.assertEqual(state['shard_id'],'200')
        self.assertEqual(state['region_display'],'US-EAST');self.assertEqual(state['hop_status'],'RETURN #2')
    def test_wrong_owner_or_stale_bridge_hides_session(self):
        for owner,now in [(99,101),(42,105),(42,99)]:
            self.assertIsNone(hud_state(self.snapshot(),owner,now)['session_token'])
    def test_source_timestamps_are_not_freshened_by_bridge_publication(self):
        snapshot=self.snapshot();snapshot['hud_state']=dict(client_fps=60,ping_ms=45,
            metric_meta=dict(client_fps=dict(observed_at=98),ping_ms=dict(observed_at=100,source='game_udp_ping_pong')))
        state=hud_state(snapshot,42,101)
        self.assertNotIn('client_fps',state);self.assertEqual(state['ping_ms'],45)
        self.assertEqual(state['metric_meta']['ping_ms']['source'],'game_udp_ping_pong')
    def test_main_menu_does_not_reuse_previous_shard(self):
        snapshot=self.snapshot();snapshot.update(session_token=None,full_shard_id='',shard_name='Main menu')
        state=hud_state(snapshot,42,101)
        self.assertEqual(state['connection_status'],'main_menu');self.assertEqual(state['shard_id'],'--')

    def test_brief_delay_retains_only_labelled_identity_for_same_game(self):
        view=RibbonSessionState();snapshot=self.snapshot()
        snapshot['hud_state']=dict(client_fps=60,ping_ms=45,server_fps=30,shard_pop=80,location_display='Old location',metric_meta={})
        view.update(snapshot,42,101)
        state=view.update(snapshot,42,105,{9})
        self.assertEqual(state['callsign'],'TEST NAME');self.assertEqual(state['shard_id'],'200')
        self.assertTrue(state['last_known_identity']);self.assertEqual(state['connection_status'],'refreshing')
        self.assertIsNone(state['session_token']);self.assertIn('LAST KNOWN',state['feed_status'])
        for field in ('client_fps','ping_ms','server_fps','shard_pop','location_display','metric_meta'):
            self.assertNotIn(field,state)

    def test_missing_or_unreadable_snapshot_has_bounded_grace(self):
        view=RibbonSessionState();view.update(self.snapshot(),42,101)
        self.assertEqual(view.update({},42,105,{9})['connection_status'],'refreshing')
        self.assertEqual(view.update({},42,129,{9})['connection_status'],'refreshing')
        self.assertEqual(view.update({},42,130,{9})['connection_status'],'unavailable')

    def test_exit_or_new_game_process_prevents_identity_retention(self):
        for games in (set(),{10},None):
            view=RibbonSessionState();view.update(self.snapshot(),42,101)
            state=view.update({},42,105,games)
            self.assertNotIn('last_known_identity',state)
            self.assertIsNone(view.last)

    def test_confirmed_menu_clears_retained_identity_immediately(self):
        view=RibbonSessionState();view.update(self.snapshot(),42,101)
        snapshot=self.snapshot();snapshot.update(written_at=105,session_token=None,full_shard_id='',shard_name='Main menu')
        self.assertEqual(view.update(snapshot,42,106)['connection_status'],'main_menu')
        self.assertNotIn('last_known_identity',view.update({},42,110,{9}))

    def test_newer_but_delayed_hop_never_reuses_old_shard(self):
        view=RibbonSessionState();view.update(self.snapshot(),42,101)
        snapshot=self.snapshot();snapshot.update(written_at=102,session_token='join-two',full_shard_id='pub_use1b_12881860_201')
        self.assertEqual(view.update(snapshot,42,107,{9})['connection_status'],'unavailable')

    def test_fresh_hop_replaces_retained_identity_and_removes_updating(self):
        view=RibbonSessionState();view.update(self.snapshot(),42,101);view.update({},42,105,{9})
        snapshot=self.snapshot();snapshot.update(written_at=106,session_token='new',full_shard_id='pub_use1b_12881860_201',shard_name='Second shard')
        state=view.update(snapshot,42,107)
        self.assertEqual(state['shard_id'],'201');self.assertEqual(state['session_token'],'new')
        self.assertNotIn('last_known_identity',state);self.assertNotIn('feed_status',state)

    def test_wrong_owner_or_clock_reversal_clears_retained_identity(self):
        for other,now in [(dict(self.snapshot(),owner_pid=99),105),({},99)]:
            view=RibbonSessionState();view.update(self.snapshot(),42,101)
            self.assertNotIn('last_known_identity',view.update(other,42,now,{9}))

    def test_small_ribbon_snapshot_excludes_optional_heavy_data_without_freshening_metrics(self):
        snapshot=self.snapshot();snapshot.update(diary={'large':'payload'},questing={'slow':'collector'},hud_state={'metric_meta':{'ping_ms':{'observed_at':98}}},interdictions={'alerts':[{'id':'live-alert'}]})
        result=ribbon_snapshot(snapshot)
        self.assertNotIn('diary',result);self.assertNotIn('questing',result)
        self.assertEqual(result['written_at'],100)
        self.assertEqual(result['hud_state']['metric_meta']['ping_ms']['observed_at'],98)
        self.assertEqual(result['interdictions']['alerts'][0]['id'],'live-alert')

    def test_actual_ribbon_painter_keeps_identity_and_shows_updating_without_stale_stats(self):
        from hud_appearance import render_original_bar
        view=RibbonSessionState();view.update(self.snapshot(),42,101)
        state=view.update({},42,105,{9})
        canvas=Mock();canvas.bbox.return_value=(0,0,100,16)
        hud=SimpleNamespace(state=state,bar_canvas=canvas,bar_width=1600,BAR_HEIGHT=24,compact=True)
        render_original_bar(hud)
        text=' | '.join(str(call.kwargs.get('text','')) for call in canvas.create_text.call_args_list)
        self.assertIn('TEST NAME',text);self.assertIn('SHARD 200',text)
        self.assertIn('UPDATING · LAST KNOWN SHARD',text)
        for label in ('PLAYER FPS:','SRV FPS:','PING:','MAIN MENU'):
            self.assertNotIn(label,text)

if __name__=='__main__':unittest.main()
