"""Regression tests use temporary records only: never import the old test scripts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_core import EvidenceHealth, IncrementalGameLog, MetricStore, ShardHistory, utc_iso
from session_store import ServerLogManager


def join(at, region="use1b", deployment="100", shard="020"):
    return f"<{utc_iso(at)}> [Notice] <Join PU> address[192.0.2.1] port[64000] shard[pub_{region}_{deployment}_{shard}]\n"


class TemporaryRecords(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.now = 10000.0
        self.clock = lambda: self.now

    def tearDown(self):
        self.directory.cleanup()

    def reader(self, text=""):
        path = self.root / "Game.log"
        path.write_text(text, encoding="utf-8")
        return IncrementalGameLog(path)


class LogTests(TemporaryRecords):
    def test_partial_join_line_and_utf8_are_preserved(self):
        reader = self.reader()
        message = join(self.now).encode()
        reader.feed(message[:85])
        self.assertFalse(reader.connected)
        reader.feed(message[85:])
        self.assertEqual(reader.full_shard_id, "pub_use1b_100_020")
        login = "User Login Success - Handle[Synthronaut]\n".encode()
        reader.feed(login)
        text = "Player[Synthronaut] requested inventory for Location[CaféStation]\n".encode()
        cut = text.index(bytes([0xC3])) + 1
        reader.feed(text[:cut]); reader.feed(text[cut:])
        self.assertEqual(reader.location_hint, "CAFÉSTATION")

    def test_loading_events_are_chronological(self):
        reader = self.reader(join(self.now))
        reader.feed(b"OpenLoadingScreen\nStopLoadingScreen Finished\nOpenLoadingScreen\n")
        self.assertTrue(reader.is_loading_screen)

    def test_disconnect_clears_all_session_fields(self):
        reader = self.reader(join(self.now))
        reader.feed(f"<{utc_iso(self.now)}> Server FPS 12.3\n".encode())
        self.assertTrue(reader.observations)
        reader.feed(b"Connection closed\n")
        self.assertFalse(reader.connected)
        self.assertIsNone(reader.session_token)
        self.assertEqual(reader.observations, {})
        self.assertEqual(reader.shard_id, "--")

    def test_same_shard_rejoin_has_distinct_token(self):
        reader = self.reader(join(self.now))
        first = reader.session_token
        reader.feed(join(self.now + 5).encode())
        self.assertNotEqual(reader.session_token, first)
        self.assertEqual([event["type"] for event in reader.events], ["joined", "left", "joined"])

    def test_frontend_disconnect_does_not_end_remote_session(self):
        reader = self.reader(join(self.now))
        reader.feed(b'<Channel Created> remoteAddr=192.0.2.1:64000 connection={3, 0}\n')
        reader.feed(b'<Channel Disconnected> remoteAddr=<local>:12300 connection={1, 0}\n')
        self.assertTrue(reader.connected)
        reader.feed(b'<Channel Disconnected> remoteAddr=192.0.2.1:64000 connection={3, 0}\n')
        self.assertFalse(reader.connected)

    def test_truncation_resets_and_reads_new_session(self):
        reader = self.reader(join(self.now) + "some extra content\n" * 200)
        Path(reader.log_path).write_text(join(self.now + 5, shard="021"), encoding="utf-8")
        reader.poll()
        self.assertEqual(reader.shard_id, "021")
        self.assertFalse(reader.observations)

    def test_numeric_inventory_id_does_not_override_location(self):
        reader = self.reader(join(self.now) + "User Login Success - Handle[Player]\n")
        reader.feed(b"Player[Player] requested inventory for Location[GrimHEX]\n")
        reader.feed(b"<Update Inventory Location> Player [Player] Landing [0] -> [3781743795]\n")
        self.assertEqual(reader.location_hint, "GRIMHEX")

    def test_no_local_player_identification_means_no_guessed_location(self):
        reader = self.reader(join(self.now))
        reader.feed(b"Player[SomeoneElse] requested inventory for Location[GrimHEX]\n")
        self.assertEqual(reader.location_hint, "")

    def test_metrics_require_measurement_lines(self):
        reader = self.reader(join(self.now))
        reader.feed(b"net_log_fps_interval = 1\nEnable logging server fps at intervals\n")
        self.assertFalse(reader.observations)
        reader.feed(f"<{utc_iso(self.now)}> Server FPS 0.0 [0.0..30.0]\n".encode())
        reader.feed(f"<{utc_iso(self.now)}> Net: ping 42.5ms, loss 2.0% BwIn 1.500Kbps, BwOut 0.2Kbps\n".encode())
        self.assertEqual(reader.observations["server_fps"].value, 0)
        self.assertEqual(reader.observations["ping_ms"].value, 42.5)
        self.assertEqual(reader.observations["loss_pct"].value, 2)


class MetricTests(unittest.TestCase):
    def test_expiration_preserves_source_but_hides_old_value(self):
        store = MetricStore(ttl=5)
        store.set_session("a")
        store.ingest({"ping_ms": 20}, "game_log", 100, "a")
        self.assertEqual(store.snapshot(104)[0]["ping_ms"], 20)
        values, meta = store.snapshot(106)
        self.assertIsNone(values["ping_ms"])
        self.assertEqual(meta["ping_ms"]["status"], "stale")
        self.assertEqual(meta["ping_ms"]["source"], "game_log")

    def test_late_sample_cannot_cross_session_boundary(self):
        store = MetricStore()
        store.set_session("a")
        store.ingest({"shard_pop": 610}, "capture", 100, "a")
        store.set_session("b")
        store.ingest({"shard_pop": 610}, "capture", 102, "a")
        self.assertIsNone(store.snapshot(102)[0]["shard_pop"])

    def test_old_log_value_cannot_replace_newer_capture(self):
        store = MetricStore(); store.set_session("a")
        store.ingest({"ping_ms": 20}, "capture", 102, "a")
        store.ingest({"ping_ms": 100}, "game_log", 100, "a")
        self.assertEqual(store.snapshot(103)[0]["ping_ms"], 20)

    def test_invalid_and_nonfinite_values_are_not_evidence(self):
        store = MetricStore(); store.set_session("a")
        store.ingest({"ping_ms": float("nan"), "server_fps": -1, "shard_pop": float("inf"), "loss_pct": 101}, "capture", 100, "a")
        self.assertTrue(all(value is None for value in store.snapshot(100)[0].values()))
        store.ingest({"shard_pop": 10.5}, "capture", 100, "a")
        self.assertIsNone(store.snapshot(100)[0]["shard_pop"])


class HistoryTests(TemporaryRecords):
    def history(self):
        return ShardHistory(self.root / "shard_history.json", self.clock)

    def observe(self, history, full="pub_use1b_100_020", token="first"):
        _, region, _, shard = full.split("_")
        return history.observe_shard(region, shard, full_shard_id=full, join_token=token)

    def test_region_and_deployment_are_part_of_identity(self):
        history = self.history()
        for full in ("pub_use1b_100_020", "pub_use2a_100_020", "pub_use1b_101_020"):
            self.assertEqual(self.observe(history, full, full)[0], "FIRST VISIT")
        self.assertEqual(len(history.shards), 3)

    def test_same_shard_reconnect_counts_and_restart_does_not(self):
        history = self.history(); self.observe(history)
        history.leave_current(); self.now += 300
        status, _ = self.observe(history, token="second")
        self.assertIn("RETURN #2", status)
        resumed = self.history()
        self.assertIn("RETURN #2", self.observe(resumed, token="second")[0])

    def test_legacy_short_ids_are_not_claimed_as_exact_matches(self):
        (self.root / "shard_history.json").write_text(json.dumps({"USE:020": {"visits": 10}}))
        history = self.history()
        self.assertEqual(self.observe(history)[0], "FIRST VISIT")
        self.assertIn("USE:020", json.loads(history.path.read_text())["legacy"])

    def test_precise_legacy_sessions_are_recovered_without_extra_visit(self):
        (self.root / "shard_history.json").write_text(json.dumps({"USE:020": {"visits": 10}}))
        full = "pub_use1b_100_020"
        (self.root / "server_log.json").write_text(json.dumps({"sessions": [
            {"full_shard_id": full, "joined_at": utc_iso(9000), "left_at": None, "server_name": "QUIET HARBOR"}]}))
        history = self.history()
        status, _ = self.observe(history, token=f"0:{full}:9000.000")
        self.assertEqual(status, "FIRST VISIT")
        self.assertEqual(history.get_known_name("use1b", "020", full), "QUIET HARBOR")

    def test_reminder_follows_full_identity_and_expires(self):
        history = self.history(); self.observe(history)
        history.mark_cooldown("Component room", 30)
        self.assertEqual(len(history.active_cooldowns()), 1)
        self.observe(history, "pub_use2a_100_020", "elsewhere")
        self.assertFalse(history.active_cooldowns())
        self.observe(history, token="return")
        self.assertEqual(history.active_cooldowns()[0]["label"], "Component room")
        self.now += 1801
        self.assertFalse(history.active_cooldowns())

    def test_invalid_storage_is_preserved(self):
        path = self.root / "shard_history.json"
        path.write_text("[]")
        with self.assertLogs("telemetry_core", level="ERROR"):
            history = self.history()
        self.assertTrue(history.read_only)
        self.observe(history)
        self.assertEqual(path.read_text(), "[]")


class HealthTests(TemporaryRecords):
    def test_missing_measurements_are_unknown(self):
        result = EvidenceHealth().evaluate()
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["score"])
        self.assertFalse(result["is_alert"])

    def test_zero_fps_is_stalled_and_time_advances_without_redraw(self):
        health = EvidenceHealth(self.clock)
        self.assertEqual(health.evaluate(0)["status"], "STALLED")
        self.now += 4
        self.assertTrue(health.evaluate(0)["should_voice"])
        self.assertFalse(health.evaluate(0)["should_voice"])

    def test_no_false_server_failure_from_latency_or_silence(self):
        result = EvidenceHealth().evaluate(ping_ms=350)
        self.assertEqual(result["status"], "LATENCY")
        self.assertFalse(result["is_alert"])

    def test_actual_remote_connection_loss_is_reported(self):
        result = EvidenceHealth().evaluate(is_in_server=False, connection_status="connection_lost")
        self.assertEqual(result["status"], "DISCONNECTED")
        self.assertTrue(result["is_alert"])


class SessionTests(TemporaryRecords):
    def store(self):
        return ServerLogManager(self.root / "server_log.json", clock=self.clock)

    def test_historical_session_is_not_assumed_live(self):
        (self.root / "server_log.json").write_text(json.dumps({"sessions": [{"id": "old", "active": True}]}))
        self.assertIsNone(self.store().get_active_session())

    def test_join_leave_and_rejoin_are_persisted(self):
        store = self.store()
        first = store.start_new_session("use1b", "100", "020", joined_at=self.now)
        self.now += 20; store.end_session()
        self.assertIsNone(store.get_active_session())
        self.assertEqual(first["duration_sec"], 20)
        store.start_new_session("use1b", "100", "020", joined_at=self.now)
        self.assertEqual(len(store.sessions), 2)
        self.assertEqual(len(json.loads(store.log_file.read_text())["sessions"]), 2)

    def test_measurements_are_counted_once_and_zero_is_valid(self):
        store = self.store(); session = store.start_new_session("use1b", "100", "020")
        metadata = {key: {"observed_at": 100} for key in ("server_fps", "ping_ms")}
        store.record_telemetry_sample(0, 0, 0, metadata)
        store.record_telemetry_sample(0, 0, 0, metadata)
        self.assertEqual(session["telemetry"]["sfps_samples"], 1)
        self.assertEqual(session["telemetry"]["avg_sfps"], 0)
        self.now += 20
        metadata["server_fps"]["observed_at"] = 101
        store.record_telemetry_sample(30, 0, 0, metadata)
        self.assertEqual(session["telemetry"]["avg_sfps"], 15)
        self.assertEqual(json.loads(store.log_file.read_text())["sessions"][0]["telemetry"]["avg_sfps"], 15)

    def test_legacy_receive_timestamp_is_aligned_without_duplicate_session(self):
        (self.root / "server_log.json").write_text(json.dumps({"sessions": [
            {"id": "old", "full_shard_id": "pub_use1b_100_020", "joined_at": utc_iso(self.now + .472), "active": True}]}))
        store = self.store()
        session = store.start_new_session("use1b", "100", "020", joined_at=self.now)
        self.assertEqual(len(store.sessions), 1)
        self.assertEqual(session["id"], "old")
        self.assertEqual(session["joined_at"], utc_iso(self.now))
        self.assertEqual(session["legacy_joined_at"], utc_iso(self.now + .472))


if __name__ == "__main__":
    unittest.main()
