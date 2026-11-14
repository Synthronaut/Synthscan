"""Build and inject ALL Wikelo contracts (ships, weapons, armor, gear, currencies) into SynthScan."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "wikelo_data.json"

def clean_item_name(raw_name, cat):
    parts = [p.strip() for p in raw_name.split(';') if p.strip()]
    if not parts:
        return raw_name
    first = parts[0]
    if cat == 'armor':
        # Simplify e.g. "Ana Arms Endro; Ana Legs Endro..." -> "Ana Endro Armor Set"
        clean = first.replace('Arms', '').replace('Legs', '').replace('Core', '').replace('Helmet', '').strip()
        clean = re.sub(r'\s+', ' ', clean)
        if not clean.endswith('Armor Set') and not clean.endswith('Suit'):
            clean += ' Armor Set'
        return clean
    elif cat == 'weapon':
        clean = first
        if len(parts) > 1 and 'Cap' in parts[1]:
            clean += ' (+ Ammo Pack)'
        return clean
    elif cat == 'gear':
        return first
    return first

def parse_recipe(recipe):
    parts = [p.strip() for p in recipe.split(';') if p.strip()]
    favors = 0
    items = []
    for p in parts:
        m = re.match(r'^(\d+)x\s+(.+)$', p)
        if m:
            qty, name = int(m.group(1)), m.group(2).strip()
            if 'wikelo favor' in name.lower():
                favors = qty
            else:
                items.append({'name': name, 'amount': qty, 'label': f'{qty} × {name}', 'detail': f'Turn-in requirement: {name}'})
        else:
            items.append({'name': p, 'amount': 1, 'label': p, 'detail': f'Turn-in requirement: {p}'})
    return favors, items

def build_all_wikelo_rows():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing {DATA_PATH}")

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = []

    # 1. Ships & Vehicles (42 entries)
    for s in data.get('ships', []):
        sid = s.get('id', 'ship_unknown')
        name = s.get('name', '')
        mission = s.get('mission_name', name)
        desc = s.get('description', '')
        recipe = s.get('recipe', '')
        favors, req_items = parse_recipe(recipe)

        is_vehicle = (
            s.get('category') == 'vehicle'
            or 'ATLS' in name
            or 'Ursa' in name
            or 'Nox' in name
            or 'Pulse' in name
            or 'Golem' in name
        )
        kind = "Vehicle" if is_vehicle else "Ship"

        display_name = f"{name} (Wikelo Edition)" if "Wikelo" not in name and "Mod" not in name else name

        favors_label = f"{favors} × Wikelo Favors" if favors > 0 else "Direct Material Barter"

        detail = (
            f"{display_name}\n"
            f"{kind} · Wikelo Emporium Exclusive\n\n"
            f"WIKELO TURN-IN CONTRACT\n"
            f"Contract: \"{mission}\"\n"
            f"Requirements: {recipe or 'See turn-in items'} (NO aUEC COST)\n"
            f"Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            f"Delivery: Station Freight Elevator\n"
            f"Prerequisite: Complete \"Wikelo Arrive to System\" contract in mobiGlas\n\n"
            f"Wikelo Dialogue:\n\"{desc}\"\n\n"
            f"Source: starcitizen.tools/Wikelo · verified for Alpha 4.10.2"
        )

        search_tokens = [
            display_name, name, mission, "Wikelo", "Wikalo", "Wickalow",
            "Barter", "Turn-in", "Favor", "Favors", kind, "Ships"
        ]
        for it in req_items:
            search_tokens.append(it['name'])

        turnin_data = {
            "task": mission,
            "favors": favors,
            "favors_label": favors_label,
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": req_items,
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator",
            "reputation_reward": s.get('reputation_reward', 25),
            "briefing": desc
        }

        # Size & specs inference
        length = 20.0
        hangar = "Small (S)"
        if "Polaris" in name:
            length, hangar = 155.0, "Capital / Docking"
        elif "Idris" in name:
            length, hangar = 240.0, "Capital / Docking"
        elif "Starlifter" in name or "Asgard" in name:
            length, hangar = 94.0, "Large (L)"
        elif "Starlancer" in name or "Taurus" in name or "Max" in name or "C1" in name or "Spirit" in name or "Apollo" in name:
            length, hangar = 45.0, "Medium (M)"
        elif is_vehicle:
            length, hangar = 3.5, "Vehicle Bay / XS"

        row = {
            "id": f"wikelo-{sid}",
            "item_id": f"wikelo-{sid}",
            "name": display_name,
            "kind": kind,
            "category": "Wikelo Barter Ships",
            "source_category": "Wikelo Emporium",
            "detail": detail,
            "icon": "",
            "search": " ".join(dict.fromkeys(search_tokens)),
            "ship_overview": {
                "source": "Wikelo Emporium",
                "patch": "4.10.2",
                "crew": "1–2" if not "Polaris" in name and not "Idris" in name else "6–14",
                "concept": False,
                "length": length,
                "hangar": hangar,
                "roles": ["Barter Trade", kind]
            },
            "ship_stats": {
                "role": "Banu Barter Trade Vessel",
                "size": 6 if "Capital" in hangar else 3 if "Medium" in hangar else 2 if "Small" in hangar else 1,
                "patch": "sc-alpha-4.10.2"
            },
            "wikelo_turnin": turnin_data,
            "hangar": hangar
        }
        rows.append(row)

    # 2. Weapons, Armor, and Gear (41 entries)
    for it in data.get('items', []):
        iid = it.get('id', 'item_unknown')
        cat = it.get('category', 'gear')
        raw_name = it.get('name', '')
        mission = it.get('mission_name', raw_name)
        desc = it.get('description', '')
        recipe = it.get('recipe', '')
        favors, req_items = parse_recipe(recipe)

        clean_name = clean_item_name(raw_name, cat)

        if cat == 'weapon':
            category_label = "Wikelo Weapons"
            item_type = "WeaponPersonal"
        elif cat == 'armor':
            category_label = "Wikelo Armor"
            item_type = "Char_Armor_Torso"
        else:
            category_label = "Wikelo Gear"
            item_type = "Equipment"

        favors_label = f"{favors} × Wikelo Favors" if favors > 0 else "Direct Material Barter"

        detail = (
            f"{clean_name}\n"
            f"{cat.title()} · Wikelo Emporium Exclusive\n\n"
            f"WIKELO TURN-IN CONTRACT\n"
            f"Contract: \"{mission}\"\n"
            f"Requirements: {recipe or 'See turn-in items'} (NO aUEC COST)\n"
            f"Reward: {raw_name}\n"
            f"Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n"
            f"Delivery: Station Freight Elevator\n"
            f"Prerequisite: Complete \"Wikelo Arrive to System\" contract in mobiGlas\n\n"
            f"Wikelo Dialogue:\n\"{desc}\"\n\n"
            f"Source: starcitizen.tools/Wikelo · verified for Alpha 4.10.2"
        )

        search_tokens = [
            clean_name, raw_name, mission, "Wikelo", "Wikalo", "Wickalow",
            "Barter", "Turn-in", "Favor", "Favors", cat, category_label
        ]
        for r_it in req_items:
            search_tokens.append(r_it['name'])

        turnin_data = {
            "task": mission,
            "favors": favors,
            "favors_label": favors_label,
            "replace_cost": True,
            "cost_label": "NO aUEC COST · BARTER TURN-IN ONLY",
            "items": req_items,
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Complete \"Wikelo Arrive to System\" contract in mobiGlas Contract Manager",
            "method": "Physical delivery to Station Freight Elevator",
            "reputation_reward": it.get('reputation_reward', 25),
            "briefing": desc
        }

        row = {
            "id": f"wikelo-{iid}",
            "item_id": f"wikelo-{iid}",
            "name": clean_name,
            "kind": "Item",
            "category": category_label,
            "source_category": "Wikelo Emporium",
            "detail": detail,
            "icon": "",
            "search": " ".join(dict.fromkeys(search_tokens)),
            "item_type": item_type,
            "wikelo_turnin": turnin_data
        }
        rows.append(row)

    # 3. Currency Exchanges (5 entries)
    for idx, ce in enumerate(data.get('currency_exchanges', [])):
        recipe = ce.get('recipe', '')
        reward = ce.get('reward', 'Wikelo Favor')
        mission = ce.get('mission_name', f'Exchange for {reward}')
        desc = ce.get('description', '')
        favors, req_items = parse_recipe(recipe)

        name = f"{reward} (Trade: {recipe})" if recipe else f"{reward} Exchange"

        detail = (
            f"{name}\n"
            f"Currency / Barter Token · Wikelo Emporium\n\n"
            f"CURRENCY CONVERSION CONTRACT\n"
            f"Contract: \"{mission}\"\n"
            f"Turn-In: {recipe}\n"
            f"Receives: 1× {reward}\n"
            f"Location: Wikelo Emporium (Dasi / Selo / Kinga Station)\n\n"
            f"Wikelo Dialogue:\n\"{desc}\"\n\n"
            f"Source: starcitizen.tools/Wikelo · verified for Alpha 4.10.2"
        )

        search_tokens = [
            name, reward, mission, "Wikelo", "Wikalo", "Wickalow",
            "Favor", "Favors", "Scrip", "Currency", "Exchange", recipe
        ]

        turnin_data = {
            "task": mission,
            "favors": 0,
            "favors_label": "Direct Exchange",
            "replace_cost": True,
            "cost_label": "1:1 DIRECT CURRENCY CONVERSION",
            "items": req_items,
            "locations": "Wikelo Emporium (Dasi Station - Hurston, Selo Station - Crusader/Yela, Kinga Station - microTech)",
            "prerequisite": "Wikelo Emporium Terminal Exchange",
            "method": "Physical delivery to Station Freight Elevator",
            "briefing": desc
        }

        row = {
            "id": f"wikelo-currency-{idx+1}",
            "item_id": f"wikelo-currency-{idx+1}",
            "name": name,
            "kind": "Material",
            "category": "Wikelo Currencies",
            "source_category": "Wikelo Emporium",
            "detail": detail,
            "icon": "",
            "search": " ".join(dict.fromkeys(search_tokens)),
            "item_type": "Commodity",
            "wikelo_turnin": turnin_data
        }
        rows.append(row)

    # 4. Intro Mission
    intro = data.get('intro_mission')
    if intro:
        recipe = intro.get('recipe', '1x Vestal Water; 3x Tundra Kopion Horn')
        favors, req_items = parse_recipe(recipe)
        detail = (
            "Wikelo Introductory Contract: \"Wikelo Arrive to System\"\n"
            "Mission Unlock · Wikelo Emporium\n\n"
            "CONTRACT DETAILS\n"
            "Turn in: 1× Vestal Water + 3× Tundra Kopion Horn\n"
            "Reward: Unlocks Wikelo Barter Network & Trading Contracts (+10 Rep)\n"
            "Location: Contract Manager (mobiGlas) -> Wikelo Emporium\n\n"
            f"Wikelo Dialogue:\n\"{intro.get('description', '')}\"\n\n"
            "Source: starcitizen.tools/Wikelo · verified for Alpha 4.10.2"
        )
        row = {
            "id": "wikelo-intro-mission",
            "item_id": "wikelo-intro-mission",
            "name": "Wikelo Unlock: \"Wikelo Arrive to System\"",
            "kind": "Item",
            "category": "Wikelo Intro",
            "source_category": "Wikelo Emporium",
            "detail": detail,
            "icon": "",
            "search": "Wikelo Arrive to System Wikalo Wickalow Vestal Water Tundra Kopion Horn Intro Unlock Mission",
            "item_type": "Equipment",
            "wikelo_turnin": {
                "task": "Wikelo Arrive to System",
                "favors": 0,
                "favors_label": "Intro Contract",
                "replace_cost": True,
                "cost_label": "UNLOCK PREREQUISITE CONTRACT",
                "items": req_items,
                "locations": "Wikelo Emporium (Dasi / Selo / Kinga Station)",
                "prerequisite": "Available upon entering Stanton system",
                "method": "Physical delivery to Station Freight Elevator",
                "reputation_reward": 10,
                "briefing": intro.get('description', '')
            }
        }
        rows.append(row)

    return rows

ALL_WIKELO_ROWS = build_all_wikelo_rows()

def update_library_file(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"Skipping {p}: file not found")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading {p}: {e}")
        return

    rows = data.get("rows", [])
    row_ids = {r.get("id"): idx for idx, r in enumerate(rows)}

    added = 0
    updated = 0
    for w in ALL_WIKELO_ROWS:
        wid = w["id"]
        if wid in row_ids:
            rows[row_ids[wid]] = w
            updated += 1
        else:
            rows.insert(0, w)
            added += 1

    data["rows"] = rows
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)
    print(f"Updated {p}: added {added}, updated {updated}, total rows {len(rows)}")

if __name__ == "__main__":
    print(f"Generated {len(ALL_WIKELO_ROWS)} total Wikelo rows")
    targets = [
        ROOT / "dist" / "native" / "workspace_library.json",
        Path(os.path.expandvars(r"%LOCALAPPDATA%\SynthScan\native\workspace_library.json")),
    ]
    for target in targets:
        update_library_file(target)
