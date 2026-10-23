"""
SynthScan - Game Version Sentinel & Automated Adaptation Engine
Automatically detects when Star Citizen updates / patches, identifies newly added blueprints,
and automatically applies SynthStrings compression and synchronization rules.
"""

import os
import re
import json
import time
import shutil
import threading
from datetime import datetime

DEFAULT_SC_DIR = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE"
MANIFEST_FILE = os.path.join(DEFAULT_SC_DIR, "build_manifest.id")
DEFAULT_INI_PATH = os.path.join(DEFAULT_SC_DIR, "Data", "Localization", "english", "global.ini")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patch_state.json")

# Core Ruleset for Tag Compressions
ROCK_TAG_RULES = [
    (r'\(Shale\)', '(SHAL)'),
    (r'\(Granite\)', '(GRAN)'),
    (r'\(Obsidian\)', '(OBS)'),
    (r'\(Gneiss\)', '(GNEI)'),
    (r'\(Quartz\)', '(QRTZ)'),
    (r'\(Felsic\)', '(FELS)'),
    (r'\(Ataxite\)', '(ATAC)'),
    (r'\(Quantainium\)', '(QUAN)')
]

def get_current_game_version(sc_dir=DEFAULT_SC_DIR):
    """
    Reads build_manifest.id and global.ini state to get version info.
    """
    manifest_p = os.path.join(sc_dir, "build_manifest.id")
    ini_p = os.path.join(sc_dir, "Data", "Localization", "english", "global.ini")

    info = {
        "branch": "Unknown",
        "version": "Unknown",
        "build_num": "Unknown",
        "build_id": "Unknown",
        "build_date": "Unknown",
        "manifest_mtime": 0,
        "ini_mtime": 0,
        "ini_size": 0
    }

    if os.path.exists(manifest_p):
        try:
            with open(manifest_p, "r", encoding="utf-8") as f:
                data = json.load(f).get("Data", {})
                info["branch"] = data.get("Branch", "sc-alpha")
                info["version"] = data.get("Version", "")
                info["build_num"] = str(data.get("RequestedP4ChangeNum", ""))
                info["build_id"] = data.get("BuildId", "")
                info["build_date"] = data.get("BuildDateStamp", "")
            info["manifest_mtime"] = os.path.getmtime(manifest_p)
        except Exception:
            pass

    if os.path.exists(ini_p):
        try:
            info["ini_mtime"] = os.path.getmtime(ini_p)
            info["ini_size"] = os.path.getsize(ini_p)
        except Exception:
            pass

    return info

def load_patch_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_patch_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print("Failed to save patch state:", e)

