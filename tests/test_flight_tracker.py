"""Tests for flight_tracker: sortie tracking, helm durations, fleet statistics, and incident handling."""

import json
from pathlib import Path
import tempfile
import time
import unittest

from flight_tracker import FlightTracker, resolve_ship_identity
from piracy_watch import PiracyReader


SAMPLE_LOG_CHUNKS = b"""<2026-11-11T00:37:37.472Z> [Notice] <SHUDEvent_OnNotification> Added notification "You have joined channel 'Corsair PYAM Exec : Synthronaut'." [Team_GameServices][Notification]
<2026-11-11T00:38:00.000Z> [Notice] <Vehicle Control Flow> [Vehicle::SeatControl] Requesting vehicle control token for 'DRAK_Corsair_Exec_StealthIndustrial_273189749172'
<2026-11-11T00:39:15.120Z> [Notice] <Calculate Route> Calculate Route to 'Grim HEX' | DRAK_Corsair_Exec_StealthIndustrial_273189749172[3129841]
<2026-11-11T00:41:20.500Z> [Notice] <Quantum Drive Arrived - Arrived at Final Destination> Quantum travel complete | DRAK_Corsair_Exec_StealthIndustrial_273189749172
<2026-11-11T00:42:00.000Z> [Notice] <SHUDEvent_OnNotification> Added notification "Contract Complete: Bounty Hunting" [Team_GameServices][Notification]
<2026-11-11T00:43:00.000Z> [Notice] <Vehicle Control Flow> CVehicleMovementBase::ClearDriver: Local client node 2 releasing control token for 'DRAK_Corsair_Exec_StealthIndustrial_273189749172'
<2026-11-11T00:44:00.000Z> [Notice] <Inventory> requested inventory for Location[station_grim_hex_hangar]
"""

SAMPLE_COLLISION_CHUNK = b"""<2026-11-11T01:00:00.000Z> [Notice] <SHUDEvent_OnNotification> Added notification "You have joined channel 'Gladius : Synthronaut'." [Team_GameServices][Notification]
<2026-11-11T01:01:00.000Z> [Notice] <Calculate Route> Calculate Route to 'Daymar' | AEGS_Gladius[999]
<2026-11-11T01:03:00.000Z> [Notice] <FatalCollision> Fatal Collision occured for vehicle AEGS_Gladius [Physics]
"""


class TestFlightTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        self.log_file = self.directory / "Game.log"
        self.log_file.write_bytes(SAMPLE_LOG_CHUNKS)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_ship_identity(self):
        name, mfg, col = resolve_ship_identity("DRAK_Corsair_Exec_StealthIndustrial_273189749172")
        self.assertIn("Drake", name)
        self.assertIn("Corsair", name)
        self.assertEqual(mfg, "Drake")
        self.assertEqual(col, "#c2a649")

        name2, mfg2, col2 = resolve_ship_identity("AEGS_Gladius_12345")
        self.assertIn("Aegis", name2)
        self.assertIn("Gladius", name2)
        self.assertEqual(mfg2, "Aegis")
        self.assertEqual(col2, "#3b82f6")

        name3, mfg3, col3 = resolve_ship_identity("Corsair PYAM Exec")
        self.assertIn("Drake Corsair", name3)

    def test_sortie_lifecycle_and_metrics(self):
        tracker = FlightTracker(self.directory, self.log_file)
        summary = tracker.summary()

        self.assertEqual(summary['state'], "ON_FOOT")
        self.assertEqual(summary['total_sorties'], 1)
        self.assertEqual(summary['total_jumps'], 1)
        self.assertEqual(summary['total_contracts'], 1)
        self.assertEqual(summary['total_losses'], 0)
        self.assertTrue(len(summary['fleet']) >= 1)
        self.assertIn("Corsair", summary['fleet'][0]['name'])
        self.assertGreater(summary['fleet'][0]['seconds'], 0)
        self.assertEqual(summary['fleet'][0]['pct'], 100)

        # Check recent sorties list
        self.assertEqual(len(summary['recent']), 1)
        self.assertIn("Corsair", summary['recent'][0]['ship'])
        self.assertEqual(summary['recent'][0]['jumps'], 1)
        self.assertEqual(summary['recent'][0]['contracts'], 1)
        self.assertEqual(summary['recent'][0]['reason'], "Landed & Disembarked")

    def test_collision_detection(self):
        collision_log = self.directory / "Collision.log"
        collision_log.write_bytes(SAMPLE_COLLISION_CHUNK)
        tracker = FlightTracker(self.directory, collision_log)
        summary = tracker.summary()

        self.assertEqual(summary['total_losses'], 1)
        self.assertEqual(len(summary['recent']), 1)
        self.assertEqual(summary['recent'][0]['incident'], "Fatal Collision")

    def test_history_persistence_and_reload(self):
        tracker1 = FlightTracker(self.directory, self.log_file)
        self.assertTrue((self.directory / "flight_history.json").exists())

        # Load fresh tracker from same directory
        tracker2 = FlightTracker(self.directory, self.directory / "empty.log")
        summary2 = tracker2.summary()
        self.assertEqual(summary2['total_sorties'], 1)
        self.assertIn("Corsair", summary2['fleet'][0]['name'])

    def test_piracy_reader_integration(self):
        reader = PiracyReader(self.directory, self.log_file)
        view = reader.tick(True, "shard-alpha-1")
        self.assertIn('flight', view)
        flight = view['flight']
        self.assertEqual(flight['total_sorties'], 1)
        self.assertEqual(flight['total_jumps'], 1)
        self.assertIn("Corsair", flight['fleet'][0]['name'])

    def test_jurisdiction_route_and_pull_ledger_persistence(self):
        extra_log = self.directory / "Juris.log"
        extra_log.write_bytes(
            b"""<2026-11-11T02:00:00.000Z> [Notice] <VehicleListQuery> Retrieved 14 entitlements [Team_GameServices]
<2026-11-11T02:01:00.000Z> [Notice] <SHUDEvent_OnNotification> Added notification "You have joined channel 'RSI Mantis : Synthronaut'." [Team_GameServices][Notification]
<2026-11-11T02:02:00.000Z> [Notice] <Calculate Route> Calculate Route to 'Checkmate Station' | RSI_Mantis[42]
<2026-11-11T02:03:00.000Z> [Notice] Entered Ungoverned Jurisdiction [Jurisdiction]
"""
        )
        reader = PiracyReader(self.directory, extra_log)
        view = reader.tick(True, "shard-pyro-2")
        flight = view['flight']
        self.assertEqual(flight['entitlements'], 14)
        self.assertEqual(flight['active_route'], "Checkmate Station")
        self.assertEqual(flight['jurisdiction'], "Ungoverned")
        self.assertIs(flight['monitored'], False)

        # Log and delete pulls
        reader.command("piracy_log_pull", {
            "target": "Crusader C2 Hercules",
            "lane": "Monox -> Checkmate",
            "outcome": "catch",
            "value_uec": 2400000,
            "notes": "Refined gold",
        })
        view2 = reader.tick(True, "shard-pyro-2")
        self.assertEqual(view2['pull_stats']['total'], 1)
        self.assertEqual(view2['pull_stats']['catches'], 1)
        self.assertEqual(view2['pull_stats']['total_loot_uec'], 2400000)

        # Reload reader and confirm persistence in piracy_log.json
        reader2 = PiracyReader(self.directory, extra_log)
        view3 = reader2.tick(True, "shard-pyro-2")
        self.assertEqual(len(view3['pulls']), 1)
        pull_id = view3['pulls'][0]['id']
        reader2.command("piracy_delete_pull", {"pull_id": pull_id})
        view4 = reader2.tick(True, "shard-pyro-2")
        self.assertEqual(len(view4['pulls']), 0)


if __name__ == '__main__':
    unittest.main()
