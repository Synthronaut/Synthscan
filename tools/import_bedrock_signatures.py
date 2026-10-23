"""Import reviewed signature facts from the local upstream checkout.

Never downloads or changes game/player data. Bedrock's NOTICE identifies these
tables as Star Citizen game data, separate from its GPL code.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "research/bedrock_upstream"


def main():
    path = UPSTREAM / "include/MiningData.h"
    source = path.read_text(encoding="utf-8")
    ship = source.split("MINERAL_SIGNATURES = {", 1)[1].split("};", 1)[0]
    special = source.split("SPECIAL_SIGNATURES = {", 1)[1].split("};", 1)[0]
    caps = {"Legendary": 2, "Epic": 3, "Rare": 4, "Uncommon": 5, "Common": 6}
    ores = []
    for name, base, rarity, systems in re.findall(r'\{"([^"]+)",\s*(\d+),\s*Rarity::(\w+),\s*([^}]+)\}', ship):
        tokens = [token.strip().removeprefix("SYS_") for token in systems.split("|")]
        if any(token not in {"ALL", "STANTON", "PYRO", "NYX"} for token in tokens):
            raise ValueError("Unknown system availability expression")
        ores.append({"name": name, "base_rs": int(base), "rarity": rarity,
                     "max_count": caps[rarity], "systems": ["STANTON", "PYRO", "NYX"] if tokens == ["ALL"] else tokens,
                     "category": "ship_mining"})
    families = []
    for name, category, base, maximum, typical in re.findall(
            r'\{"([^"]+)",\s*SignalCategory::(\w+),\s*(\d+),\s*(\d+),\s*(\d+)\}', special):
        families.append({"name": name, "category": {"ROCMining": "roc", "FPSMining": "hand", "Salvage": "salvage"}[category],
                         "base_rs": int(base), "max_count": int(maximum), "typical_min": int(typical)})
    if len(ores) != 26 or len(families) != 3:
        raise ValueError("Upstream table shape changed; review it before importing")
    revision = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    result = {"schema_version": 1, "game_version_family": "4.10", "upstream_commit": revision,
              "source_url": f"https://github.com/SC-Ravaxx/Bedrock/blob/{revision}/include/MiningData.h",
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "provenance": "Bedrock's reviewed tables; source attributes signature facts to SCMDB/Strata. Not independently extracted from this installed game build.",
              "scope": "Single mineral clusters and special families only. Mixed signatures are not inferred by this decoder.",
              "max_signature": 250000, "minerals": ores, "families": families}
    output = ROOT / "data/mining_signatures.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"minerals": len(ores), "families": len(families), "commit": revision, "output": str(output)}))


if __name__ == "__main__":
    main()
