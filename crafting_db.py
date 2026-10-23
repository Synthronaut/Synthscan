"""
SynthScan - Crafting Database & Inventory Reduction Engine
Handles craftable item recipes and automatically deducts materials from the vault.
Supports custom user-defined recipes stored in crafting_recipes.json.
"""

import os
import json
from refinery_db import load_inventory, save_inventory

RECIPES_FILE = os.path.join(os.path.dirname(__file__), "crafting_recipes.json")

DEFAULT_RECIPES = [
    # --- Mining Modules & Gadgets ---
    {
        "id": "mod_surge",
        "name": "Surge Module",
        "category": "Mining Consumables",
        "desc": "Boosts mining laser power output.",
        "cost": {"Quantainium": 0.25, "Titanium": 0.50}
    },
    {
        "id": "mod_stampede",
        "name": "Stampede Module",
        "category": "Mining Consumables",
        "desc": "Maximizes laser charge rate.",
        "cost": {"Bexalite": 0.20, "Gold": 0.30}
    },
    {
        "id": "mod_focus",
        "name": "Focus III Module",
        "category": "Mining Consumables",
        "desc": "Stabilizes catastrophic charge window.",
        "cost": {"Laranite": 0.25, "Silicon": 0.50}
    },
    {
        "id": "mod_torpid",
        "name": "Torpid Module",
        "category": "Mining Consumables",
        "desc": "Reduces rock instability drastically.",
        "cost": {"Hephaestanite": 0.30, "Copper": 0.40}
    },
    {
        "id": "mod_brandt",
        "name": "Brandt Module",
        "category": "Mining Consumables",
        "desc": "Significantly decreases rock resistance.",
        "cost": {"Taranite": 0.20, "Borase": 0.30}
    },
    {
        "id": "gadget_boremax",
        "name": "BoreMax Mining Gadget",
        "category": "Mining Consumables",
        "desc": "Deployable rock attachment for high mass deposits.",
        "cost": {"Agricium": 0.40, "Titanium": 0.80}
    },
    {
        "id": "gadget_waveshift",
        "name": "WaveShift Gadget",
        "category": "Mining Consumables",
        "desc": "Subharmonic filter gadget for unstable deposits.",
        "cost": {"Quantainium": 0.50, "Silicon": 0.80}
    },

    # --- Ship & Industrial Crafting ---
    {
        "id": "ind_composite_plate",
        "name": "Composite Armor Plate",
        "category": "Ship & Industrial",
        "desc": "Heavy composite plate for hull repair.",
        "cost": {"Titanium": 1.00, "Tungsten": 0.50}
    },
    {
        "id": "ind_construction_mat",
        "name": "Construction Materials (1 SCU)",
        "category": "Ship & Industrial",
        "desc": "Standard industrial construction cargo.",
        "cost": {"Iron": 0.60, "Aluminum": 0.40}
    },
    {
        "id": "ind_quantum_fuel",
        "name": "Quantum Fuel Tank Refill",
        "category": "Ship & Industrial",
        "desc": "Concentrated quantum propulsion charge.",
        "cost": {"Quantainium": 1.00, "Copper": 0.50}
    },
    {
        "id": "ind_hull_patch",
        "name": "Hull Repair Patch (x5)",
        "category": "Ship & Industrial",
        "desc": "Quick-weld hull repair plating.",
        "cost": {"Aluminum": 0.50, "Copper": 0.25}
    },

    # --- Gear & Consumables ---
    {
        "id": "gear_medpen_bundle",
        "name": "MedPen Crate (x10)",
        "category": "FPS Gear & Supplies",
        "desc": "10-pack Hemozal medical autoinjectors.",
        "cost": {"Agricium": 0.15, "Silicon": 0.30}
    },
    {
        "id": "gear_ammo_crate",
        "name": "Ballistic Ammo Crate",
        "category": "FPS Gear & Supplies",
        "desc": "Bulk ballistic ammunition restock.",
        "cost": {"Copper": 0.50, "Iron": 0.50}
    },
    {
        "id": "gear_battery_pack",
        "name": "Heavy Energy Battery",
        "category": "FPS Gear & Supplies",
        "desc": "High capacity weapon and shield energy cell.",
        "cost": {"Gold": 0.20, "Silicon": 0.40}
    }
]

