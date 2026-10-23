"""Prepare/install/remove the finite native DisplayInfo-binding experiment."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_displayinfo_bindings import build_profile, install_profile, remove_profile, sha256_file

GAME = Path(r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE")
OUT = ROOT / "research" / "native_displayinfo"


def game_is_running():
    # Query process names only; never obtain a VM handle or send game input.
    result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq StarCitizen.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, check=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return '"starcitizen.exe"' in result.stdout.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "install", "remove"), nargs="?", default="prepare")
    args = parser.parse_args()
    manifest = OUT / "manifest.json"
    candidate = OUT / "defaultProfile.xml"
    if args.operation == "prepare":
        source = ROOT / "research" / "console_free" / "Data__Libs__Config__defaultProfile.xml"
        # Only prepare against the executable whose assets were inspected.
        inventory = json.loads((source.parent / "executable_strings.json").read_text(encoding="utf-8"))
        actual = sha256_file(GAME / "Bin64" / "StarCitizen.exe")
        if actual != inventory["exe_sha256"]:
            raise RuntimeError("Executable changed since asset inspection")
        asset_inventory = json.loads((source.parent / "asset_inventory.json").read_text(encoding="utf-8"))
        asset = next(x for x in asset_inventory["extracted"] if x["name"] == "Data/Libs/Config/defaultProfile.xml")
        if sha256_file(source) != asset["sha256"]:
            raise RuntimeError("Extracted source changed since inspection")
        if (OUT / "installation.json").exists():
            raise RuntimeError("Remove the installed experiment before preparing another one")
        OUT.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(build_profile(source.read_bytes()))
        record = {"status": "prepared_not_installed_not_live_verified", "exe_sha256": actual,
                  "source_sha256": sha256_file(source), "candidate_sha256": sha256_file(candidate),
                  "on_key": "F14", "off_key": "F15", "original_actions": len(ET.fromstring(source.read_bytes()).findall('.//action')), "added_actions": 2,
                  "target": str(GAME / "USER/Client/0/Controls/defaultProfile.xml"),
                  "automatic_sampling": False, "requires_game_restart": True}
        manifest.write_text(json.dumps(record, indent=2), encoding="utf-8")
    elif args.operation == "install":
        record = install_profile(candidate, manifest, GAME, game_running=game_is_running())
    else:
        record = remove_profile(manifest, GAME, game_running=game_is_running())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Native DisplayInfo experiment: {exc}", file=sys.stderr)
        sys.exit(1)
