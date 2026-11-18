"""
SynthScan - SynthStrings Localization & Blueprint Syncer
Synchronizes unlocked blueprints from SynthScan with Star Citizen's local global.ini (SynthStrings).
Tags owned blueprints as [OWNED] and unowned as [  ] in mission descriptions, and updates contract
titles to [ALL BP OWNED] (skip) or [BP: X LEFT] so you instantly know which missions to run!
Maintains compressed commodity tags:
- Amiant Pod -> Pod
- Flareweed Stalk -> Stock
- Quasigrazer -> QzG
"""

import os
import re
import shutil
from datetime import datetime

DEFAULT_INI_PATH = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Data\Localization\english\global.ini"

_TITLE_LABEL_KEY_RE = re.compile(r"(?:title|_name(?:_|$)|_label(?:_|$))", re.I)
_BLUEPRINT_BLOCK_RE = re.compile(r"(?:\\n)*(<EM4>(?:Potential Blueprints|Multiple Blueprint Pools).*)$", re.I)


def is_title_or_label_key(k_low: str) -> bool:
    return "desc" not in k_low and bool(_TITLE_LABEL_KEY_RE.search(k_low))


def strip_blueprint_pool_from_title(line: str) -> tuple[str, str]:
    """Strip any misplaced blueprint pool block from title, name, or label keys."""
    if "=" not in line:
        return line, ""
    k_part, v_part = line.split("=", 1)
    k_low = k_part.split(",")[0].strip().casefold()
    if not is_title_or_label_key(k_low):
        return line, ""
    v_low = v_part.casefold()
    if "potential blueprints" not in v_low and "multiple blueprint pools" not in v_low:
        return line, ""
    ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = v_part[:-len(ending)] if ending else v_part
    m = _BLUEPRINT_BLOCK_RE.search(body)
    if not m:
        return line, ""
    cleaned = body[:m.start()].rstrip()
    return f"{k_part}={cleaned}{ending}", m.group(1).strip()


def format_blueprint_pool(pool_text: str, owned_names: set):
    """
    Tags each blueprint item in the mission description:
    - [OWNED] Item Name (Type)
    - [  ] Item Name (Type)
    Returns: (new_pool_text, owned_count, total_count)
    """
    from blueprint_strings import item_key
    owned = {item_key(n) for n in owned_names}
    seen = set()
    have = set()

    def repl(m):
        raw_name = m.group(1).strip()
        type_tag = m.group(2) or ""
        full_name = (raw_name + type_tag).strip()
        identity = item_key(full_name)
        seen.add(identity)
        if identity in owned:
            have.add(identity)
            tag = "[OWNED]"
        else:
            tag = "[  ]"
            
        return r"\n- " + tag + " " + raw_name + type_tag

    # Matches "- Item Name (Type)" or "- [OWNED] Item Name (Type)" or "- [  ] Item Name (Type)"
    pattern = re.compile(r'\\n\s*-\s*(?:\[(?:OWNED|X|\u2714)\]\s*|\[\s*\]\s*)?([^\n\r\\]+?)(\s*\([^\)\\\n\r]+\))?(?=\\n|$)')
    new_pool = pattern.sub(repl, pool_text)
    return new_pool, len(have), len(seen)

def update_title_tag(title_line: str, owned_count: int, total_count: int) -> str:
    """
    Updates the [BP] tag in a mission title line:
    - If all owned: [ALL BP OWNED]
    - If partial:   [BP: {rem} LEFT]
    - If none:      [BP]
    """
    if total_count <= 0:
        return title_line

    if owned_count == total_count:
        new_tag = "[ALL BP OWNED]"
    elif owned_count > 0:
        rem = total_count - owned_count
        new_tag = f"[BP: {rem} LEFT]"
    else:
        new_tag = "[BP]"

    # Replace any existing tag variation like [BP], [BP]*, [ALL BP OWNED], [BP: X LEFT]
    new_title = re.sub(r'\[(?:ALL BP OWNED|BP(?:: \d+ LEFT)?)\*?\]\*?', new_tag, title_line)
    return new_title