def load_recipes():
    if not os.path.exists(RECIPES_FILE):
        save_recipes(DEFAULT_RECIPES)
        return DEFAULT_RECIPES.copy()
    try:
        with open(RECIPES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_RECIPES.copy()

def save_recipes(recipes):
    try:
        with open(RECIPES_FILE, "w", encoding="utf-8") as f:
            json.dump(recipes, f, indent=4)
    except Exception as e:
        print("Failed to save recipes:", e)

def add_custom_recipe(name, category, cost_dict, desc=""):
    recipes = load_recipes()
    recipe_id = "custom_" + name.lower().replace(" ", "_")
    new_entry = {
        "id": recipe_id,
        "name": name,
        "category": category if category else "Custom",
        "desc": desc,
        "cost": cost_dict
    }
    recipes.append(new_entry)
    save_recipes(recipes)
    return new_entry

def delete_recipe(recipe_id):
    recipes = load_recipes()
    recipes = [r for r in recipes if r.get("id") != recipe_id]
    save_recipes(recipes)
    return recipes

def craft_item(recipe, count=1, use_best_materials=True, selected_batches=None):
    """
    Attempts to craft `count` of a recipe.
    - use_best_materials: If True, consumes materials starting from highest quality batch (Star Citizen default).
                          If False, consumes starting from lowest quality batch (to save high-quality materials).
    - selected_batches: Optional dict { ore_name: batch_id } to prioritize consuming from a specific quality batch.
    Returns: (success: bool, message: str, deducted_summary: dict)
    """
    if count <= 0:
        return False, "Count must be at least 1", {}

    inv = load_inventory()
    totals = inv.get("totals", {})
    batches = inv.setdefault("batches", {})
    cost = recipe.get("cost", {})

    # 1. Verify enough materials exist in totals
    missing = []
    needed_materials = {}
    for ore, req_scu in cost.items():
        total_req = round(req_scu * count, 2)
        needed_materials[ore] = total_req
        avail = totals.get(ore, 0.0)
        if avail < total_req - 0.0001:
            missing.append(f"{ore} (Need {total_req:,.2f} SCU, vault has {avail:,.2f} SCU)")

    if missing:
        msg = "Insufficient materials:\n• " + "\n• ".join(missing)
        return False, msg, {}

    # 2. Perform Deduction with Quality Batch Logic
    deducted_summary = {}
    deducted_batch_details = []
    import datetime

    for ore, total_req in needed_materials.items():
        needed = total_req
        b_list = batches.setdefault(ore, [])
        if not b_list:
            # Fallback if no batches exist but totals had it
            b_list.append({
                "id": f"{ore.lower()}_def",
                "scu": totals.get(ore, needed),
                "quality": 850,
                "added_at": "Default Batch"
            })

        # Sort batches based on choice
        # If user selected a specific batch for this ore, put that batch first
        specific_id = selected_batches.get(ore) if selected_batches else None

        def _sort_key(b):
            is_priority = 1 if (specific_id and b.get("id") == specific_id) else 0
            q = b.get("quality", 850)
            return (is_priority, q if use_best_materials else -q)

        b_list.sort(key=_sort_key, reverse=True)

        ore_deducted_total = 0.0
        for b in list(b_list):
            if needed <= 0.0001:
                break
            b_avail = b.get("scu", 0.0)
            if b_avail <= 0.0001:
                continue

            take = min(needed, b_avail)
            take = round(take, 2)
            if take > b_avail:
                take = round(b_avail, 2)

            b["scu"] = round(b_avail - take, 2)
            needed = round(needed - take, 2)
            ore_deducted_total = round(ore_deducted_total + take, 2)

            detail = {
                "ore": ore,
                "batch_id": b.get("id"),
                "scu": take,
                "quality": b.get("quality", 850)
            }
            deducted_batch_details.append(detail)

        # Remove empty batches
        batches[ore] = [b for b in b_list if b.get("scu", 0.0) > 0.0001]

        # Recompute totals[ore]
        rem_scu = round(sum(b.get("scu", 0.0) for b in batches[ore]), 2)
        if rem_scu <= 0.0001:
            totals.pop(ore, None)
            batches.pop(ore, None)
        else:
            totals[ore] = rem_scu

        deducted_summary[ore] = ore_deducted_total

    # 3. Log to History
    history = inv.setdefault("history", [])
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_entry = {
        "timestamp": now_str,
        "source": f"Fabricated {count}x {recipe['name']}",
        "mode": "Best Quality" if use_best_materials else "Saved Best Quality",
        "deductions": deducted_summary,
        "batch_details": deducted_batch_details
    }
    history.insert(0, history_entry)

    save_inventory(inv)

    detail_lines = []
    for d in deducted_batch_details:
        detail_lines.append(f"• {d['ore']}: -{d['scu']:.2f} SCU [{d['quality']} Quality]")

    mode_tag = "BEST MATERIALS" if use_best_materials else "SAVED BEST (LOWEST USED)"
    success_msg = f"Crafted {count}x {recipe['name']} [{mode_tag}]!\nDeducted from vault:\n" + "\n".join(detail_lines)
    return True, success_msg, deducted_summary
