import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import reputation_trace_probe as probe


class ReputationProbeTests(unittest.TestCase):
    def test_signed_score_and_json_message_are_candidates_only(self):
        message = ('Received reputation update from push message for: subject 123 - '
                   'entity 66bfae03-86c1-4982-977b-09bfcfc05e1a - '
                   'scope: e23f8034-3e76-49b3-bfc6-228bcb1381df - score -250 - standing example')
        candidate = probe.parse_score_candidate(json.dumps({'message': message}))
        self.assertEqual(candidate['score'], -250)
        self.assertFalse(candidate['own_account_verified'])
        self.assertIsNone(probe.parse_score_candidate(message.replace('-250', str(2**32))))
        self.assertIsNone(probe.parse_score_candidate(message.replace('subject 123', 'subject null')))

    def test_task_text_or_unrendered_template_cannot_supply_balance(self):
        self.assertIsNone(probe.parse_score_candidate('Mission completed reputation +1000'))
        self.assertIsNone(probe.parse_score_candidate('subject $$ - entity $$ - scope: $$ - score $$ - standing %%'))
        self.assertIsNone(probe.parse_score_candidate('{"score":1000}'))

    def test_old_run_or_wrong_filter_cannot_establish_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / 'events').mkdir()
            prefix = 'SynthScanReputationTrace_0123456789'
            manifest = {'environment': {'SYSTEM_TRACE_OUTPUT_FILENAME': prefix}}
            manifest_path = profile / 'probe_manifest.json'
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(probe.status(profile)['state'], 'prepared_only')
            manifest['launch_requested_at'] = time.time() - 2
            manifest_path.write_text(json.dumps(manifest))
            control = json.dumps({'event': 'Local Trace Config loaded', 'path': str(profile / 'trace_filter.json')})
            (profile / 'events/SynthScanReputationTrace_aaaaaaaaaa.json').write_text(control)
            current = profile / 'events' / (prefix + '.json')
            current.write_text('Local Trace Config loaded wrong/path.json')
            self.assertFalse(probe.status(profile)['trace_ready'])
            current.write_text(control)
            result = probe.status(profile)
            self.assertTrue(result['trace_ready'])
            self.assertFalse(result['live_balance_verified'])
            self.assertEqual(len(result['files']), 1)

    def test_never_closes_or_launches_over_existing_game_or_launcher(self):
        for names in ({'starcitizen.exe'}, {'rsi launcher.exe'}):
            with patch.object(probe, 'running_names', return_value=names), patch.object(probe.subprocess, 'Popen') as launch:
                with self.assertRaises(RuntimeError):
                    probe.launch()
                launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
