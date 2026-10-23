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

def format_blueprint_pool(pool_text: str, owned_names: set):
    """
    Tags each blueprint item in the mission description:
    - [OWNED] Item Name (Type)
    - [  ] Item Name (Type)
    Returns: (new_pool_text, owned_count, total_count)
    """
    owned_count = 0
    total_count = 0

    def repl(m):
        nonlocal owned_count, total_count
        raw_name = m.group(1).strip()
        type_tag = m.group(2) or ""
        total_count += 1
        
        is_owned = any(o in raw_name.lower() or raw_name.lower() in o for o in owned_names)
        if is_owned:
            owned_count += 1
            tag = "[OWNED]"
        else:
            tag = "[  ]"
            
        return r"\n- " + tag + " " + raw_name + type_tag

    # Matches "- Item Name (Type)" or "- [OWNED] Item Name (Type)" or "- [  ] Item Name (Type)"
    pattern = re.compile(r'\\n\s*-\s*(?:\[(?:OWNED|X|\u2714)\]\s*|\[\s*\]\s*)?([^\(\n\r\\]+?)(\s*\([^\)\\\n\r]+\))?(?=\\n|$)')
    new_pool = pattern.sub(repl, pool_text)
    return new_pool, owned_count, total_count

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
        owned_names = set(k.lower() for k in bpm.blueprints.keys())
    else:
        owned_names = set(k.lower() for k in owned_blueprints)

    # 1. Create a safe backup before first or subsequent modifications
    backup_path = ini_path + ".synthscan_bak"
    if not os.path.exists(backup_path):
        try:
            shutil.copy2(ini_path, backup_path)
        except Exception as e:
            print("Backup creation warning:", e)

    # 2. Read existing global.ini
    try:
        with open(ini_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Failed to read {ini_path}: {e}", {}

    # 3. Process descriptions and map counts by key
    mission_counts = {} # base_key -> (owned_c, total_c)
    updated_lines = []
    desc_updates = 0
    title_updates = 0
    complete_count = 0
    partial_count = 0

    for line in lines:
        # Enforce compressed commodity and HUD scanning tags
        if line.startswith("items_commodities_amiantpod="):
            line = "items_commodities_amiantpod=Pod\n"
        elif line.startswith("items_commodities_flareweedstalk="):
            line = "items_commodities_flareweedstalk=Stock\n"
        elif line.startswith("hud_scanning_cat_harvestables="):
            line = "hud_scanning_cat_harvestables=Harv\n"

        if "Potential Harvestables:" in line:
            line = line.replace("Potential Harvestables:", "Potential Harv:")

        if "Potential Blueprints" in line:
            parts = line.split("Potential Blueprints", 1)
            prefix = parts[0] + "Potential Blueprints"
            pool = parts[1]
            new_pool, owned_c, total_c = format_blueprint_pool(pool, owned_names)
            
            # Extract key: e.g. Adagio_Desc_001
            key = line.split("=", 1)[0].split(",")[0].strip()
            # Canonical base key
            base_key = key.replace("_Desc", "_Title").replace("_desc", "_title")
            mission_counts[base_key] = (owned_c, total_c)
            
            if total_c > 0:
                if owned_c == total_c:
                    complete_count += 1
                elif owned_c > 0:
                    partial_count += 1

            new_line = prefix + new_pool
            if new_line != line:
                desc_updates += 1
            updated_lines.append(new_line)
        else:
            updated_lines.append(line)

    # 4. Process titles
    final_lines = []
    for line in updated_lines:
        line_key = line.split("=", 1)[0].split(",")[0].strip()
        if line_key in mission_counts:
            owned_c, total_c = mission_counts[line_key]
            new_title = update_title_tag(line, owned_c, total_c)
            if new_title != line:
                title_updates += 1
            final_lines.append(new_title)
        else:
            final_lines.append(line)

    # 5. Write back with UTF-8 BOM and LF line endings
    try:
        content = "".join(final_lines)
        # Ensure LF line endings
        content = content.replace("\r\n", "\n")
        with open(ini_path, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(content)
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
    backup_path = ini_path + ".synthscan_bak"
    if not os.path.exists(backup_path):
        return False, "No backup file found (.synthscan_bak)"
    try:
        shutil.copy2(backup_path, ini_path)
        return True, "Successfully restored original global.ini from backup!"
    except Exception as e:
        return False, f"Failed to restore: {e}"

# Backward compatibility alias
restore_starstrings_backup = restore_synthstrings_backup
