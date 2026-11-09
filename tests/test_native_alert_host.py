import unittest
from native_alert_host import fresh_token


class AlertSessionTests(unittest.TestCase):
    def test_only_live_same_owner_same_shard_identity_can_show_alerts(self):
        row=dict(owner_pid=12,written_at=100,session_token='join-a',full_shard_id='pub_use1b_12881860_310',game_pids=[19])
        self.assertEqual(fresh_token(row,12,101),'join-a')
        for changes in (dict(owner_pid=13),dict(written_at=90),dict(written_at=102),dict(game_pids=[]),dict(full_shard_id='unknown'),dict(session_token=None)):
            self.assertIsNone(fresh_token(dict(row,**changes),12,101))
