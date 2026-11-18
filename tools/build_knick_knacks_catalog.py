"""Build data/knick_knacks_catalog.json from Data.p4k, global.ini, and SynthScan catalogs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_P4K = Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Data.p4k')
DEFAULT_GLOBAL_INI = Path(r'C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\data\Localization\english\global.ini')
STARBREAKER = ROOT / 'third_party' / 'starbreaker' / 'v0.3.2' / 'starbreaker.exe'

_CRC32C_POLY = 0x82F63B78
_CRC32C_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ _CRC32C_POLY if (_c & 1) else (_c >> 1)
    _CRC32C_TABLE.append(_c)

_NON_ITEM_LIBRARY_TYPES = {
    'AIModule', 'AttachedPart', 'Button', 'Char_Accessory_Eyes', 'Char_Body',
    'Char_Hair_Color', 'Char_Head', 'Char_Head_Eyes', 'Char_Head_Hair',
    'Char_Head_Piercings', 'Char_Skin_Color', 'CommsController', 'ControlPanel',
    'CoolerController', 'Display', 'DockingAnimator', 'DockingCollar', 'Door',
    'DoorController', 'Elevator', 'EnergyController', 'FlightController',
    'FuelIntake', 'LightController', 'LifeSupportGenerator', 'MainThruster',
    'ManneuverThruster', 'MissileController', 'Radar_Display', 'Relay',
    'Seat', 'SeatAccess', 'SeatDashboard', 'SelfDestruct', 'ShieldController',
    'TargetSelector', 'Usable', 'WeaponController',
}

_NON_ITEM_RECORD_FRAGMENTS = (
    '/ships/displays/',
    '/ships/dashboard/',
    '/vehicles/dashboard/',
    '/decals/',
    '/doors/',
    '/lighting/',
    '/internal/',
    '/rooms/',
)

_NON_ITEM_EXACT_NAMES = {
    'GeomEntity', 'LightGroup', 'Room_RN', 'RoomConnector', 'FP_Visor', 'SCItemDisplayScreen',
    'ChipSet_LightControl', 'Vehicle_Screen_MFD', 'Vehicle_Screen_Physical',
    'StreamingObjectContainer', 'VehicleObjectContainer', 'UnattendedVehicleMarker',
    'ObjectContainer', 'ObjectContainerModifier', 'procedural_connection_navlink',
    'Player', 'Universal_Necksock',
}


def crc32c_bytes(data: bytes) -> int:
    c = 0xFFFFFFFF
    for b in data:
        c = _CRC32C_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


def cig_guid_crc(guid_str: str) -> int:
    hx = guid_str.replace('-', '').strip()
    if len(hx) != 32:
        raise ValueError(f'Invalid GUID: {guid_str!r}')
    hi = int(hx[:16], 16)
    lo = int(hx[16:], 16)
    return crc32c_bytes(struct.pack('<QQ', hi, lo))


def load_global_ini(ini_path: Path | None = None) -> dict[str, str]:
    candidates = [ini_path] if ini_path else []
    candidates.extend([
        DEFAULT_GLOBAL_INI,
        ROOT / 'data' / 'global.ini',
    ])
    strings: dict[str, str] = {}
    for p in candidates:
        if p and p.exists():
            for line in p.read_text(encoding='utf-8-sig', errors='replace').splitlines():
                if '=' in line:
                    k, v = line.split('=', 1)
                    strings[k.strip().lower()] = v.strip()
            if strings:
                return strings
    return strings


def infer_system(record_name: str, loc_key: str, display_name: str) -> str:
    joined = f'{record_name} {loc_key} {display_name}'.lower()
    if 'nyx' in joined or 'levski' in joined or 'delamar' in joined or 'keeger' in joined:
        return 'Nyx'
    if any(k in joined for k in ('pyro', 'rr_p', 'checkmate', 'orbituary', 'ruin', 'bloom', 'monox', 'terminu', 'patch_city', 'gaslight', 'rod_s', 'dudley', 'megumi', 'rat_s')):
        if 'stantonpyro' in joined or 'pyro_jpstation' in joined:
            return 'Pyro' if 'pyro gateway' in display_name.lower() else 'Stanton'
        return 'Pyro'
    if any(k in joined for k in ('stanton', 'hur', 'cru', 'arc', 'mic', 'lorville', 'orison', 'area18', 'newbabbage', 'new babbage', 'everus', 'baijini', 'seraphim', 'tressler', 'grimhex', 'grim hex', 'collectorasteroid_stanton', 'asd_delve')):
        return 'Stanton'
    return ''


def load_starmap_locations(p4k: Path, gini: dict[str, str]) -> dict[str, dict[str, str]]:
    if not STARBREAKER.exists() or not p4k.exists():
        return {}
    res = subprocess.run(
        [str(STARBREAKER), 'dcb', 'query', '--p4k', str(p4k), 'StarMapObject'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    )
    dec = json.JSONDecoder()
    s = res.stdout
    pos, n = 0, len(s)
    locations: dict[str, dict[str, str]] = {}
    while pos < n:
        while pos < n and s[pos].isspace():
            pos += 1
        if pos >= n:
            break
        obj, pos = dec.raw_decode(s, pos)
        rid = obj.get('_RecordId_')
        if not rid or len(rid.replace('-', '')) != 32:
            continue
        rv = obj.get('_RecordValue_') or {}
        rname = obj.get('_RecordName_') or ''
        short_rec = rname.removeprefix('StarMapObject.')
        loc_key = (rv.get('name') or '').strip()
        disp = gini.get(loc_key.lstrip('@').lower()) or ''
        if not disp or disp.startswith('@'):
            disp = short_rec.replace('_', ' ')
        # Clean common localization placeholders
        if disp == '@LOC_UNINITIALIZED':
            disp = short_rec.replace('_', ' ')
        crc = str(cig_guid_crc(rid))
        locations[crc] = {
            'name': disp,
            'record': short_rec,
            'system': infer_system(short_rec, loc_key, disp),
        }
    return locations


def _clean_record_display_name(short_rec: str) -> str:
    txt = short_rec
    for prefix in ('PlayerDeco_Static_', 'PlayerDeco_', 'BaseBuilding_Interactables_', 'Carryable_'):
        if txt.startswith(prefix):
            txt = txt[len(prefix):]
            break
    return re.sub(r'\s+', ' ', txt.replace('_', ' ')).strip()


def scan_entity_classes(
    p4k: Path, lib_crcs: set[int], gini: dict[str, str],
) -> tuple[list[int], list[int], list[int], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Stream all EntityClassDefinition records to extract vehicles, hangars, structural CRCs, extra items, and vehicle names."""
    if not STARBREAKER.exists() or not p4k.exists():
        return [], [], [], {}, {}
    proc = subprocess.Popen(
        [str(STARBREAKER), 'dcb', 'query', '--p4k', str(p4k), 'EntityClassDefinition'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
    )
    vehicles: list[int] = []
    hangars: list[int] = []
    non_items: list[int] = []
    extra_items: dict[str, dict[str, str]] = {}
    vehicle_names: dict[str, dict[str, str]] = {}

    cur_name = ''
    in_vehicle_tag_prefixes = (
        'AEGS_', 'ANVL_', 'ARGO_', 'BANU_', 'CNOU_', 'CRUS_', 'DRAK_', 'ESPR_',
        'GAMA_', 'GATAC_', 'GRIN_', 'KRIG_', 'MISC_', 'MRAI_', 'ORIG_', 'RSI_',
        'TMBL_', 'VNCL_', 'XIAN_',
    )
    veh_subparts = (
        '_dashboard', '_turret', '_door', '_thruster', '_seat', '_display', '_hud',
        '_radar', '_ramp', '_elevator', '_ladder', '_bed', '_kitchen', '_toilet',
        '_screen', '_panel', '_lights', '_light_', '_decal', '_armor', '_canopy', '_wing',
        '_wingtip', '_cargogrid', '_landing', '_module', '_pod', '_scitem_',
        '_relay', '_cockpit', '_airlock', '_docking', '_geo_', '_flare', '_decoy',
        '_noiselauncher', '_selfdestruct', '_barrel', '_firingmechanism', '_powerarray',
        '_ventilation',
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        if line.startswith('  "_RecordName_":'):
            m = re.search(r'"([^"]+)"\s*,?\s*$', line)
            cur_name = m.group(1) if m else ''
        elif line.startswith('  "_RecordId_":'):
            m = re.search(r'([0-9a-f-]{36})', line)
            if not m or not cur_name:
                continue
            rid = m.group(1)
            crc = cig_guid_crc(rid)
            short = cur_name.removeprefix('EntityClassDefinition.')
            low = short.lower()
            if short.startswith('Hangar_'):
                hangars.append(crc)
                non_items.append(crc)
                continue
            if (
                short in _NON_ITEM_EXACT_NAMES
                or short.startswith(('H_Dashboard_', 'ControlPanel_', 'Door_', 'Relay_', 'RELAY_', 'VHCL_', 'MRCK_', 'WeaponRack', 'Universal_Necksock', 'universal_necksock', 'body_01', 'Chair_', 'Table_', 'Bed_', 'Transit', 'Elevator_', 'LoadingPlatform'))
                or '_template' in low
                or '_barrel_s' in low
                or low.endswith(('_firingmechanism', '_powerarray', '_ventilation'))
                or re.search(r'_(?:firingmechanism|powerarray|ventilation)_s\d+$', low)
            ):
                non_items.append(crc)
                continue

            # Detect vehicles: ship/vehicle hull definitions not in scitem parts
            is_veh_subpart = any(tok in low for tok in veh_subparts) or low.endswith(('_geo', '_light'))
            if 'atls_geo' in low:
                is_veh_subpart = False
            if (
                short.startswith(in_vehicle_tag_prefixes)
                and not is_veh_subpart
                and '_scitem' not in low
                and not any(low.startswith(p) for p in ('shld_', 'powr_', 'qdrv_', 'cool_', 'jdrv_', 'rad_', 'gats_', 'mxox_', 'klwe_', 'amrs_', 'behr_', 'apoc_', 'espr_', 'hrst_', 'aspr_', 'krig_', 'jokr_', 'taln_', 'mining_', 'asad_', 'drak_salvage'))
                and crc not in lib_crcs
            ):
                vehicles.append(crc)
                vdisp = (
                    gini.get(f'vehicle_name{low}')
                    or gini.get(f'vehicle_name_{low}')
                    or gini.get(f'item_name{low}')
                    or _clean_record_display_name(short)
                )
                vehicle_names[str(crc)] = {'name': vdisp, 'record': short}
                continue

            if short.startswith('Flair_Badge_'):
                disp = (
                    gini.get(f'item_name{low}')
                    or gini.get(f'item_name_{low}')
                    or _clean_record_display_name(short.removeprefix('Flair_Badge_'))
                )
                extra_items[str(crc)] = {
                    'name': disp,
                    'category': 'Hangar & flair',
                    'type': 'Flair',
                    'record': short,
                }
                continue

            if crc not in lib_crcs:
                if short.startswith(('PlayerDeco_', 'BaseBuilding_', 'TrophyCase_')):
                    extra_items[str(crc)] = {
                        'name': _clean_record_display_name(short),
                        'category': 'Cargo & containers' if short.startswith(('BaseBuilding_', 'TrophyCase_')) else 'Hangar & flair',
                        'type': 'Flair' if short.startswith('PlayerDeco_') else 'BaseBuilding',
                        'record': short,
                    }
                elif any(low.startswith(p) for p in ('cds_', 'adp_', 'orc_', 'inquisitor_', 'morozov_', 'strata_', 'volt_', 'behr_', 'klwe_', 'ksar_', 'gmni_', 'apar_', 'krig_', 'grin_')):
                    # Resolvable item record missing from local_game_library
                    disp = (
                        gini.get(f'item_name{low}')
                        or gini.get(f'item_name_{low}')
                        or _clean_record_display_name(short)
                    )
                    is_wpn = any(tok in low for tok in ('rifle', 'smg', 'pistol', 'sniper', 'hmg', 'lmg', 'shotgun', 'ubarrel', 'optic', 'flsh', 'comp', 'stab', 'supp', 'mag', 'battery', 'multitool'))
                    extra_items[str(crc)] = {
                        'name': disp,
                        'category': 'Weapons & ammunition' if is_wpn else 'Armor & clothing',
                        'type': 'WeaponPersonal' if is_wpn else 'Armor',
                        'record': short,
                    }
                elif any(tok in low for tok in ('dashboard', 'thruster', 'door_', '_scitem_door', 'screen_', '_hud_', 'projector_hud', 'turret_lights', 'cargogrid', 'room_', 'lightgroup', 'geom', 'chipset_', 'visor', 'roomconnector', 'navlink')):
                    non_items.append(crc)
    proc.wait()
    return sorted(set(vehicles)), sorted(set(hangars)), sorted(set(non_items)), extra_items, vehicle_names


def parse_wikelo_ingredients(wikelo_path: Path) -> list[str]:
    if not wikelo_path.exists():
        return []
    data = json.loads(wikelo_path.read_text(encoding='utf-8'))
    names: set[str] = {'wikelo favor', 'polaris bit', 'mg scrip', 'council scrip'}
    for section in ('items', 'ships', 'currency_exchanges'):
        for row in data.get(section) or []:
            recipe = str(row.get('recipe') or row.get('cost') or '')
            for part in re.split(r'[;,\n]+', recipe):
                cleaned = re.sub(r'^\s*\d+(?:\.\d+)?\s*[x×]?\s*', '', part, flags=re.I).strip()
                # Ignore armor/weapon/ship reward trade-ins unless clearly barter material
                low = cleaned.lower()
                if cleaned and len(cleaned) >= 3 and not low.endswith(('scu', 'uec', 'auec')):
                    names.add(low)
    for ing in data.get('ingredients_info') or []:
        nm = str(ing.get('name') or '').strip().lower()
        if nm:
            names.add(nm)
    return sorted(names)


def parse_crafting_materials(crafting_path: Path) -> list[str]:
    if not crafting_path.exists():
        return []
    data = json.loads(crafting_path.read_text(encoding='utf-8'))
    names: set[str] = set()
    for m in data.get('materials') or []:
        nm = str(m.get('name') or '').strip().lower()
        if nm:
            names.add(nm)
    return sorted(names)


def build_catalog(
    p4k: Path = DEFAULT_P4K,
    global_ini: Path | None = None,
    output: Path = ROOT / 'data' / 'knick_knacks_catalog.json',
) -> dict:
    gini = load_global_ini(global_ini)
    lib_path = ROOT / 'data' / 'local_game_library.json'
    lib = json.loads(lib_path.read_text(encoding='utf-8'))
    lib_crcs: set[int] = set()
    vehicles_from_lib: set[int] = set()
    non_items_from_lib: set[int] = set()
    veh_names_from_lib: dict[str, dict[str, str]] = {}

    for entry in lib.get('entries') or []:
        gid = entry.get('id')
        if not gid or len(gid.replace('-', '')) != 32:
            continue
        crc = cig_guid_crc(gid)
        lib_crcs.add(crc)
        rec = (entry.get('record') or '').lower()
        tp = entry.get('type') or ''
        tag = (entry.get('tag') or '').removeprefix('EntityClassDefinition.')
        is_flight_blade = tp == 'Flight Blade' or '_blade_' in rec or 'flight blade' in str(entry.get('name') or '').lower()
        if '/entities/spaceships/' in rec or '/entities/groundvehicles/' in rec:
            vehicles_from_lib.add(crc)
            nm = str(entry.get('name') or _clean_record_display_name(tag)).strip()
            if nm:
                veh_names_from_lib[str(crc)] = {'name': nm, 'record': tag}
        elif (
            (entry.get('internal') and not is_flight_blade)
            or tp in _NON_ITEM_LIBRARY_TYPES
            or any(frag in rec for frag in _NON_ITEM_RECORD_FRAGMENTS)
            or tag in _NON_ITEM_EXACT_NAMES
        ):
            non_items_from_lib.add(crc)

    locations = load_starmap_locations(p4k, gini)
    vehicles_p4k, hangars, non_items_p4k, extra_items, vehicle_names = scan_entity_classes(p4k, lib_crcs, gini)
    for k, v in veh_names_from_lib.items():
        vehicle_names.setdefault(k, v)

    # Read game build id if available
    build_id = ''
    bm = p4k.parent / 'build_manifest.id'
    if bm.exists():
        try:
            build_id = json.loads(bm.read_text(encoding='utf-8')).get('Data', {}).get('BuildId', '')
        except Exception:
            build_id = ''

    catalog = {
        'schema': 1,
        'build_id': build_id,
        'locations': locations,
        'vehicle_crcs': sorted(vehicles_from_lib | set(vehicles_p4k)),
        'vehicle_names': vehicle_names,
        'hangar_crcs': hangars,
        'non_item_crcs': sorted(non_items_from_lib | set(non_items_p4k)),
        'extra_items': extra_items,
        'wikelo_ingredients': parse_wikelo_ingredients(ROOT / 'data' / 'wikelo_data.json'),
        'crafting_materials': parse_crafting_materials(ROOT / 'data' / 'crafting_catalog.json'),
    }
    output.write_text(json.dumps(catalog, separators=(',', ':')), encoding='utf-8')
    return catalog


if __name__ == '__main__':
    p4k_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_P4K
    cat = build_catalog(p4k=p4k_arg)
    out = ROOT / 'data' / 'knick_knacks_catalog.json'
    print(
        f'Wrote {out} ({out.stat().st_size:,} bytes): '
        f"{len(cat['locations'])} locations, {len(cat['vehicle_crcs'])} vehicles, "
        f"{len(cat['hangar_crcs'])} hangars, {len(cat['non_item_crcs'])} non_items, "
        f"{len(cat['extra_items'])} extra_items, {len(cat['wikelo_ingredients'])} wikelo_ingredients, "
        f"{len(cat['crafting_materials'])} crafting_materials"
    )
