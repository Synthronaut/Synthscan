import unittest
from native_session_hud import hud_state

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

if __name__=='__main__':unittest.main()
