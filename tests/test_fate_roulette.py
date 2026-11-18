"""Tests for Fate Roulette wheel math, category toggles, and unowned blueprint rolling."""

from pathlib import Path
import json
import subprocess
import tempfile
import tkinter as tk
import unittest

from fate_roulette import CATEGORY_ORDER, FateRoulettePage


class _DummyBPManager:
    def __init__(self, rows):
        self._rows = list(rows)

    def get_blueprints(self, category=None, search=None, status_filter="ALL"):
        if status_filter == "MISSING":
            return [r for r in self._rows if not r.get("is_unlocked")]
        return list(self._rows)


class _DummyApp:
    def __init__(self, rows):
        self.bp_manager = _DummyBPManager(rows)


class FateRouletteTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.prefs_path = Path(self.tmp.name) / "roulette_categories.json"
        self.sample_bps = [
            {
                "id": "bp_1",
                "name": "Karna \"Fate\" Rifle",
                "type": "FPS Weapon",
                "size": None,
                "grade": "A",
                "sources": [0],
                "known_from_start": False,
                "is_favorite": True,
                "is_unlocked": False,
            },
            {
                "id": "bp_2",
                "name": "Suckerpunch-XL Cannon",
                "type": "Weapon Gun",
                "size": 3,
                "grade": "A",
                "sources": [0],
                "known_from_start": False,
                "is_favorite": False,
                "is_unlocked": False,
            },
            {
                "id": "bp_3",
                "name": "Unlocked Already Rifle",
                "type": "FPS Weapon",
                "size": None,
                "grade": "B",
                "sources": [0],
                "known_from_start": False,
                "is_favorite": False,
                "is_unlocked": True,
            },
            {
                "id": "bp_4",
                "name": "Unobtainable Cash Shop Variant",
                "type": "Torso (Armor)",
                "size": None,
                "grade": None,
                "sources": [],
                "known_from_start": False,
                "is_favorite": False,
                "is_unlocked": False,
            },
            {
                "id": "bp_5",
                "name": "Starter Known Suit",
                "type": "Undersuit (Armor)",
                "size": None,
                "grade": None,
                "sources": [0],
                "known_from_start": True,
                "is_favorite": False,
                "is_unlocked": False,
            },
        ]

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()

    def test_blueprint_category_filters_to_missing_obtainable_only(self):
        page = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        bp_names = {e.bp_name for e in page._sampled_bps}
        self.assertEqual(bp_names, {"Karna \"Fate\" Rifle", "Suckerpunch-XL Cannon"})
        self.assertEqual(page._missing_bp_count, 2)
        karna = next(e for e in page._sampled_bps if e.bp_name == "Karna \"Fate\" Rifle")
        self.assertTrue(karna.is_wanted)
        self.assertIn("Unlock via:", karna.description)

    def test_category_toggles_and_persistence(self):
        page = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        page._disable_all_cats()
        self.assertEqual(len(page._entries), 0)
        self.assertEqual(str(page._btn_spin.cget("state")), "disabled")

        page._toggle_category("Blueprint Unlock")
        self.assertEqual(len(page._entries), 2)
        self.assertEqual(str(page._btn_spin.cget("state")), "normal")
        self.assertTrue(all(e.category == "Blueprint Unlock" for e in page._entries))

        # Re-open from saved prefs
        page2 = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        self.assertTrue(page2._enabled_cats["Blueprint Unlock"])
        for cat_name, _ in CATEGORY_ORDER:
            if cat_name != "Blueprint Unlock":
                self.assertFalse(page2._enabled_cats[cat_name])
        self.assertEqual(len(page2._entries), 2)

    def test_pointer_math_matches_target_slice_across_sizes(self):
        page = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        for cat in ("Mining", "PvP", "Chaos"):
            page._disable_all_cats()
            page._toggle_category(cat)
            n = len(page._entries)
            sweep = 360.0 / n
            for target_idx in range(n):
                for jitter in (-0.38 * sweep, 0.0, 0.38 * sweep):
                    angle = -(target_idx + 0.5) * sweep + jitter
                    self.assertEqual(page._slice_at_pointer(angle), target_idx)

    def test_collection_category_includes_quality_and_rare_hunts(self):
        page = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        page._disable_all_cats()
        page._toggle_category("Collection")
        self.assertGreaterEqual(len(page._entries), 15)
        self.assertTrue(all(e.category == "Collection" for e in page._entries))
        quality_hunts = [e for e in page._entries if e.label.startswith("COLLECT: Q")]
        self.assertEqual(len(quality_hunts), 5)
        for q in quality_hunts:
            self.assertIn("Quality ", q.description)
        rare_labels = {e.label for e in page._entries}
        self.assertIn("VALAKKAR PEARL HUNT", rare_labels)
        self.assertIn("COMP-BOARD HEIST", rare_labels)

    def test_spin_completion_records_matching_history(self):
        page = FateRoulettePage(self.root, _DummyApp(self.sample_bps), prefs_path=self.prefs_path)
        page._disable_all_cats()
        page._toggle_category("Blueprint Unlock")
        page._start_spin()
        self.assertTrue(page._spin_active)
        # Fast-forward spin completion
        page._current_angle = page._final_angle % 360.0
        page._on_spin_complete()
        self.assertFalse(page._spin_active)
        self.assertEqual(len(page.history), 1)
        self.assertEqual(page.history[0].entry.label, page._entries[page._selected_idx].label)

    def test_native_roulette_selftest_and_render(self):
        exe = Path(__file__).resolve().parents[1] / "dist/native/SynthScan.exe"
        if not exe.exists():
            self.skipTest("Native binary not built")
        res = subprocess.run([str(exe), "--selftest"], capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)

        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d)
            (out_dir / "roulette_test_model.json").write_text("{}", encoding="utf-8")
            env = dict(**__import__("os").environ)
            env["SYNTHSCAN_DATA_DIR"] = str(out_dir)
            ui_res = subprocess.run(
                [str(exe), "--ui-test", str(out_dir)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(ui_res.returncode, 0, ui_res.stderr)
            report = json.loads((out_dir / "roulette_ui_test.json").read_text(encoding="utf-8"))
            self.assertTrue(report["mounted"])
            self.assertTrue(report["shot_large"])
            self.assertTrue(report["shot_small"])
            self.assertTrue((out_dir / "roulette_1360.png").exists())
            self.assertTrue((out_dir / "roulette_1152.png").exists())


if __name__ == "__main__":
    unittest.main()
