"""
SynthScan - Refinery Database & OCR Receipt Parser
Extracts refined ore amounts from Star Citizen refinery terminal screenshots.
Tracks total collected ore inventory and computes market values.
"""

import os
import json
import re
import datetime
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "inventory.json")

ORE_CATALOG = {
    "Quantainium": {"tags": ["quantainium", "qz", "quan"], "price": 24000, "color": "#00e5ff", "tier": "Legendary"},
    "Bexalite":    {"tags": ["bexalite", "bex"],          "price": 8800,  "color": "#ffb300", "tier": "Rare"},
    "Taranite":    {"tags": ["taranite", "tar"],          "price": 7800,  "color": "#00e676", "tier": "Rare"},
    "Gold":        {"tags": ["gold", "gld"],              "price": 7200,  "color": "#ffd700", "tier": "Rare"},
    "Borase":      {"tags": ["borase", "bor"],            "price": 4200,  "color": "#26a69a", "tier": "Rare"},
    "Laranite":    {"tags": ["laranite", "lar"],          "price": 3200,  "color": "#29b6f6", "tier": "Uncommon"},
    "Agricium":    {"tags": ["agricium", "agr"],          "price": 2800,  "color": "#ab47bc", "tier": "Uncommon"},
    "Beryl":       {"tags": ["beryl", "ber"],              "price": 2600,  "color": "#81c784", "tier": "Uncommon"},
    "Hephaestanite":{"tags": ["hephaestanite", "heph"],   "price": 1600,  "color": "#ff7043", "tier": "Common"},
    "Titanium":    {"tags": ["titanium", "titn"],         "price": 1050,  "color": "#90a4ae", "tier": "Common"},
    "Tungsten":    {"tags": ["tungsten", "tung"],         "price": 950,   "color": "#b0bec5", "tier": "Common"},
    "Copper":      {"tags": ["copper", "cop"],            "price": 750,   "color": "#d84315", "tier": "Common"},
    "Corundum":    {"tags": ["corundum", "cor"],          "price": 450,   "color": "#78909c", "tier": "Common"},
    "Quartz":      {"tags": ["quartz", "qrtz"],           "price": 350,   "color": "#eceff1", "tier": "Common"},
    "Silicon":     {"tags": ["silicon", "sil"],           "price": 280,   "color": "#cfd8dc", "tier": "Common"},
    "Iron":        {"tags": ["iron"],                     "price": 250,   "color": "#b0bec5", "tier": "Common"},
    "Aluminum":    {"tags": ["aluminum", "aluminium", "alum"], "price": 220, "color": "#cfd8dc", "tier": "Common"},
    "Tin":         {"tags": ["tin"],                      "price": 210,   "color": "#cfd8dc", "tier": "Common"},
    # Gemstones
    "Janalite":    {"tags": ["janalite", "jan"],          "price": 120000,"color": "#ea80fc", "tier": "Gem"},
    "Hadanite":    {"tags": ["hadanite", "had"],          "price": 27500, "color": "#ff1744", "tier": "Gem"},
    "Aphorite":    {"tags": ["aphorite", "aph"],          "price": 15200, "color": "#ba68c8", "tier": "Gem"},
    "Dolivine":    {"tags": ["dolivine", "dol"],          "price": 13000, "color": "#00e676", "tier": "Gem"}
}

