"""Save graphics inventories, register measured runs, and compare one setting.

All commands are read-only with respect to game/system settings. Outputs are
local research records; no data is uploaded. Numeric menu enums stay raw.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from performance_lab import (GAME, CATALOG, snapshot, setting_inventory, summarize_frame_csv,
                             compare_runs, write_json, read_json, utc_now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inventory = commands.add_parser('inventory')
    inventory.add_argument('--game', type=Path, default=GAME)
    inventory.add_argument('--output', type=Path, required=True)
    register = commands.add_parser('register')
    register.add_argument('--game', type=Path, default=GAME)
    register.add_argument('--frames', type=Path)
    register.add_argument('--pid', type=int)
    register.add_argument('--resources', type=Path)
    register.add_argument('--scene', required=True)
    register.add_argument('--route', required=True)
    register.add_argument('--workload', required=True, help='Background workload, including Discord watching/sharing state')
    register.add_argument('--driver', required=True)
    register.add_argument('--runtime-verified', action='store_true')
    register.add_argument('--overrides-verified', action='store_true')
    register.add_argument('--frame-generation-off', action='store_true')
    register.add_argument('--visual-notes', default='Not yet assessed')
    register.add_argument('--visibility-notes', default='Not yet assessed')
    register.add_argument('--output', type=Path, required=True)
    compare = commands.add_parser('compare')
    compare.add_argument('before', type=Path)
    compare.add_argument('after', type=Path)
    compare.add_argument('--setting', required=True, choices=[row[0] for row in CATALOG])
    compare.add_argument('--baseline-repeat', type=Path)
    compare.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'inventory':
        saved = snapshot(args.game)
        result = {'snapshot': saved, 'inventory': setting_inventory(saved)}
        write_json(args.output, result)
        csv_path = args.output.with_suffix('.csv')
        with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result['inventory'][0]))
            writer.writeheader()
            writer.writerows(result['inventory'])
        print(json.dumps({'output': str(args.output), 'worksheet': str(csv_path),
                          'settings': len(result['inventory']), 'potential_overrides': saved['potential_overrides'],
                          'errors': saved['errors']}, indent=2))
        return
    if args.command == 'register':
        saved = snapshot(args.game)
        result = {'schema': 1, 'captured_at': utc_now(), 'scene': args.scene, 'route': args.route,
                  'background_workload': args.workload, 'driver_version': args.driver,
                  'game_build': saved['build'].get('RequestedP4ChangeNum'),
                  'snapshot': saved, 'frames': summarize_frame_csv(args.frames, args.pid) if args.frames else None,
                  'frame_csv': str(args.frames.resolve()) if args.frames else None,
                  'resources': read_json(args.resources) if args.resources else None,
                  'runtime_verified': args.runtime_verified, 'overrides_verified': args.overrides_verified,
                  'frame_generation': False if args.frame_generation_off else None,
                  'visual_notes': args.visual_notes, 'visibility_notes': args.visibility_notes,
                  'settings_timestamp_note': 'Snapshot taken at registration; verify it matches the captured run. Register before changing another setting.'}
        if not args.frames:
            result['measurement_warning'] = 'No per-frame CSV. No FPS or 1% low result is calculated.'
    else:
        result = compare_runs(read_json(args.before), read_json(args.after), args.setting,
                              read_json(args.baseline_repeat) if args.baseline_repeat else None)
    write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
