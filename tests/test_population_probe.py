import unittest
from unittest.mock import patch
from types import SimpleNamespace
from tools.probe_population_service import projection,probe,safe_rpc_details,configure_own_request


class PopulationProbeTests(unittest.TestCase):
    def test_each_request_uses_verified_local_identity(self):
        client=SimpleNamespace(subject='own-player-urn',metadata=(('account_id','123'),('player_id','456')))
        request=SimpleNamespace()
        configure_own_request(request,client,'social')
        self.assertEqual(request.player_urn,'own-player-urn')
        request=SimpleNamespace()
        configure_own_request(request,client,'contacts')
        self.assertEqual(vars(request),dict(account_id=123,player_id=456))
        with self.assertRaises(ValueError):configure_own_request(request,client,'unknown')

    def test_validation_details_exclude_credentials_and_own_identity(self):
        client=SimpleNamespace(subject='urn:sc:global:player:geid:123456789',
            metadata=(('authorization','Bearer secret-token'),('account_id','987654321')))
        error=SimpleNamespace(details=lambda:'invalid player urn:sc:global:player:geid:123456789 account 987654321 Bearer secret-token')
        result=safe_rpc_details(error,client)
        for value in ('123456789','987654321','secret-token'):
            self.assertNotIn(value,result)
        self.assertIn('invalid player',result)

    def test_closed_game_never_reads_credentials_or_opens_a_client(self):
        with patch('app_lifecycle.game_process_ids',return_value=set()),patch('game_account.OwnAccount') as client:
            self.assertEqual(probe(),dict(status='blocked_game_closed',requests_sent=0))
            client.assert_not_called()

    def test_empty_or_other_shard_response_does_not_confirm_current_population(self):
        info=SimpleNamespace(id='other-shard',dgs_id='server',player_count=0,total_players=0)
        self.assertFalse(projection(info,True,'current-shard')['matches_current_log_shard'])
        info.id=''
        self.assertFalse(projection(info,True,'')['matches_current_log_shard'])
        info.id='current-shard'
        result=projection(info,True,'current-shard')
        self.assertTrue(result['matches_current_log_shard'])
        self.assertFalse(result['semantics_verified'])