class RefineryParseResult(dict):
    """
    Subclasses dict so {ore: scu} iteration works seamlessly with legacy code,
    while carrying per-ore Quality ratings and raw haul details.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.qualities = {}
        self.details = []

def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return {"totals": {}, "batches": {}, "history": []}
    try:
        with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"totals": {}, "batches": {}, "history": []}

    if "totals" not in data or not isinstance(data["totals"], dict):
        data["totals"] = {}
    if "batches" not in data or not isinstance(data["batches"], dict):
        data["batches"] = {}
    if "history" not in data or not isinstance(data["history"], list):
        data["history"] = []

    # Ensure all ores in totals have at least one batch in batches
    for ore, scu in list(data["totals"].items()):
        if scu <= 0:
            continue
        if ore not in data["batches"] or not data["batches"][ore]:
            data["batches"][ore] = [{
                "id": f"{ore.lower()}_def",
                "scu": round(float(scu), 2),
                "quality": 850,
                "added_at": "Default Batch"
            }]
        else:
            # Recompute total from batches to keep in sync
            batch_tot = round(sum(b.get("scu", 0.0) for b in data["batches"][ore]), 2)
            if abs(batch_tot - scu) > 0.01:
                data["totals"][ore] = batch_tot

    return data

def save_inventory(inv):
    try:
        with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=4)
    except Exception as e:
        print("Failed to save inventory:", e)

def get_ore_batches(ore: str) -> list:
    """
    Returns all batches for a specific ore, sorted by quality descending.
    """
    inv = load_inventory()
    batches = inv.get("batches", {}).get(ore, [])
    return sorted(batches, key=lambda b: b.get("quality", 850), reverse=True)

def get_ore_quality_summary(ore: str) -> str:
    """
    Returns a human-readable quality summary string for this ore.
    e.g. '12.5 SCU @ 910 Q | 8.0 SCU @ 800 Q'
    """
    batches = get_ore_batches(ore)
    if not batches:
        return ""
    if len(batches) == 1:
        return f"{batches[0].get('scu', 0.0):.2f} SCU [{batches[0].get('quality', 850)} Q]"
    parts = [f"{b.get('scu', 0.0):.1f} [{b.get('quality', 850)} Q]" for b in batches if b.get('scu', 0.0) > 0]
    return " | ".join(parts)

def add_haul_record(ore_amounts, source="screenshot", quality_map=None):
    """
    Adds newly parsed/entered ores to inventory, tracks quality batches, and appends a persistent history log.
    ore_amounts: dict { "Tungsten": 12.5, ... } or RefineryParseResult
    quality_map: optional dict { "Tungsten": 910 }
    """
    if not ore_amounts:
        return load_inventory()

    inv = load_inventory()
    totals = inv.setdefault("totals", {})
    batches = inv.setdefault("batches", {})
    history = inv.setdefault("history", [])

    if quality_map is None and hasattr(ore_amounts, "qualities"):
        quality_map = ore_amounts.qualities

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": now_str,
        "source": source,
        "items": {},
        "details": [],
        "total_scu": 0.0,
        "total_value": 0
    }

    import time
    ts_seed = int(time.time() * 1000)

    for ore, scu in ore_amounts.items():
        if str(ore).startswith("_"):
            continue
        try:
            scu_val = round(float(scu), 2)
        except (ValueError, TypeError):
            continue
        if scu_val <= 0:
            continue

        q = 850
        if quality_map and ore in quality_map:
            try:
                q = int(quality_map[ore])
            except (ValueError, TypeError):
                q = 850

        # Find or create batch with this exact quality
        b_list = batches.setdefault(ore, [])
        found_batch = False
        for b in b_list:
            if b.get("quality", 850) == q:
                b["scu"] = round(b.get("scu", 0.0) + scu_val, 2)
                found_batch = True
                break
        if not found_batch:
            ts_seed += 1
            b_list.append({
                "id": f"{ore.lower()}_{q}_{ts_seed}",
                "scu": scu_val,
                "quality": q,
                "added_at": now_str
            })

        totals[ore] = round(sum(b.get("scu", 0.0) for b in b_list), 2)
        entry["items"][ore] = scu_val
        price = ORE_CATALOG.get(ore, {}).get("price", 500)
        item_val = int(scu_val * price)
        entry["details"].append({
            "ore": ore,
            "scu": scu_val,
            "quality": q,
            "est_value": item_val
        })
        entry["total_scu"] = round(entry["total_scu"] + scu_val, 2)
        entry["total_value"] += item_val

    if entry["items"]:
        history.insert(0, entry)

    save_inventory(inv)
    return inv

def delete_single_ore(ore: str):
    inv = load_inventory()
    if ore in inv.get("totals", {}):
        del inv["totals"][ore]
    if ore in inv.get("batches", {}):
        del inv["batches"][ore]
    save_inventory(inv)
    return inv

def delete_ore_batch(ore: str, batch_id: str):
    inv = load_inventory()
    b_list = inv.get("batches", {}).get(ore, [])
    inv["batches"][ore] = [b for b in b_list if b.get("id") != batch_id]
    if not inv["batches"][ore]:
        if ore in inv.get("totals", {}):
            del inv["totals"][ore]
    else:
        inv["totals"][ore] = round(sum(b.get("scu", 0.0) for b in inv["batches"][ore]), 2)
    save_inventory(inv)
    return inv

def clear_inventory():
    empty = {"totals": {}, "batches": {}, "history": []}
    save_inventory(empty)
    return empty

def compute_total_value(totals):
    total_val = 0
    total_scu = 0.0
    for ore, scu in totals.items():
        info = ORE_CATALOG.get(ore, {"price": 500})
        total_val += int(scu * info["price"])
        total_scu += scu
    return round(total_scu, 2), total_val

# --- OCR Parser for Refinery Terminal ---
_ocr_engine = None

def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine

def parse_refinery_image(img_input):
    """
    Parses a Star Citizen refinery terminal confirmation screenshot.
    Focuses on the terminal confirmation window in the center of the display,
    identifying individual materials, refined yield (SCU/cSCU), and material quality ratings.
    Returns RefineryParseResult({ "Tungsten": 12.5, ... }) with .qualities and .details.
    """
    if isinstance(img_input, str):
        if not os.path.exists(img_input):
            return RefineryParseResult()
        frame = cv2.imread(img_input)
    elif hasattr(img_input, "convert"): # PIL Image
        frame = cv2.cvtColor(np.array(img_input), cv2.COLOR_RGB2BGR)
    else:
        frame = img_input

    if frame is None or frame.size == 0:
        return RefineryParseResult()

    engine = get_ocr()

    # If full screen resolution, try focusing on the central terminal dialog first
    h, w = frame.shape[:2]
    frames_to_try = []
    if w >= 1200 and h >= 700:
        # Central 75% width, 80% height where SC displays refinery work order modals
        c_x1 = int(w * 0.12)
        c_x2 = int(w * 0.88)
        c_y1 = int(h * 0.10)
        c_y2 = int(h * 0.90)
        crop = frame[c_y1:c_y2, c_x1:c_x2]
        frames_to_try.append((crop, c_x1, c_y1))
    frames_to_try.append((frame, 0, 0))

    paired_haul = RefineryParseResult()

    for cur_frame, offset_x, offset_y in frames_to_try:
        try:
            results, _ = engine(cur_frame)
        except Exception:
            results = None

        if not results:
            continue

        detected_items = []
        for r in results:
            box, text, conf = r
            clean_text = text.strip()
            xs = [pt[0] + offset_x for pt in box]
            ys = [pt[1] + offset_y for pt in box]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            detected_items.append({
                "text": clean_text,
                "cx": cx,
                "cy": cy,
                "min_x": min(xs),
                "max_x": max(xs),
                "min_y": min(ys),
                "max_y": max(ys),
                "conf": float(conf)
            })

        # Step 1: Find all detected ore label occurrences
        found_ores = []
        for item in detected_items:
            txt = item["text"].lower()
            for canonical, info in ORE_CATALOG.items():
                for tag in info["tags"]:
                    pattern = r'\b' + re.escape(tag) + r'\b'
                    if re.search(pattern, txt, re.IGNORECASE):
                        found_ores.append({
                            "ore": canonical,
                            "cy": item["cy"],
                            "cx": item["cx"],
                            "box": item
                        })
                        break

        if not found_ores:
            continue

        # Step 2: Find all numbers (SCU quantities or raw values) & Quality ratings
        num_candidates = []
        quality_candidates = []

        for item in detected_items:
            raw_t = item["text"]
            txt_clean = raw_t.replace(",", "").strip()

            # Quality candidates: e.g. "Quality: 910", "910 Q", "910", "Purity: 850"
            q_matches = re.findall(r'(?:quality|qual|purity|q)[:\s]*([0-9]{2,4})', txt_clean, re.IGNORECASE)
            for qm in q_matches:
                try:
                    qv = int(qm)
                    if 100 <= qv <= 1000:
                        quality_candidates.append({"quality": qv, "cx": item["cx"], "cy": item["cy"]})
                except ValueError:
                    pass

            # Also check if standalone integer between 400 and 1000 without "scu" is a quality rating
            if not q_matches and not re.search(r'\b(?:c?scu|units)\b|%', txt_clean, re.IGNORECASE):
                int_matches = re.findall(r'\b([4-9]\d{2}|1000)\b', txt_clean)
                for im in int_matches:
                    try:
                        iv = int(im)
                        quality_candidates.append({"quality": iv, "cx": item["cx"], "cy": item["cy"]})
                    except ValueError:
                        pass

            # SCU / Amount candidates: e.g. "32.00 SCU", "850 cSCU", "14.5"
            matches = re.findall(r'(\d+(?:\.\d+)?)\s*(cscu|scu|units|%)?', txt_clean, re.IGNORECASE)
            for m, unit in matches:
                try:
                    if unit == '%':
                        continue
                    val = float(m)
                    # Exclude standalone quality integers from being treated as SCU
                    if val in [q["quality"] for q in quality_candidates] and "scu" not in raw_t.lower():
                        continue
                    is_cscu = unit.lower() == 'cscu' or (not unit and val > 500)
                    scu = val / 100.0 if is_cscu else val
                    if 0.05 <= scu <= 5000:
                        num_candidates.append({
                            "scu": scu,
                            "cx": item["cx"],
                            "cy": item["cy"],
                            "raw_text": raw_t
                        })
                except ValueError:
                    pass

        # Step 3: Pair each ore with the closest quantity and quality rating on the same horizontal row
        for ore_entry in found_ores:
            ore_name = ore_entry["ore"]
            ore_y = ore_entry["cy"]
            ore_x = ore_entry["cx"]

            # Filter numbers aligned horizontally (within 55px Y distance)
            row_nums = []
            for n in num_candidates:
                dy = abs(n["cy"] - ore_y)
                if dy <= 55:
                    dx = n["cx"] - ore_x
                    row_nums.append((dy + abs(dx) * 0.1, n["scu"]))

            # Filter quality ratings aligned horizontally (within 55px Y distance)
            row_qualities = []
            for q in quality_candidates:
                dy = abs(q["cy"] - ore_y)
                if dy <= 55:
                    dx = q["cx"] - ore_x
                    row_qualities.append((dy + abs(dx) * 0.1, q["quality"]))

            if row_nums:
                row_nums.sort(key=lambda x: x[0])
                best_scu = row_nums[0][1]
                paired_haul[ore_name] = round(paired_haul.get(ore_name, 0.0) + best_scu, 2)

                best_q = 850
                if row_qualities:
                    row_qualities.sort(key=lambda x: x[0])
                    best_q = row_qualities[0][1]

                paired_haul.qualities[ore_name] = best_q
                paired_haul.details.append({
                    "ore": ore_name,
                    "scu": best_scu,
                    "quality": best_q
                })

        if paired_haul:
            break

    return paired_haul
