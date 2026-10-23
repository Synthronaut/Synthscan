import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import snare_trace_probe as probe

class SnareTraceProbeTests(unittest.TestCase):
    def test_filter_preserves_other_channels_and_adds_local_control(self):
        base=dict(Version=2,Log=[dict(Severity=['Notice'])],Publish=[],Dialog=[],**{'UserHandler1:MiniDump':[]})
        before=copy.deepcopy(base);result=probe.diagnostic_filter(base)
        self.assertEqual(base,before)
        self.assertEqual(result['Log'],base['Log']);self.assertEqual(result['Dialog'],[])
        self.assertIn('Local Trace Config loaded',result['Publish'][0]['Include Events'])
        self.assertIn('Interdiction',result['Publish'][0]['Include Events'])
    def test_process_environment_is_local_and_not_installed(self):
        before=dict(os.environ);values=probe.diagnostic_environment(Path('fixture'))
        self.assertEqual(os.environ,before)
        self.assertEqual(values['SYSTEM_TRACE_SERVICE_ENABLED'],'0')
        self.assertIn('fixture',values['SYSTEM_TRACE_OUTPUT_DIRECTORY'])
    def test_never_launches_over_an_existing_game_or_launcher(self):
        for names in [{'starcitizen.exe'},{'rsi launcher.exe'}]:
            with patch.object(probe,'running_names',return_value=names),patch.object(probe.subprocess,'Popen') as launch:
                with self.assertRaises(RuntimeError):probe.launch()
                launch.assert_not_called()
    def test_preparation_and_empty_status_do_not_claim_success(self):
        base=dict(Version=2,Log=[],Publish=[])
        raw=json.dumps(base).encode()+b'\0'
        self.assertEqual(probe.default_filter(raw),base)
        with self.assertRaises(ValueError):probe.default_filter(b'unknown build')
        with tempfile.TemporaryDirectory() as tmp:
            result=probe.status(Path(tmp));self.assertFalse(result['catch_detection_verified']);self.assertEqual(result['files'],[])

    def test_status_handles_json_escaped_paths_and_rejects_old_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'events').mkdir()
            (folder/'probe_manifest.json').write_text(json.dumps(dict(environment=dict(SYSTEM_TRACE_OUTPUT_FILENAME='SynthScanSnareTrace_current'))))
            control=json.dumps(dict(event='Local Trace Config loaded',path=str(folder/'trace_filter.json')))
            (folder/'events/SynthScanSnareTrace_current.json').write_text(control)
            (folder/'events/SynthScanSnareTrace_old.json').write_text(control)
            result=probe.status(folder)
            self.assertEqual(result['local_filter_load_records'],1)
            self.assertEqual(len(result['files']),1)
            self.assertFalse(result['catch_detection_verified'])

if __name__=='__main__':unittest.main()
