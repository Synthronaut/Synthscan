import unittest
from types import SimpleNamespace

from main import SynthScanApp
from overlay import HUDOverlay


class Label:
    def __init__(self):
        self.options = {}
    def configure(self, **options):
        self.options.update(options)


class MiningUIIntegrationTests(unittest.TestCase):
    def test_manual_decoder_flows_to_existing_overlay_with_ambiguous_result(self):
        app = SynthScanApp.__new__(SynthScanApp)
        for name in ("lbl_live_title", "lbl_live_sub", "lbl_rail_sig", "lbl_rail_sub"):
            setattr(app, name, Label())
        overlay = HUDOverlay.__new__(HUDOverlay)
        overlay.is_visible = True
        overlay.win = SimpleNamespace(deiconify=lambda: None)
        drawn = []
        overlay._draw_hud = lambda **kwargs: drawn.append(kwargs)
        app.overlay = overlay
        app.voice = SimpleNamespace(speak=lambda *args, **kwargs: None)
        app.log_comms = lambda *args, **kwargs: None
        app._draw_large_reticle = lambda *args: None
        app.entry_test_sig = SimpleNamespace(get=lambda: "12,000")
        app.on_manual_test()
        self.assertEqual(app.last_detected_sig, 12000)
        self.assertIn("3 POSSIBLE", app.lbl_live_title.options["text"])
        self.assertIn("ROC", app.lbl_live_sub.options["text"])
        self.assertIn("AMBIGUOUS", drawn[-1]["badge"])
        self.assertNotIn("100%", drawn[-1]["details"])
        app.entry_test_sig = SimpleNamespace(get=lambda: "6370")
        app.on_manual_test()
        self.assertIn("STILERON", app.lbl_live_title.options["text"])
        self.assertEqual(drawn[-1]["title"], "2x Stileron")


if __name__ == "__main__":
    unittest.main()