def apply_all_rules_and_adapt(ini_path=DEFAULT_INI_PATH, sc_dir=DEFAULT_SC_DIR, force=False):
    """
    The Master Doctor:
    1. Compresses rock tags (SHAL, GRAN, etc.)
    2. Strips (raw) / (Raw)
    3. Normalizes Quasigrazer to QzG
    4. Compresses harvestables (Harv, Pod, Stock)
    5. Syncs owned blueprints against all mission pools
    6. Discovers new blueprints introduced in this patch
    Preserves UTF-8 BOM and LF line endings.
    """
    if not os.path.exists(ini_path):
        return False, f"File not found: {ini_path}", {}

    state = load_patch_state()
    current_ver = get_current_game_version(sc_dir)
    old_build = state.get("build_num", "None")
    new_build = current_ver.get("build_num", "Unknown")

    # Safe backup
    bak_path = ini_path + ".synthscan_bak"
    if not os.path.exists(bak_path):
        try:
            shutil.copy2(ini_path, bak_path)
        except Exception:
            pass

    try:
        with open(ini_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read {ini_path}: {e}", {}

    lines = content.splitlines(True)
    updated_lines = []

    # Counters
    raw_cleaned = 0
    rock_tags_cleaned = 0
    quazi_cleaned = 0
    harv_cleaned = 0

    # 1. Clean Line-by-Line Rules
    for line in lines:
        mod_line = line

        # A. Rock tags
        for pat, rep in ROCK_TAG_RULES:
            if re.search(pat, mod_line, re.IGNORECASE):
                mod_line, n = re.subn(pat, rep, mod_line, flags=re.IGNORECASE)
                rock_tags_cleaned += n

        # B. Raw removal across commodities
        if " (raw)" in mod_line.lower() or " (Raw)" in mod_line:
            mod_line, n = re.subn(r'\s*\([rR][aA][wW]\)', '', mod_line)
            raw_cleaned += n

        # C. Quasigrazers -> QzG
        if "quasigrazer" in mod_line.lower() or "quazigrazer" in mod_line.lower():
            if mod_line.startswith("items_commodities_quasigrazer=") or mod_line.startswith("actor_species_creature_quaziGrazer"):
                mod_line = re.sub(r'=.*', '=QzG\n', mod_line)
                quazi_cleaned += 1
            elif "Potential Creatures:" in mod_line:
                mod_line = re.sub(r'Quasigrazer|Quazigrazer', 'QzG', mod_line, flags=re.IGNORECASE)
                quazi_cleaned += 1

        # D. Harvestables compression
        if mod_line.startswith("items_commodities_amiantpod="):
            mod_line = "items_commodities_amiantpod=Pod\n"
            harv_cleaned += 1
        elif mod_line.startswith("items_commodities_flareweedstalk="):
            mod_line = "items_commodities_flareweedstalk=Stock\n"
            harv_cleaned += 1
        elif mod_line.startswith("hud_scanning_cat_harvestables="):
            mod_line = "hud_scanning_cat_harvestables=Harv\n"
            harv_cleaned += 1

        if "Potential Harvestables:" in mod_line:
            mod_line = mod_line.replace("Potential Harvestables:", "Potential Harv:")
            harv_cleaned += 1

        updated_lines.append(mod_line)

    # 2. Synchronize Blueprints
    from blueprint_db import BlueprintManager
    from synthstrings_sync import format_blueprint_pool, update_title_tag
    
    bpm = BlueprintManager()
    owned_names = set(k.lower() for k in bpm.blueprints.keys())

    # Catalog all blueprints visible in the file to detect newly introduced blueprints
    known_game_bps = set(state.get("known_game_blueprints", []))
    current_game_bps = set()

    mission_counts = {}
    desc_updates = 0
    title_updates = 0
    complete_count = 0
    partial_count = 0
    post_desc_lines = []

    for line in updated_lines:
        if "Potential Blueprints" in line:
            parts = line.split("Potential Blueprints", 1)
            prefix = parts[0] + "Potential Blueprints"
            pool = parts[1]
            
            # Extract names for discovery
            pool_items = re.findall(r'\\n\s*-\s*(?:\[(?:OWNED|X|\u2714)\]\s*|\[\s*\]\s*)?([^\(\n\r\\]+?)(\s*\([^\)\\\n\r]+\))?(?=\\n|$)', pool)
            for item_name, _ in pool_items:
                c_name = item_name.strip()
                if c_name:
                    current_game_bps.add(c_name)

            new_pool, owned_c, total_c = format_blueprint_pool(pool, owned_names)
            key = line.split("=", 1)[0].split(",")[0].strip()
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
            post_desc_lines.append(new_line)
        else:
            post_desc_lines.append(line)

    # Process title tags
    final_lines = []
    for line in post_desc_lines:
        line_key = line.split("=", 1)[0].split(",")[0].strip()
        if line_key in mission_counts:
            owned_c, total_c = mission_counts[line_key]
            new_title = update_title_tag(line, owned_c, total_c)
            if new_title != line:
                title_updates += 1
            final_lines.append(new_title)
        else:
            final_lines.append(line)

    # 3. Write back safely with UTF-8 BOM and LF endings
    try:
        final_text = "".join(final_lines).replace("\r\n", "\n")
        with open(ini_path, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(final_text)
    except Exception as e:
        return False, f"Failed to write adapted global.ini: {e}", {}

    # 4. Check for New Blueprints introduced in this patch
    newly_discovered_bps = sorted(list(current_game_bps - known_game_bps)) if known_game_bps else []

    # 5. Update State
    state.update({
        "last_adapted_at": datetime.now().isoformat(),
        "build_num": new_build,
        "branch": current_ver.get("branch", ""),
        "version": current_ver.get("version", ""),
        "manifest_mtime": current_ver.get("manifest_mtime", 0),
        "ini_mtime": os.path.getmtime(ini_path),
        "known_game_blueprints": sorted(list(current_game_bps)),
        "total_game_blueprints": len(current_game_bps),
        "total_missions_with_bp": len(mission_counts),
        "complete_missions": complete_count,
        "partial_missions": partial_count
    })
    save_patch_state(state)

    report = {
        "old_build": old_build,
        "new_build": new_build,
        "version": current_ver.get("version", ""),
        "new_blueprints": newly_discovered_bps,
        "total_game_blueprints": len(current_game_bps),
        "raw_cleaned": raw_cleaned,
        "rock_tags_cleaned": rock_tags_cleaned,
        "harv_cleaned": harv_cleaned,
        "complete_missions": complete_count,
        "partial_missions": partial_count,
        "desc_updates": desc_updates,
        "title_updates": title_updates
    }

    msg = (f"Auto-Adaptation Complete (Build {new_build})!\n"
           f"• {complete_count} Missions 100% COMPLETE marked [ALL BP OWNED]\n"
           f"• {partial_count} Partial Missions updated with remaining count\n"
           f"• {raw_cleaned} (raw) strings stripped | {rock_tags_cleaned} rock tags compressed\n"
           f"• Harvestables compressed to 'Harv', 'Pod', 'Stock'\n"
           f"• {len(current_game_bps)} Total Blueprints in game catalog")
    if newly_discovered_bps:
        msg += f"\n⭐ {len(newly_discovered_bps)} NEW Blueprints detected in this patch!"

    return True, msg, report

class PatchWatcher:
    """
    Background sentinel that monitors Star Citizen build_manifest.id and global.ini.
    Whenever the game is patched or updated, automatically triggers apply_all_rules_and_adapt.
    """
    def __init__(self, sc_dir=DEFAULT_SC_DIR, ini_path=DEFAULT_INI_PATH):
        self.sc_dir = sc_dir
        self.ini_path = ini_path
        self.running = False
        self.thread = None

    def start(self, on_patch_detected_cb=None, interval_sec=3600):
        if self.running:
            return
        self.running = True

        def watcher_loop():
            while self.running:
                time.sleep(interval_sec)
                try:
                    state = load_patch_state()
                    current = get_current_game_version(self.sc_dir)
                    
                    last_build = state.get("build_num")
                    current_build = current.get("build_num")
                    last_ini_mtime = state.get("ini_mtime", 0)
                    curr_ini_mtime = current.get("ini_mtime", 0)

                    # Trigger if build number changed or fresh global.ini dropped
                    build_changed = current_build and last_build and (current_build != last_build)
                    ini_changed = curr_ini_mtime and (curr_ini_mtime > last_ini_mtime + 5.0)

                    if build_changed or ini_changed:
                        ok, msg, report = apply_all_rules_and_adapt(self.ini_path, self.sc_dir)
                        if ok and on_patch_detected_cb:
                            on_patch_detected_cb(report)
                except Exception:
                    pass

        self.thread = threading.Thread(target=watcher_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
