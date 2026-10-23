"""Exercise the actual merge path without opening Tk or writing user records."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from hud_controller import TopTelemetryHUD
from hud_appearance import render_original_bar
from telemetry_core import EvidenceHealth, IncrementalGameLog, MetricStore, ShardHistory, utc_iso
from session_store import ServerLogManager


class HudMergeTests(unittest.TestCase):
    def setUp(self):
        frame_patch = patch('hud_controller.read_client_fps', return_value=None)
        frame_patch.start()
        self.addCleanup(frame_patch.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.now = time.time()
        self.clock = lambda: self.now
        self.path = self.root / "Game.log"
        self.path.write_text(self.join(self.now))
        hud = TopTelemetryHUD.__new__(TopTelemetryHUD)
        hud.log_reader = IncrementalGameLog(self.path)
        hud.shard_tracker = ShardHistory(self.root / "shard_history.json", self.clock)
        hud.server_logger = ServerLogManager(self.root / "server_log.json", clock=self.clock)
        hud.metric_store = MetricStore()
        hud.health_evaluator = EvidenceHealth(self.clock)
        hud.medical_imprint = "USER PROVIDED"
        hud.on_health_alert_cb = None
        hud._server_identity = None
        hud.state = {}
        self.hud = hud
        self.update()

    def tearDown(self):
        self.directory.cleanup()

    def join(self, at):
        return f"<{utc_iso(at)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[pub_use1b_100_020]\n"

    def update(self, sample=None, running=True):
        with patch("hud_controller.time.time", self.clock):
            self.hud.update_from_image_and_logs(sample, redraw=False, game_running=running)

    def append(self, value):
        with self.path.open("a") as stream:
            stream.write(value)

    def test_no_telemetry_does_not_become_healthy(self):
        self.assertEqual(self.hud.state["health"]["status"], "UNKNOWN")
        self.assertIsNone(self.hud.state["ping_ms"])
        self.assertIsNone(self.hud.state["shard_pop"])

    def test_disconnect_clears_visible_and_historical_active_state(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now, "server_fps": 22, "shard_pop": 500})
        self.append("Connection closed\n")
        self.update()
        self.assertEqual(self.hud.state["shard_id"], "--")
        self.assertIsNone(self.hud.state["server_fps"])
        self.assertIsNone(self.hud.server_logger.get_active_session())

    def test_stale_population_and_identity_expire_together(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now, "shard_pop": 500, "server_name": "GAME-2"})
        self.assertEqual(self.hud.state["server_name"], "GAME-2")
        self.now += 6
        self.update()
        self.assertIsNone(self.hud.state["shard_pop"])
        self.assertEqual(self.hud.state["server_name"], "--")

    def test_same_shard_rejoin_rejects_queued_old_capture(self):
        old = self.hud.state["session_token"]
        self.now += 10
        self.append("Connection closed\n" + self.join(self.now))
        self.update({"_session_token": old, "_observed_at": self.now, "ping_ms": 25, "server_name": "GAME-2"})
        self.assertIsNone(self.hud.state["ping_ms"])
        self.assertEqual(self.hud.state["server_name"], "--")
        self.assertIn("RETURN #2", self.hud.state["hop_status"])

    def test_game_exit_clears_without_needing_a_final_log_event(self):
        self.update(running=False)
        self.assertFalse(self.hud.state["session_token"])
        self.assertIsNone(self.hud.server_logger.get_active_session())

    def test_old_mining_result_is_cleared_on_session_change(self):
        self.hud.mining = dict(signature=3170,session_token=self.hud.state['session_token'])
        self.now += 1
        self.append(self.join(self.now))
        self.update()
        self.assertIsNone(self.hud.mining)

    def test_starting_companion_with_game_closed_does_not_create_a_join(self):
        self.hud.log_reader = IncrementalGameLog(self.path)
        self.hud.server_logger = ServerLogManager(self.root / "closed-game-sessions.json", clock=self.clock)
        self.update(running=False)
        self.assertEqual(self.hud.server_logger.sessions, [])
        self.assertEqual(self.hud.log_reader.last_pos, 0)

    def test_disabling_hud_does_not_disable_collection(self):
        self.hud.enabled = False
        self.append(f"<{utc_iso(self.now)}> Server FPS 10.0\n")
        self.update()
        self.assertEqual(self.hud.state["server_fps"], 10)

    def test_late_old_server_identity_cannot_follow_a_rejoin(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now, "server_name": "GAME-2"})
        self.now += 1
        self.append(self.join(self.now))
        self.update()
        self.assertEqual(self.hud.state["server_name"], "--")

    def test_partial_screen_anchor_is_not_accepted_as_telemetry(self):
        self.hud.bitmap_reader = Mock()
        self.hud.bitmap_reader.parse_image.side_effect = [
            {"shard_id": "--"}, {"server_fps": 2.5, "ping_ms": 50, "server_name": "--", "detected_lines": 6}]
        result = self.hud.parse_captured_image_background(object(), self.hud.state["session_token"])
        self.assertIsNone(result["server_fps"])
        self.assertIsNone(result["ping_ms"])

    def test_impossible_local_population_is_rejected(self):
        self.hud.bitmap_reader = Mock()
        self.hud.bitmap_reader.parse_image.side_effect = [
            {"shard_id": "--"}, {"server_fps": 20, "server_name": "GAME-2", "restarts": 0,
                                    "shard_pop": 10, "srv_pop": 100,
                                    "_validated_fields": ["server_fps", "server_name", "shard_pop", "srv_pop"]}]
        result = self.hud.parse_captured_image_background(object(), self.hud.state["session_token"])
        self.assertIsNone(result["shard_pop"])

    @unittest.skipUnless((Path(__file__).parent/'fixtures/displayinfo/clear.png').exists(),'Private capture fixture is not distributed')
    def test_real_frame_is_merged_without_needing_a_restart_reading(self):
        import cv2
        from validated_displayinfo import ValidatedDisplayInfoReader
        self.hud.bitmap_reader = ValidatedDisplayInfoReader()
        image = cv2.imread(str(Path(__file__).parent / "fixtures" / "displayinfo" / "clear.png"))
        result = self.hud.parse_captured_image_background(image, self.hud.state["session_token"],
                                                         observed_at=self.now-2)
        self.assertIsNone(result["restarts"])
        self.update(result)
        self.assertEqual(self.hud.state["ping_ms"], 8.4)
        self.assertEqual(self.hud.state["shard_pop"], 470)
        self.assertEqual(self.hud.state["srv_pop"], 83)
        self.assertEqual(self.hud.state["metric_meta"]["ping_ms"]["age_seconds"], 2)

    def test_server_transition_inside_shard_does_not_keep_previous_node_fps(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now, "server_name": "GAME-2", "server_fps": 20})
        self.now += 1
        self.update({"_session_token": token, "_observed_at": self.now, "server_name": "GAME-3", "server_fps": None})
        self.assertIsNone(self.hud.state["server_fps"])
        self.assertEqual(self.hud.state["server_name"], "GAME-3")

    def test_delayed_capture_cannot_refresh_a_stale_server_name(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now - 6, "server_name": "GAME-2", "server_fps": 20})
        self.assertEqual(self.hud.state["server_name"], "--")
        self.assertIsNone(self.hud.state["server_fps"])

    def rendered_text(self):
        """Inspect the real canvas output, without showing a window."""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            self.hud.bar_canvas = tk.Canvas(root)
            self.hud.bar_width = 1680
            self.hud.BAR_HEIGHT = 24
            self.hud.compact = True
            self.hud._last_rendered_key = None
            render_original_bar(self.hud)
            return [self.hud.bar_canvas.itemcget(item, "text")
                    for item in self.hud.bar_canvas.find_all()
                    if self.hud.bar_canvas.type(item) == "text"]
        finally:
            root.destroy()
            self.hud.bar_canvas = None

    def test_missing_metrics_and_manual_medical_note_are_not_displayed(self):
        # A reader can retain a historical count after the metric store expires.
        self.hud.log_reader.entities = 98765
        texts = self.rendered_text()
        combined = " | ".join(texts)
        for unavailable in ("PING:", "ENT:", "POP:", "SRV FPS:", "HEALTH:",
                            "PU: ONLINE", "MED:", "USER PROVIDED", "98,765"):
            self.assertNotIn(unavailable, combined)
        self.assertIn("SHARD 020", combined)
        self.assertTrue(any("VISIT" in text for text in texts))

    def test_expired_metrics_leave_no_visible_labels_or_stale_entity_fallback(self):
        token = self.hud.state["session_token"]
        self.update({"_session_token": token, "_observed_at": self.now,
                     "server_fps": 22, "ping_ms": 25, "entities": 12345, "shard_pop": 500})
        texts = self.rendered_text()
        self.assertIn("PING:", texts)
        self.assertIn("ENT:", texts)
        self.assertIn("12,345", texts)
        self.assertIn("SRV FPS: 22.0", texts)
        self.hud.log_reader.entities = 12345
        self.now += 6
        self.update()
        combined = " | ".join(self.rendered_text())
        for expired in ("PING:", "ENT:", "POP:", "SRV FPS:", "12,345"):
            self.assertNotIn(expired, combined)

    def test_observed_connection_warning_still_appears_without_numeric_telemetry(self):
        self.hud.state["health"] = self.hud.health_evaluator.evaluate(
            is_in_server=True, connection_status="recovering")
        self.assertIn("SERVER RECOVERING", self.rendered_text())

    def test_packet_latency_reaches_canvas_with_its_source_label(self):
        sample = {'ping_ms': 12.5, 'source': 'game_udp_ping_pong', 'observed_at': self.now}
        with patch('hud_controller.read_network_ping', return_value=sample):
            self.update()
        texts = self.rendered_text()
        self.assertIn('NET RTT:', texts)
        self.assertIn('12.5ms', texts)
        self.assertNotIn('PING:', texts)
        self.now += 6
        with patch('hud_controller.read_network_ping', return_value=None):
            self.update()
        self.assertNotIn('NET RTT:', self.rendered_text())

    def test_player_fps_has_an_independent_visible_field(self):
        sample = {'client_fps': 60, 'source': 'presentmon_application_presents', 'observed_at': self.now}
        with patch('hud_controller.read_client_fps', return_value=sample):
            self.update()
        texts = self.rendered_text()
        self.assertIn('PLAYER FPS:', texts)
        self.assertIn('60', texts)
        self.assertFalse(any('SRV FPS:' in text for text in texts))


if __name__ == "__main__":
    unittest.main()
