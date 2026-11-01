import unittest
from unittest.mock import patch
from tools.gpu_diagnostics import preflight,assessment,KillOnCloseJob


class GPUCheckTests(unittest.TestCase):
    def test_active_game_prevents_gpu_tool_and_sensor_start(self):
        with patch('tools.gpu_diagnostics.game_process_ids',return_value={123}),patch('tools.gpu_diagnostics.verify') as verify,patch('tools.gpu_diagnostics.gpu_sample') as sample:
            self.assertFalse(preflight()['ok']);verify.assert_not_called();sample.assert_not_called()

    def test_only_completed_valid_error_free_run_can_have_clean_observation(self):
        self.assertEqual(assessment('duration_reached',81,True,False,602),'no_errors_observed_in_this_run')
        for args in [('duration_reached',81,False,False,602),('duration_reached',81,True,False,10),('duration_reached',0,True,False,602),('gpu_core_temperature_guard',81,True,False,602),('duration_reached',85,True,False,602)]:
            self.assertEqual(assessment(*args),'inconclusive')
        self.assertEqual(assessment('duration_reached',83,True,False,602),'errors_detected')
        self.assertEqual(assessment('tool_exited',0,False,True,4),'errors_detected')

    def test_diagnostic_job_can_be_created_and_closed_without_starting_load(self):
        job=KillOnCloseJob();job.close();self.assertIsNone(job.handle)

    def test_closing_job_terminates_only_its_dummy_child(self):
        import subprocess,sys
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
        job=KillOnCloseJob()
        try:
            job.assign(child);job.close()
            self.assertIsNotNone(child.wait(timeout=5))
        finally:
            job.close()
            if child.poll() is None:child.kill();child.wait(timeout=5)
