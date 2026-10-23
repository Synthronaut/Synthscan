"""Exact single-cluster signature decoding using reviewed SC 4.10 tables.

Table provenance is in data/mining_signatures.json. A mathematical match does
not prove OCR accuracy or uniquely identify a contact. Preserve all candidates.
"""
import json
from pathlib import Path

TABLE = json.loads((Path(__file__).resolve().parent / "data/mining_signatures.json").read_text(encoding="utf-8"))
MINERAL_SIGNATURES = tuple(TABLE["minerals"])
SPECIAL_SIGNATURES = tuple(TABLE["families"])


def signature_candidates(value, *, system=None, environment=None):
    """All exact single-field explanations; empty means unresolved, not no rock."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1500 <= value <= TABLE["max_signature"]:
        return []
    system = system.upper() if system else None
    if system not in (None, "STANTON", "PYRO", "NYX"):
        raise ValueError("Unknown star system")
    if environment not in (None, "space", "surface"):
        raise ValueError("Environment must be space, surface, or unknown")
    candidates = []
    for row in (*MINERAL_SIGNATURES, *SPECIAL_SIGNATURES):
        count, remainder = divmod(value, row["base_rs"])
        if remainder or not 1 <= count <= row["max_count"]:
            continue
        if system and row.get("systems") and system not in row["systems"]:
            continue
        if environment == "space" and row["category"] in ("roc", "hand"):
            continue
        name = row["name"]
        if row["category"] == "salvage" and environment != "space":
            name = "Harvestable / salvage"
        candidates.append({"name": name, "category": row["category"], "count": count,
                           "base_rs": row["base_rs"], "rarity": row.get("rarity"),
                           "unusual_count": 1 < count < row.get("typical_min", 1),
                           "label": f"{count}x {name}"})
    return candidates


def parse_signature(sig_value, tolerance=0, *, system=None, environment=None):
    """Adapter for the detector, overlay and manual UI; never repairs digits.

Tolerance remains for old callers but has no effect. A fuzzy repair needs
independent picture evidence, which this decoder does not have.
"""
    matches = signature_candidates(sig_value, system=system, environment=environment)
    if not matches:
        return None
    ambiguous = len(matches) > 1
    first = matches[0]
    return {"title": f"{len(matches)} possible matches" if ambiguous else first["label"],
            "speech": f"Multiple possible matches for signature {sig_value}" if ambiguous else first["label"],
            "type": "ambiguous" if ambiguous else first["category"],
            "count": None if ambiguous else first["count"], "base_rs": None if ambiguous else first["base_rs"],
            "diff": 0, "match_kind": "exact_table", "ambiguous": ambiguous,
            "candidates": matches, "alternates": matches[1:], "details": " | ".join(row["label"] for row in matches),
            "source": TABLE["source_url"], "game_version_family": TABLE["game_version_family"]}


def match_summary(match):
    """Human-readable evidence, never a fabricated resource probability."""
    count = len(match["candidates"])
    label = f"{count} EXACT MATCHES" if count > 1 else "EXACT TABLE MATCH"
    if match.get("ocr_confidence") is not None:
        label += f" / OCR {match['ocr_confidence']:.0%}"
    return label


def reference_groups():
    groups = []
    for rarity in ("Legendary", "Epic", "Rare", "Uncommon", "Common"):
        rows = [(f"{row['name']} (1-{row['max_count']} rocks)", f"{row['base_rs']:,} RS", row["base_rs"])
                for row in MINERAL_SIGNATURES if row["rarity"] == rarity]
        groups.append((f"{rarity.upper()} // SC 4.10 MINERAL SIGNATURES", rows))
    groups.append(("GROUND FIELDS / SALVAGE // MINERAL NOT IDENTIFIED", [
        ("ROC field (ore unknown)", "4,000 RS", 4000),
        ("Hand-mining field (ore unknown)", "3,000 RS", 3000),
        ("Harvestable / salvage (context needed)", "2,000 RS", 2000),
        ("Ambiguous field example", "12,000 RS", 12000),
    ]))
    return groups
