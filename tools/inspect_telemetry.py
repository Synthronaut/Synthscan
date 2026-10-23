"""Read available log telemetry without opening the app or changing any records."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from displayinfo_reader import translate_location
from telemetry_core import DEFAULT_GAME_LOG, IncrementalGameLog, MetricStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=DEFAULT_GAME_LOG, help="Game.log to inspect; never modified")
    options = parser.parse_args()
    reader = IncrementalGameLog(options.log, translate_location=translate_location)
    # Finish a finite snapshot, without following a continually growing log.
    length = Path(options.log).stat().st_size
    while reader.last_pos < length:
        previous = reader.last_pos
        reader.poll()
        if reader.last_pos == previous:
            break
    store = MetricStore()
    store.set_session(reader.session_token)
    for key, observation in reader.observations.items():
        store.ingest({key: observation.value}, observation.source, observation.observed_at, reader.session_token)
    values, metadata = store.snapshot(time.time())
    print(json.dumps({"log_indicates_session": reader.connected, "full_shard_id": reader.full_shard_id,
                      "region": reader.region_raw, "last_observed_location": reader.location_hint,
                      "location_observed_at": reader.location_observed_at,
                      "metrics": values, "metric_metadata": metadata,
                      "note": "A log snapshot does not establish that the game is currently running."}, indent=2))


if __name__ == "__main__":
    main()