def sync_blueprints_to_global_ini(ini_path=DEFAULT_INI_PATH, owned_blueprints=None):
    """
    Scans global.ini and updates all mission blueprint pools and titles.
    Enforces compressed commodity tags (Pod, Stock, QzG).
    Preserves UTF-8 BOM and LF line endings.
    """
    if not os.path.exists(ini_path):
        return False, f"File not found: {ini_path}", {}

    if owned_blueprints is None:
        from blueprint_db import BlueprintManager
        bpm = BlueprintManager()
        owned_names = set(bp.get('name', k) for k, bp in bpm.blueprints.items() if isinstance(bp, dict))
        try:
            from installation import PROFILE
            from blueprint_strings import native_owned_names
            owned_txt = PROFILE / "owned_blueprints.txt"
            if owned_txt.exists():
                owned_names.update(native_owned_names(owned_txt))
        except Exception:
            pass
    else:
        owned_names = set(owned_blueprints)

    # 2. Read existing global.ini
    has_bom = False
    try:
        with open(ini_path, "rb") as bf:
            has_bom = bf.read(3) == b"\xef\xbb\xbf"
        with open(ini_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Failed to read {ini_path}: {e}", {}

    # 3. Process descriptions and map counts by key
    from blueprint_strings import resolve_title_key
    from mining_labels import compact_mining_labels
    custom_overrides = {}
    try:
        import json
        from pathlib import Path
        custom_path = Path(__file__).resolve().parent / "data" / "custom_synthstrings.json"
        if custom_path.exists():
            custom_overrides = json.loads(custom_path.read_text(encoding="utf-8"))
    except Exception:
        custom_overrides = {}

    all_keys = {l.split("=", 1)[0].split(",")[0].strip().casefold() for l in lines if "=" in l}
    moved_pools = {}
    cleaned_lines = []
    for line in lines:
        cleaned_line, moved_block = strip_blueprint_pool_from_title(line)
        if moved_block and "=" in cleaned_line:
            k_low = cleaned_line.split("=", 1)[0].split(",")[0].strip().casefold()
            desc_key = re.sub(r"(_name|_title)(?=_|$)", "_desc", k_low)
            if desc_key != k_low and desc_key in all_keys:
                moved_pools.setdefault(desc_key, moved_block)
        cleaned_lines.append(cleaned_line)
    lines = cleaned_lines

    mission_counts_sets = {}  # base_key -> (have_set, seen_set)
    updated_lines = []
    desc_updates = 0
    title_updates = 0
    seen_custom = set()

    for line in lines:
        if "=" in line:
            k_part, v_part = line.split("=", 1)
            k_clean = k_part.lstrip("\ufeff").strip()
            if k_clean in custom_overrides:
                seen_custom.add(k_clean)
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                bom = "\ufeff" if k_part.startswith("\ufeff") else ""
                line = f"{bom}{k_clean}={custom_overrides[k_clean]}{ending}"
        line, _ = compact_mining_labels(line)
        # Enforce compressed HUD scanning category tag
        if line.startswith("hud_scanning_cat_harvestables="):
            line = "hud_scanning_cat_harvestables=Harv\n"

        if "Potential Harvestables:" in line:
            line = line.replace("Potential Harvestables:", "Potential Harv:")
        if "Potential Harv:" in line:
            line = line.replace("Flareweed Stalk", "Stock").replace("Amiant Pod", "Pod")

        line, _ = strip_blueprint_pool_from_title(line)
        if "=" in line:
            k_part, v_part = line.split("=", 1)
            k_low = k_part.split(",")[0].strip().casefold()
            if k_low in moved_pools and "potential blueprints" not in v_part.casefold() and "multiple blueprint pools" not in v_part.casefold():
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                body = v_part[:-len(ending)] if ending else v_part
                line = f"{k_part}={body}\\n\\n{moved_pools[k_low]}{ending}"

        if "Potential Blueprints" in line:
            parts = line.split("Potential Blueprints", 1)
            prefix = parts[0] + "Potential Blueprints"
            pool = parts[1]
            new_pool, owned_c, total_c = format_blueprint_pool(pool, owned_names)
            
            # Extract key: e.g. Adagio_Desc_001
            key = line.split("=", 1)[0].split(",")[0].strip().casefold()
            base_key = resolve_title_key(key, all_keys)
            if base_key not in mission_counts_sets:
                mission_counts_sets[base_key] = [0, 0]
            mission_counts_sets[base_key][0] += owned_c
            mission_counts_sets[base_key][1] += total_c

            new_line = prefix + new_pool
            if new_line != line:
                desc_updates += 1
            updated_lines.append(new_line)
        else:
            updated_lines.append(line)

    mission_counts = {k: (c[0], c[1]) for k, c in mission_counts_sets.items()}
    complete_count = sum(c[0] == c[1] and c[1] > 0 for c in mission_counts.values())
    partial_count = sum(0 < c[0] < c[1] for c in mission_counts.values())

    # 4. Process titles
    final_lines = []
    for line in updated_lines:
        line_key = line.split("=", 1)[0].split(",")[0].strip().casefold()
        if line_key in mission_counts:
            owned_c, total_c = mission_counts[line_key]
            new_title = update_title_tag(line, owned_c, total_c)
            if new_title != line:
                title_updates += 1
            final_lines.append(new_title)
        else:
            final_lines.append(line)

    # Append any custom overrides not present in base global.ini (new items/unlocalized fixes)
    for k_custom, v_custom in custom_overrides.items():
        if k_custom not in seen_custom:
            final_lines.append(f"{k_custom}={v_custom}\n")

    # 5. Write back preserving original BOM presence and LF line endings
    try:
        content = "".join(final_lines)
        # Ensure LF line endings
        content = content.replace("\r\n", "\n")
        from game_text_lifecycle import write_localization
        write_localization(ini_path, content.encode("utf-8-sig" if has_bom else "utf-8"))
    except Exception as e:
        return False, f"Failed to write updated global.ini: {e}", {}

    stats = {
        "total_missions_with_bp": len(mission_counts),
        "complete_missions": complete_count,
        "partial_missions": partial_count,
        "desc_updates": desc_updates,
        "title_updates": title_updates,
        "owned_blueprints_checked": len(owned_names)
    }

    msg = (f"SynthStrings sync successful!\n"
           f"• {complete_count} Missions 100% COMPLETE marked [ALL BP OWNED]\n"
           f"• {partial_count} Partial Missions updated with remaining count\n"
           f"• {desc_updates} Mission descriptions tagged with [OWNED] / [  ]\n"
           f"• Harvestables compressed: 'Harvestable' -> 'Harv', Amiant Pod -> 'Pod', Flareweed Stalk -> 'Stock'")
    return True, msg, stats

def restore_synthstrings_backup(ini_path=DEFAULT_INI_PATH):
    try:
        from pathlib import Path
        from game_text_lifecycle import Manager
        result=Manager(Path(ini_path).resolve().parents[3]).restore()
        return not result['conflicts'], 'Managed recovery completed; older or externally edited files may need review in Setup.'
    except (OSError,ValueError) as error:
        return False, str(error)

# Backward compatibility alias
restore_starstrings_backup = restore_synthstrings_backup
