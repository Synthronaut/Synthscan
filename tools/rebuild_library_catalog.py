import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game_records import GameRecords
from tools.export_game_library import export as export_library
from reference_catalogs import catalogue_path, publish_catalogues

cache_root = Path(r"C:\Users\Dev\Documents\SynthScan\research\game_reference_cache\d6fec516-2d22-45eb-aeb2-29b9d769bd1d")
records_dir = cache_root / "records"
ini_path = next(cache_root.rglob("global.ini"))
artwork_dir = cache_root / "artwork"
vehicle_xml_dir = cache_root / "vehicle_xml"

manifest_path = ROOT / "release-validation/profile/reference/2cae0dfc-a941-4dcc-b82a-543b08b52d97/build_manifest.id"
if not manifest_path.exists():
    manifest_path = next(Path(r"C:\Users\Dev\Documents\SynthScan").rglob("build_manifest.id"))

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
print(f"Loading GameRecords from {records_dir} and {ini_path}...")
store = GameRecords(records_dir, ini_path)

print(f"Exporting game library using artwork at {artwork_dir}...")
destination = ROOT
library_data = export_library(store, artwork_dir, destination, manifest, vehicle_xml_dir)

print(f"Generated {len(library_data['entries'])} entries!")
verdicts = [e for e in library_data['entries'] if 'verdict' in e['name'].lower()]
print(f"Verdicts found in library: {[v['name'] for v in verdicts]}")
hellions = [e for e in library_data['entries'] if 'hellion' in e['name'].lower() or 'helion' in e['name'].lower()]
print(f"Hellions found in library: {[h['name'] for h in hellions]}")
kastak_weapons = [e for e in library_data['entries'] if 'kastak' in e.get('manufacturer', '').lower() and 'weapon' in e.get('category', '').lower()]
print(f"Kastak weapons found in library: {len(kastak_weapons)}")

# Write to data/local_game_library.json
target = ROOT / "data/local_game_library.json"
temp = target.with_suffix(".json.tmp")
temp.write_text(json.dumps(library_data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
os.replace(temp, target)
print(f"Updated {target}")

# Also update the active catalogue directory if present
curr_pointer = ROOT / "data/catalogue_current.json"
if curr_pointer.exists():
    info = json.loads(curr_pointer.read_text(encoding="utf-8"))
    gen_dir = ROOT / "data/catalogues" / info["generation"]
    if gen_dir.exists():
        gen_target = gen_dir / "local_game_library.json"
        gen_temp = gen_target.with_suffix(".json.tmp")
        gen_temp.write_text(json.dumps(library_data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        os.replace(gen_temp, gen_target)
        import hashlib
        info["hashes"]["local_game_library.json"] = hashlib.sha256(gen_target.read_bytes()).hexdigest()
        curr_pointer.write_text(json.dumps(info, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f"Updated active catalogue at {gen_target} and refreshed hash in {curr_pointer}")

# Export workspace_library.json
from item_directory import build_workspace
dist_lib = ROOT / "dist/native/workspace_library.json"
print(f"Rebuilding workspace_library.json at {dist_lib}...")
build_workspace(dist_lib)
print(f"Workspace library exported to {dist_lib}")

# Also copy to local profile workspace_library.json
from installation import PROFILE
local_lib = PROFILE / "workspace_library.json"
if local_lib.parent.exists():
    import shutil
    shutil.copy2(dist_lib, local_lib)
    print(f"Copied to local profile: {local_lib}")
