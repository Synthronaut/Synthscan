import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from voice_dictation import VoiceDictationService
from companion_features import CompanionService


class TestVoiceDictation(unittest.TestCase):
    def test_voice_dictation_singleton(self):
        svc1 = VoiceDictationService.get_instance()
        svc2 = VoiceDictationService.get_instance()
        self.assertIs(svc1, svc2)
        self.assertIsInstance(svc1.is_available, bool)
        self.assertFalse(svc1.is_recording)

    def test_voice_dictation_empty_audio_returns_empty(self):
        svc = VoiceDictationService()
        svc._is_recording = True
        svc._frames = [b"123"] # Too short (< 3200 bytes)
        svc._capture_device = Mock()
        text = svc.stop_recording_and_recognize()
        self.assertEqual(text, "")
        self.assertFalse(svc.is_recording)

    def test_companion_features_voice_dictation_flow(self):
        import tempfile, time, uuid
        with tempfile.TemporaryDirectory() as td:
            cs = CompanionService(td, 999999, social=Mock(), market=Mock())
            cs.session = "test-session"
            mock_vd = Mock()
            mock_vd.is_available = True
            mock_vd.start_recording.return_value = True
            mock_vd.stop_recording_and_recognize.return_value = "Heading to Port Tressler"
            cs.voice_dictation = mock_vd
            now = time.time()

            # 1. Start voice dictation
            cmd_start = {
                "id": f"cmd-v-{uuid.uuid4().hex}",
                "owner_pid": 999999,
                "at": now,
                "action": "start_voice_dictation",
                "session_token": "test-session",
            }
            cs.command(cmd_start, now)
            self.assertTrue(cs.voice_dictating)
            mock_vd.start_recording.assert_called_once()

            # 2. Stop voice dictation with auto-send
            cmd_stop = {
                "id": f"cmd-v-{uuid.uuid4().hex}",
                "owner_pid": 999999,
                "at": now,
                "action": "stop_voice_dictation",
                "session_token": "test-session",
                "send": True,
                "group_id": "group-global",
                "encode_zh": False,
            }
            cs.command(cmd_stop, now)
            self.assertFalse(cs.voice_dictating)
            self.assertEqual(cs.last_dictated_text, "Heading to Port Tressler")
            self.assertIn("chat_send", cs.jobs)
            mock_vd.stop_recording_and_recognize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
