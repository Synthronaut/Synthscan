"""Public HUD entry point; acquisition and state are implemented separately."""
from hud_controller import TopTelemetryHUD
from displayinfo_reader import FastDisplayInfoBitmapReader, translate_location, translate_region
from telemetry_core import EvidenceHealth as ServerHealthEvaluator, IncrementalGameLog as GameLogTelemetryReader
from telemetry_core import ShardHistory
from pathlib import Path

class ShardTracker(ShardHistory):
    def __init__(self, path=None):
        super().__init__(path or Path(__file__).resolve().parent / "shard_history.json")
