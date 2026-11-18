"""Knick-Knacks service: aggregates spare / unmounted player inventory across stations & hangars."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import base64
import json
import re
import struct
import threading
import time

ROOT = Path(__file__).resolve().parent

_CRC32C_POLY = 0x82F63B78
_CRC32C_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ _CRC32C_POLY if (_c & 1) else (_c >> 1)
    _CRC32C_TABLE.append(_c)

_CONTAINER_TYPES = {
    'InventoryContainer', 'Container', 'Char_Armor_Backpack', 'Char_Clothing_Backpack',
    'Char_Armor_Torso', 'Char_Armor_Legs', 'Char_Clothing_Legs', 'Char_Clothing_Torso_0',
    'Char_Clothing_Torso_1',
}

_SHIP_COMPONENT_TYPES = {
    'Cooler', 'FuelTank', 'JumpDrive', 'PowerPlant', 'QuantumDrive',
    'QuantumFuelTank', 'Radar', 'Shield',
}

_SHIP_WEAPON_TYPES = {
    'Bomb', 'BombLauncher', 'Missile', 'MissileLauncher',
    'Turret', 'TurretBase', 'WeaponDefensive', 'WeaponGun', 'WeaponMount',
}

_MINING_SALVAGE_TYPES = {
    'MiningModifier', 'SalvageFillerStation', 'SalvageHead', 'SalvageModifier',
    'ToolArm', 'TowingBeam', 'TractorBeam', 'WeaponMining',
}

_STARTER_RESPAWN_NAMES = {
    'beacon undersuit white',
    'horizon helmet white',
    'medical gown',
    'hospital gown',
    'patient gown',
    'gme 338-10 medical gown',
    'gme 338-10 medical gown primrose',
    'gme 338-10 medical gown honeycomb',
    'gme 240-15 patient slippers',
    'gme 240-15 patient slippers primrose',
    'gme 240-15 patient slippers honeycomb',
    'shizhen surgical gown',
    'inmate worksuit',
    'inmate work helmet',
    'inmate workpack',
}

_ENTITLEMENT_NOISE_PREFIXES = (
    'universal_necksock',
    'fp_visor',
    'controlpanel_',
    'vehicle_screen',
    'radar_display',
    'lfsp_',
    'weapon_rack_',
    'h_dashboard_',
    'door_',
    'relay_',
    'body_01',
    'vgl_flightsuit_core',
    'vgl_flightsuit_extra',
)

_ENTITLEMENT_NOISE_SUBSTRS = (
    '_turret_lights', '_decal', 'esc_pod', 'prisonpod', 'atcdatamanager',
    'seataccess', 'component_cover', 'shieldfluff', '_decoy', '_noise',
    '_backpack', '_module_', 'ballisticcannon',
)


def crc32c_bytes(data: bytes) -> int:
    c = 0xFFFFFFFF
    for b in data:
        c = _CRC32C_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


def cig_guid_crc(guid_str: str) -> int:
    hx = str(guid_str or '').replace('-', '').strip()
    if len(hx) != 32:
        raise ValueError(f'Invalid GUID: {guid_str!r}')
    hi = int(hx[:16], 16)
    lo = int(hx[16:], 16)
    return crc32c_bytes(struct.pack('<QQ', hi, lo))


def _is_comp_board_or_key(name: str, record: str, lib_type: str) -> bool:
    low_n = name.lower()
    low_r = record.lower()
    if lib_type == 'RemovableChip':
        return True
    if any(k in low_n for k in ('comp-board', 'compboard', 'comp board', 'keycard', 'cryptokey', 'passcode disk', 'server blade', 'alignment blade', 'decryption key', 'dchs-')):
        return True
    if any(k in low_r for k in ('compboard', 'keycard', 'hackingchip', 'pyro_serverblade', 'delving_serverblade')):
        return True
    return False


class KnickKnacksCatalog:
    """Reference lookup mapping class_guid_crc -> item metadata and Location:<id> -> station."""

    def __init__(
        self,
        catalog_path: Path | None = None,
        library_path: Path | None = None,
    ) -> None:
        cpath = catalog_path or (ROOT / 'data' / 'knick_knacks_catalog.json')
        lpath = library_path or (ROOT / 'data' / 'local_game_library.json')
        cat = json.loads(cpath.read_text(encoding='utf-8')) if cpath.exists() else {}
        lib = json.loads(lpath.read_text(encoding='utf-8')) if lpath.exists() else {}

        self.locations: dict[str, dict[str, str]] = dict(cat.get('locations') or {})
        self.vehicle_crcs: set[int] = {int(c) for c in (cat.get('vehicle_crcs') or ())}
        self.vehicle_names: dict[int, dict[str, str]] = {
            int(k): v for k, v in (cat.get('vehicle_names') or {}).items() if isinstance(v, dict)
        }
        scpath = ROOT / 'data' / 'ship_catalog.json'
        scat = json.loads(scpath.read_text(encoding='utf-8')) if scpath.exists() else {}
        self.earnable_ships: list[dict] = list(scat.get('ships') or ())
        self.ship_by_crc: dict[int, dict] = {}
        for sh in self.earnable_ships:
            try:
                scrc = int(sh.get('crc') or 0)
            except (TypeError, ValueError):
                scrc = 0
            if scrc:
                self.ship_by_crc.setdefault(scrc, sh)
                if sh.get('name'):
                    self.vehicle_names.setdefault(scrc, {'name': str(sh['name']), 'record': ''})
        self.hangar_crcs: set[int] = {int(c) for c in (cat.get('hangar_crcs') or ())}
        self.non_item_crcs: set[int] = {int(c) for c in (cat.get('non_item_crcs') or ())}
        self.wikelo_ingredients: set[str] = {str(x).lower() for x in (cat.get('wikelo_ingredients') or ())}
        self.crafting_materials: set[str] = {str(x).lower() for x in (cat.get('crafting_materials') or ())}

        self.items_by_crc: dict[int, dict] = {}
        self.name_by_guid_le: dict[bytes, str] = {}
        for entry in lib.get('entries') or []:
            gid = entry.get('id')
            if not gid or len(str(gid).replace('-', '')) != 32:
                continue
            try:
                crc = cig_guid_crc(gid)
            except ValueError:
                continue
            hx = str(gid).replace('-', '').strip()
            le_bytes = struct.pack('<QQ', int(hx[:16], 16), int(hx[16:], 16))
            nm = str(entry.get('name') or '')
            if nm:
                self.name_by_guid_le.setdefault(le_bytes, nm)
            self.items_by_crc[crc] = {
                'name': nm,
                'category': str(entry.get('category') or ''),
                'type': str(entry.get('type') or ''),
                'manufacturer': str(entry.get('manufacturer') or ''),
                'size': entry.get('size'),
                'grade': entry.get('grade'),
                'record': str(entry.get('record') or ''),
                'internal': bool(entry.get('internal')),
            }
        for crc_str, extra in (cat.get('extra_items') or {}).items():
            try:
                crc = int(crc_str)
            except (TypeError, ValueError):
                continue
            if crc not in self.items_by_crc and isinstance(extra, dict):
                self.items_by_crc[crc] = {
                    'name': str(extra.get('name') or ''),
                    'category': str(extra.get('category') or 'Cargo & other'),
                    'type': str(extra.get('type') or ''),
                    'manufacturer': '',
                    'size': None,
                    'grade': None,
                    'record': str(extra.get('record') or ''),
                    'internal': False,
                }

    def resolve_inventory_location(self, inventory_id: str) -> dict[str, str]:
        parts = str(inventory_id or '').split(':')
        storage_kind = parts[1].lower() if len(parts) >= 2 else 'other'
        loc_id = parts[2] if len(parts) >= 3 else '0'
        if storage_kind == 'playerinventory':
            return {
                'inventory_id': inventory_id,
                'location_id': 'player',
                'location_name': 'Equipped on Character',
                'system': 'Character',
                'storage_kind': 'player',
            }
        loc = self.locations.get(str(loc_id))
        if loc:
            return {
                'inventory_id': inventory_id,
                'location_id': str(loc_id),
                'location_name': str(loc.get('name') or f'Location {loc_id}'),
                'system': str(loc.get('system') or ''),
                'storage_kind': storage_kind,
            }
        return {
            'inventory_id': inventory_id,
            'location_id': str(loc_id),
            'location_name': f'Location {loc_id}' if loc_id != '0' else 'Unknown Location',
            'system': '',
            'storage_kind': storage_kind,
        }

    def is_container_crc(self, crc: int) -> bool:
        if crc in self.hangar_crcs:
            return True
        meta = self.items_by_crc.get(crc)
        if not meta:
            return False
        if meta.get('type') in _CONTAINER_TYPES:
            return True
        rec = meta.get('record', '').lower()
        return 'inventorycontainer' in rec or 'backpack' in rec

    def classify_item(self, crc: int) -> dict | None:
        if crc in self.non_item_crcs or crc in self.vehicle_crcs or crc in self.hangar_crcs:
            return None
        meta = self.items_by_crc.get(crc)
        if not meta:
            return {
                'crc': crc,
                'name': f'Unknown Item ({crc})',
                'category': 'other',
                'category_label': 'Cargo & Other',
                'sub_type': '',
                'manufacturer': '',
                'size': None,
                'grade': None,
                'is_wikelo': False,
                'is_crafting': False,
                'is_comp_board': False,
                'is_ship_component': False,
            }
        if meta.get('internal'):
            return None

        name = str(meta.get('name') or '').strip()
        if not name:
            return None
        if name.lower() in _STARTER_RESPAWN_NAMES:
            return None
        lib_cat = str(meta.get('category') or '')
        lib_type = str(meta.get('type') or '')
        record = str(meta.get('record') or '')
        low_n = name.lower()
        low_r = record.lower()

        is_comp_board = _is_comp_board_or_key(name, record, lib_type)
        is_wikelo = (
            low_n in self.wikelo_ingredients
            or 'collector' in low_r
            or 'banu_favour' in low_r
            or 'wikelo' in low_n
            or 'scrip' in low_r
            or 'yormandi' in low_n
            or 'vanduul' in low_n
            or 'asdreward' in low_r
        )
        is_crafting = (
            low_n in self.crafting_materials
            or lib_cat in {'Materials & commodities', 'Raw resources'}
            or lib_type in _MINING_SALVAGE_TYPES
            or 'harvestable_mineral' in low_r
            or 'commodity_mineral' in low_r
            or 'commodity_ore' in low_r
            or '_ore_' in low_r
        )
        is_ship_component = (
            lib_type in _SHIP_COMPONENT_TYPES
            or lib_type in _SHIP_WEAPON_TYPES
            or lib_cat == 'Ship components'
        )

        # Pick clean primary bucket matching user priorities
        if is_comp_board:
            cat = 'comp_boards'
            cat_label = 'Comp Boards & Keys'
        elif is_ship_component:
            cat = 'ship_components'
            cat_label = 'Ship Components'
        elif is_crafting:
            cat = 'mining_crafting'
            cat_label = 'Mining & Crafting'
        elif is_wikelo:
            cat = 'wikelo'
            cat_label = 'Wikelo Turn-Ins'
        elif lib_cat in {'Armor & clothing', 'Weapons & ammunition', 'Paints & customization'} or lib_type in {'WeaponPersonal', 'WeaponAttachment', 'Grenade'}:
            cat = 'gear_weapons'
            cat_label = 'Paints' if lib_cat == 'Paints & customization' else 'FPS Gear & Weapons'
        else:
            cat = 'other'
            cat_label = 'Cargo & Other'

        return {
            'crc': crc,
            'name': name,
            'category': cat,
            'category_label': cat_label,
            'sub_type': lib_type or lib_cat,
            'manufacturer': str(meta.get('manufacturer') or ''),
            'size': meta.get('size'),
            'grade': meta.get('grade'),
            'is_wikelo': is_wikelo,
            'is_crafting': is_crafting,
            'is_comp_board': is_comp_board,
            'is_ship_component': is_ship_component,
        }

    def _clean_vehicle_name(self, raw: str) -> str:
        txt = str(raw or '').strip()
        if txt.upper().startswith('S-'):
            txt = txt[2:]
        txt = txt.replace('_', ' ').replace('-', ' ')
        txt = re.sub(r'\bMK\s*(\d+)\b', r'Mk \1', txt, flags=re.I)
        txt = re.sub(r'\s+', ' ', txt).strip()
        for prefix, full in (
            ('RSI ', 'RSI '),
            ('AEGS ', 'Aegis '),
            ('ANVL ', 'Anvil '),
            ('ARGO ', 'ARGO '),
            ('BANU ', 'Banu '),
            ('CNOU ', 'Consolidated Outland '),
            ('CRUS ', 'Crusader '),
            ('DRAK ', 'Drake '),
            ('ESPR ', 'Esperia '),
            ('GAMA ', 'Gatac '),
            ('GRIN ', 'Greycat '),
            ('KRIG ', 'Kruger '),
            ('MISC ', 'MISC '),
            ('MRAI ', 'Mirai '),
            ('ORIG ', 'Origin '),
            ('TMBL ', 'Tumbril '),
            ('XIAN ', 'Aopoa '),
        ):
            if txt.upper().startswith(prefix):
                txt = full + txt[len(prefix):]
                break
        for suffix in ('Collector Military', 'Collector Industrial', 'Collector Civilian'):
            if suffix in txt:
                txt = txt.replace(suffix, 'Wikelo Special')
        return txt

    def classify_entitlement(self, guid_str: str, fallback_name: str = '', sku: str = '') -> dict | None:
        raw_name = str(fallback_name or '').strip()
        low_fb = raw_name.lower()
        if (
            any(low_fb.startswith(p) for p in _ENTITLEMENT_NOISE_PREFIXES)
            or low_fb == 'player'
            or any(sub in low_fb for sub in _ENTITLEMENT_NOISE_SUBSTRS)
        ):
            return None
        crc = 0
        if guid_str and len(str(guid_str).replace('-', '').strip()) == 32:
            try:
                crc = cig_guid_crc(guid_str)
            except ValueError:
                crc = 0

        if crc and crc in self.hangar_crcs:
            return {
                'crc': crc,
                'name': raw_name or 'Personal Hangar',
                'category': 'flair',
                'category_label': 'Flair & Hangars',
                'sub_type': 'Hangar',
                'manufacturer': '',
                'size': None,
                'grade': None,
            }
        # Resolve known catalog ships FIRST before general item library
        sh_meta = self.ship_by_crc.get(crc) if crc else None
        if (crc and crc in self.vehicle_crcs) or sh_meta:
            vmeta = self.vehicle_names.get(crc) or {}
            name = str((sh_meta or {}).get('name') or vmeta.get('name') or self._clean_vehicle_name(raw_name)).strip()
            return {
                'crc': crc,
                'name': name,
                'category': 'ships',
                'category_label': 'Ships & Vehicles',
                'sub_type': str((sh_meta or {}).get('role') or 'Ship / Vehicle'),
                'manufacturer': str((sh_meta or {}).get('company') or (name.split(' ', 1)[0] if ' ' in name else '')),
                'size': None,
                'grade': None,
            }

        meta = self.items_by_crc.get(crc) if crc else None
        if meta and not meta.get('internal'):
            rec_low = str(meta.get('record') or '').lower()
            tp = str(meta.get('type') or '')
            cat_raw = str(meta.get('category') or '')
            name = str(meta.get('name') or raw_name).strip()
            if not name or name.lower() in _STARTER_RESPAWN_NAMES:
                return None
            if tp == 'Flight Blade' or '_blade_' in rec_low or 'flight blade' in name.lower():
                return {
                    'crc': crc, 'name': name, 'category': 'ship_components',
                    'category_label': 'Ship Components', 'sub_type': 'Flight Blade',
                    'manufacturer': str(meta.get('manufacturer') or ''), 'size': None, 'grade': None,
                }
            if cat_raw == 'Paints & customization':
                return {
                    'crc': crc, 'name': name, 'category': 'paints',
                    'category_label': 'Paints & Liveries', 'sub_type': tp or 'Paint',
                    'manufacturer': str(meta.get('manufacturer') or ''), 'size': None, 'grade': None,
                }
            if tp in _SHIP_COMPONENT_TYPES or tp in _SHIP_WEAPON_TYPES or cat_raw == 'Ship components':
                return {
                    'crc': crc, 'name': name, 'category': 'ship_components',
                    'category_label': 'Ship Components', 'sub_type': tp or 'Component',
                    'manufacturer': str(meta.get('manufacturer') or ''), 'size': meta.get('size'), 'grade': meta.get('grade'),
                }
            if cat_raw in {'Armor & clothing', 'Weapons & ammunition'} or tp in {'WeaponPersonal', 'WeaponAttachment', 'Grenade', 'Armor'}:
                return {
                    'crc': crc, 'name': name, 'category': 'gear_weapons',
                    'category_label': 'FPS Gear & Weapons', 'sub_type': tp or cat_raw,
                    'manufacturer': str(meta.get('manufacturer') or ''), 'size': None, 'grade': None,
                }
            return {
                'crc': crc, 'name': name, 'category': 'flair',
                'category_label': 'Flair & Hangars', 'sub_type': tp or cat_raw or 'Flair',
                'manufacturer': str(meta.get('manufacturer') or ''), 'size': None, 'grade': None,
            }

        if crc and crc in self.non_item_crcs:
            return None

        is_veh_fallback = (
            low_fb.startswith((
                'aegs_', 'anvl_', 'argo_', 'banu_', 'cnou_', 'crus_', 'drak_',
                'espr_', 'gama_', 'gatac_', 'krig_', 'misc_', 'mrai_', 'orig_', 'rsi_',
                'tmbl_', 'vncl_', 'xian_',
            ))
            and not any(tok in low_fb for tok in (
                '_paint', 'livery', '_blade', '_rack', '_lights', '_display', '_screen',
                '_door', '_turret', '_cannon', '_gatling', '_repeater', '_gun', '_rifle',
                '_pistol', '_mag', '_armor', '_undersuit', '_helmet', '_jacket', '_melee',
                '_scitem', 'bedding', 'duvet', 'pillow', 'sheet',
            ))
        )
        if is_veh_fallback:
            vmeta = self.vehicle_names.get(crc) or {}
            name = str(vmeta.get('name') or self._clean_vehicle_name(raw_name)).strip()
            return {
                'crc': crc,
                'name': name,
                'category': 'ships',
                'category_label': 'Ships & Vehicles',
                'sub_type': 'Ship / Vehicle',
                'manufacturer': name.split(' ', 1)[0] if ' ' in name else '',
                'size': None,
                'grade': None,
            }
        if not raw_name:
            return None
        name = raw_name.replace('_', ' ').strip()
        is_paint = 'paint' in low_fb or 'livery' in low_fb
        return {
            'crc': crc,
            'name': name,
            'category': 'paints' if is_paint else 'flair',
            'category_label': 'Paints & Liveries' if is_paint else 'Flair & Hangars',
            'sub_type': sku if sku and sku != 'UNDEFINED' else ('Paint' if is_paint else 'Account Item'),
            'manufacturer': '',
            'size': None,
            'grade': None,
        }


def extract_entitlement_items(
    catalog: KnickKnacksCatalog,
    entitlements: list[dict],
    snapshots: list[dict],
) -> tuple[list[dict], dict[str, int]]:
    """Filter & group permanent RSI Hangar + In-Game Persistent (LTP) account entitlements."""
    attached_urns: set[str] = set()
    for row in snapshots or ():
        sn = (row or {}).get('snapshot') or {}
        if sn.get('attach_path') and sn.get('item_urn'):
            attached_urns.add(str(sn['item_urn']))

    grouped: dict[tuple[int, str, str, str, str], dict] = {}
    for ent in entitlements or ():
        urn = str(ent.get('urn') or '')
        if urn and urn in attached_urns:
            continue
        stype = str(ent.get('source_type') or '')
        if stype == 'ENTITLEMENT_SOURCE_TYPE_PLATFORM':
            source_kind = 'rsi_hangar'
            source_label = 'RSI Hangar'
        elif stype == 'ENTITLEMENT_SOURCE_TYPE_INGAME_PERSISTENT':
            source_kind = 'ingame_ltp'
            source_label = 'In-Game Persistent (LTP)'
        else:
            continue

        status_raw = str(ent.get('status') or '')
        if status_raw in {'ENTITLEMENT_STATUS_REVOKED', 'ENTITLEMENT_STATUS_FAILED'}:
            continue
        status_label = 'In Hangar (Unclaimed)' if status_raw in {'ENTITLEMENT_STATUS_PACKAGED', 'ENTITLEMENT_STATUS_UNDELIVERED'} else 'Delivered'

        md = ent.get('metadata') or {}
        raw_md_name = str(md.get('name') or '').strip()
        raw_sku = str(md.get('source_sku') or '').strip()
        info = catalog.classify_entitlement(
            str(ent.get('entity_class_guid') or ''),
            raw_md_name,
            raw_sku,
        )
        if not info:
            continue
        if info.get('category') == 'ships':
            if status_raw in {'ENTITLEMENT_STATUS_PACKAGED', 'ENTITLEMENT_STATUS_UNDELIVERED'} or raw_md_name.lower().startswith('s-'):
                continue
            if source_kind == 'rsi_hangar' and raw_sku.lower() in {'s-misc-starfarer-tanker'}:
                continue

        qty = max(1, int(md.get('stack_size') or 1))
        key = (int(info['crc']), str(info['name']), source_kind, status_label, str(info['category']))
        created_at = str(ent.get('created_at') or '')
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {
                **info,
                'source_kind': source_kind,
                'source_label': source_label,
                'status_label': status_label,
                'real_money': bool(md.get('real_money')),
                'created_at': created_at,
                'quantity': qty,
            }
        else:
            existing['quantity'] += qty
            if created_at and (not existing['created_at'] or created_at > existing['created_at']):
                existing['created_at'] = created_at

    items = list(grouped.values())
    items.sort(key=lambda r: (0 if r['source_kind'] == 'rsi_hangar' else 1, -r['quantity'], r['name'].lower()))
    counts: dict[str, int] = {
        'all': 0,
        'rsi_hangar': 0,
        'ingame_ltp': 0,
        'ships': 0,
        'paints': 0,
        'ship_components': 0,
        'gear_weapons': 0,
        'flair': 0,
    }
    for row in items:
        q = int(row['quantity'])
        counts['all'] += q
        counts[row['source_kind']] += q
        if row['category'] in counts:
            counts[row['category']] += q
    return items, counts


_EXEC_MILITARY_CRC_TO_BASE = {
    2258173790: 2651921316,
    349290720: 981430424,
    2406305955: 3494349459,
    3572361305: 4155388182,
    272666220: 1054717367,
}


def build_fleet_summary(
    catalog: KnickKnacksCatalog,
    account_items: list[dict],
) -> tuple[list[dict], dict[str, int]]:
    """Build combined owned (in-game earned + RSI pledge) and unowned earnable ship directory."""
    owned_by_key: dict[tuple[int, str], dict] = {}
    owned_crcs: set[int] = set()
    for row in account_items or ():
        if row.get('category') != 'ships':
            continue
        raw_crc = int(row.get('crc') or 0)
        crc = _EXEC_MILITARY_CRC_TO_BASE.get(raw_crc, raw_crc)
        if crc:
            owned_crcs.add(crc)
        if raw_crc:
            owned_crcs.add(raw_crc)
        ownership = 'pledged' if row.get('source_kind') == 'rsi_hangar' else 'ingame_earned'
        cat_ship = catalog.ship_by_crc.get(crc) or catalog.ship_by_crc.get(raw_crc) or {}
        ship_name = str(cat_ship.get('name') or row.get('name') or '').strip()
        low_name = ship_name.lower()
        if cat_ship:
            ch = str(cat_ship.get('channel') or 'dealership')
            ch_label = str(cat_ship.get('channel_label') or 'In-Game Dealership')
            dealer = str(cat_ship.get('dealer_label') or '')
        elif 'pyam' in low_name or 'exec' in low_name:
            ch = 'exec_hangar'
            ch_label = 'Executive Hangar'
            dealer = 'PYAM-EXHANG-0-1 (Pyro)'
        elif 'wikelo' in low_name:
            ch = 'wikelo'
            ch_label = 'Wikelo Emporium'
            dealer = 'Wikelo Emporium (Dasi / Selo / Kinga)'
        elif 'teach' in low_name:
            ch = 'dealership'
            ch_label = 'In-Game Dealership'
            dealer = "Teach's Levski"
        else:
            ch = 'dealership' if ownership == 'ingame_earned' else 'rsi_hangar'
            ch_label = 'In-Game Dealership' if ownership == 'ingame_earned' else 'RSI Hangar'
            dealer = 'RSI Hangar' if ownership == 'pledged' else ''

        key = (crc, ownership)
        existing = owned_by_key.get(key)
        qty = int(row.get('quantity') or 1)
        if existing is None:
            entry = {
                'crc': crc,
                'name': ship_name,
                'company': str(cat_ship.get('company') or row.get('manufacturer') or ''),
                'role': str(cat_ship.get('role') or row.get('sub_type') or 'Ship'),
                'owned': True,
                'ownership': ownership,
                'ownership_label': 'RSI Hangar (Pledged)' if ownership == 'pledged' else 'Earned In-Game',
                'channel': ch,
                'channel_label': ch_label,
                'price_auec': int(cat_ship.get('price_auec') or 0),
                'dealer_label': dealer,
                'recipe': str(cat_ship.get('recipe') or ''),
                'scu': int(cat_ship.get('scu') or 0),
                'created_at': str(row.get('created_at') or ''),
                'quantity': qty,
            }
            if cat_ship.get('also_wikelo'):
                entry['also_wikelo'] = True
            owned_by_key[key] = entry
        else:
            existing['quantity'] += qty

    fleet: list[dict] = list(owned_by_key.values())
    for cat_ship in catalog.earnable_ships:
        crc = int(cat_ship.get('crc') or 0)
        if not crc or crc in owned_crcs:
            continue
        entry = {
            'crc': crc,
            'name': str(cat_ship.get('name') or '').strip(),
            'company': str(cat_ship.get('company') or ''),
            'role': str(cat_ship.get('role') or 'Ship'),
            'owned': False,
            'ownership': 'unowned',
            'ownership_label': 'Not Owned (Earnable)',
            'channel': str(cat_ship.get('channel') or 'dealership'),
            'channel_label': str(cat_ship.get('channel_label') or 'In-Game Dealership'),
            'price_auec': int(cat_ship.get('price_auec') or 0),
            'dealer_label': str(cat_ship.get('dealer_label') or ''),
            'recipe': str(cat_ship.get('recipe') or ''),
            'scu': int(cat_ship.get('scu') or 0),
            'quantity': 0,
        }
        if cat_ship.get('also_wikelo'):
            entry['also_wikelo'] = True
        fleet.append(entry)

    order_rank = {'ingame_earned': 0, 'pledged': 1, 'unowned': 2}
    fleet.sort(key=lambda r: (order_rank.get(r['ownership'], 9), r['name'].lower()))
    counts = {
        'all': len(fleet),
        'ingame_earned': sum(1 for r in fleet if r['ownership'] == 'ingame_earned'),
        'pledged': sum(1 for r in fleet if r['ownership'] == 'pledged'),
        'unowned': sum(1 for r in fleet if not r['owned']),
        'dealership': sum(1 for r in fleet if r['channel'] == 'dealership'),
        'wikelo': sum(1 for r in fleet if r['channel'] == 'wikelo' or r.get('also_wikelo')),
        'exec_hangar': sum(1 for r in fleet if r['channel'] == 'exec_hangar'),
    }
    return fleet, counts


_SNAPSHOT_VAR_RESOURCE = 4185637390
_SNAPSHOT_VAR_CRAFTED = 2174272695


def _decode_entity_snapshot_meta(catalog: KnickKnacksCatalog, variables: list[dict] | None) -> dict:
    """Decode crafting status/quality and material quality/uSCU from EntitySnapshot variables."""
    meta: dict = {}
    for var in variables or ():
        if not isinstance(var, dict):
            continue
        try:
            nc = int(var.get('name_crc') or 0)
        except (TypeError, ValueError):
            continue
        b64 = var.get('snapshot')
        if not isinstance(b64, str) or not b64:
            continue
        try:
            raw = base64.b64decode(b64)
        except Exception:
            continue
        if nc == _SNAPSHOT_VAR_RESOURCE and len(raw) == 19 and raw[0] == 1:
            _, _, quality, uscu_per_unit, _ = struct.unpack('<BIHQI', raw)
            if 0 <= quality <= 1000:
                meta['mat_quality'] = int(quality)
                meta['uscu_per_unit'] = int(uscu_per_unit)
        elif nc == _SNAPSHOT_VAR_CRAFTED and len(raw) >= 2:
            ing_cnt = struct.unpack_from('<H', raw, 0)[0]
            if ing_cnt > 0 and len(raw) >= 2 + 27 * ing_cnt:
                ings: list[dict] = []
                valid = True
                for i in range(ing_cnt):
                    off = 2 + 27 * i
                    b16 = raw[off:off + 16]
                    q, amt, _ = struct.unpack_from('<HQB', raw, off + 16)
                    if q > 1000:
                        valid = False
                        break
                    mat_name = catalog.name_by_guid_le.get(b16) or f'Material {b16[:4].hex()}'
                    ings.append({'name': mat_name, 'quality': int(q), 'amount': int(amt)})
                if valid and ings:
                    meta['is_crafted'] = True
                    meta['crafted_quality'] = int(round(sum(x['quality'] for x in ings) / len(ings)))
                    meta['crafted_ingredients'] = ings
    return meta


def extract_inventory_items(
    catalog: KnickKnacksCatalog,
    inventory_id: str,
    nodes: list[dict],
    edges: list[dict],
    snapshots: list[dict] | None = None,
) -> tuple[list[dict], int]:
    """Walk one inventory graph and return (item_rows, ship_mounted_excluded_count).

    Ship/vehicle trees (`catalog.vehicle_crcs`) are excluded from spare items and tallied in
    `ship_mounted_excluded_count`. Loose items inside station storage, persistent hangars,
    or storage crates/backpacks are preserved with accurate quantities (`stack_size`) plus
    material quality/uSCU and crafted-item telemetry when EntitySnapshots are supplied.
    """
    loc = catalog.resolve_inventory_location(inventory_id)
    if loc['storage_kind'] == 'entitlement':
        return [], 0

    snaps_by_geid: dict[str, list[dict]] = {}
    for sn in snapshots or ():
        if isinstance(sn, dict) and sn.get('entity_id'):
            snaps_by_geid[str(sn['entity_id'])] = sn.get('variables') or []

    by_geid: dict[str, dict] = {}
    for nd in nodes:
        ep = (nd.get('properties') or {}).get('entity_properties') or {}
        g = str(ep.get('geid') or '')
        if g:
            by_geid[g] = ep

    in_children: dict[str, list[tuple[str, str]]] = {}
    root_geids: list[str] = []
    seen_roots: set[str] = set()
    for edge in edges:
        et = str(edge.get('type') or '')
        start_id = str((edge.get('start') or {}).get('entity_id') or '')
        end = edge.get('end') or {}
        if not start_id:
            continue
        if et == 'ENTITY_EDGE_TYPE_STOWED_IN' and end.get('type') == 'NODE_TYPE_INVENTORY':
            if start_id not in seen_roots:
                seen_roots.add(start_id)
                root_geids.append(start_id)
        elif end.get('type') == 'NODE_TYPE_ENTITY':
            parent_id = str(end.get('entity_id') or '')
            if parent_id:
                in_children.setdefault(parent_id, []).append((start_id, et))

    items: list[dict] = []
    mounted_count = 0

    def count_vehicle_subtree(root_id: str) -> int:
        cnt = 0
        stack = [root_id]
        visited: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            if cur != root_id:
                ep = by_geid.get(cur)
                if ep:
                    crc = int(ep.get('class_guid_crc') or 0)
                    if crc not in catalog.non_item_crcs and crc not in catalog.vehicle_crcs:
                        cnt += max(1, int(ep.get('stack_size') or 1))
            for ch_id, _ in in_children.get(cur, ()):
                stack.append(ch_id)
        return cnt

    def emit_item(geid: str, ep: dict, container_label: str, mounted: bool = False) -> None:
        crc = int(ep.get('class_guid_crc') or 0)
        info = catalog.classify_item(crc)
        if not info:
            return
        qty = max(1, int(ep.get('stack_size') or 1))
        smeta = _decode_entity_snapshot_meta(catalog, snaps_by_geid.get(geid))
        items.append({
            **info,
            'geid': geid,
            'quantity': qty,
            'inventory_id': inventory_id,
            'location_id': loc['location_id'],
            'location_name': loc['location_name'],
            'system': loc['system'],
            'storage_kind': loc['storage_kind'],
            'container': container_label,
            'mounted': mounted,
            'is_crafted': bool(smeta.get('is_crafted')),
            'crafted_quality': smeta.get('crafted_quality'),
            'crafted_ingredients': smeta.get('crafted_ingredients') or [],
            'mat_quality': smeta.get('mat_quality'),
            'uscu_per_unit': smeta.get('uscu_per_unit'),
            'is_cargo_scu': str(info.get('sub_type') or '') == 'Cargo',
        })

    # BFS over non-vehicle trees starting from inventory roots
    for r_id in root_geids:
        ep = by_geid.get(r_id)
        if not ep:
            continue
        crc = int(ep.get('class_guid_crc') or 0)
        if crc in catalog.vehicle_crcs:
            mounted_count += count_vehicle_subtree(r_id)
            continue

        if crc in catalog.hangar_crcs:
            base_container = 'Persistent Hangar'
            is_hangar = True
        else:
            is_hangar = False
            base_container = 'Character' if loc['storage_kind'] == 'player' else 'Local Storage'
            if loc['storage_kind'] != 'player':
                emit_item(r_id, ep, base_container, mounted=False)
            else:
                # Equipped on character — exclude from spare storage totals, track as mounted/equipped
                mounted_count += max(1, int(ep.get('stack_size') or 1))

        # Walk nested children: crates, backpacks, armor pockets, hangar floor items
        stack: list[tuple[str, int, str]] = []
        r_meta = catalog.items_by_crc.get(crc) or {}
        r_name = str(r_meta.get('name') or '')
        can_nest_attach = is_hangar or catalog.is_container_crc(crc)
        for ch_id, edge_type in in_children.get(r_id, ()):
            if edge_type == 'ENTITY_EDGE_TYPE_STOWED_IN' or can_nest_attach:
                lbl = 'Persistent Hangar' if is_hangar else (f'In {r_name}' if r_name else base_container)
                stack.append((ch_id, crc, lbl))

        visited: set[str] = {r_id}
        while stack:
            cur_id, _, cur_label = stack.pop()
            if cur_id in visited:
                continue
            visited.add(cur_id)
            c_ep = by_geid.get(cur_id)
            if not c_ep:
                continue
            c_crc = int(c_ep.get('class_guid_crc') or 0)
            if c_crc in catalog.vehicle_crcs:
                mounted_count += count_vehicle_subtree(cur_id)
                continue
            if loc['storage_kind'] != 'player':
                emit_item(cur_id, c_ep, cur_label, mounted=False)
            else:
                mounted_count += max(1, int(c_ep.get('stack_size') or 1))

            c_meta = catalog.items_by_crc.get(c_crc) or {}
            c_name = str(c_meta.get('name') or '')
            allow_attach = catalog.is_container_crc(c_crc)
            for nxt_id, edge_type in in_children.get(cur_id, ()):
                if edge_type == 'ENTITY_EDGE_TYPE_STOWED_IN' or allow_attach:
                    nxt_label = f'In {c_name}' if (c_name and catalog.is_container_crc(c_crc)) else cur_label
                    stack.append((nxt_id, c_crc, nxt_label))

    return items, mounted_count


def aggregate_items(raw_items: list[dict]) -> list[dict]:
    """Group identical items sitting in the same location & container into summed rows, preserving crafted & material quality tiers."""
    grouped: dict[tuple, dict] = {}
    for row in raw_items:
        is_crafted = bool(row.get('is_crafted'))
        craft_sig = (
            tuple((str(x.get('name') or ''), int(x.get('quality') or 0), int(x.get('amount') or 0))
                  for x in (row.get('crafted_ingredients') or ()))
            if is_crafted
            else ()
        )
        key = (
            int(row['crc']),
            str(row['location_id']),
            str(row['storage_kind']),
            str(row['container']),
            is_crafted,
            craft_sig,
        )
        qty = int(row['quantity'])
        mq = row.get('mat_quality')
        uscu_unit = row.get('uscu_per_unit')
        existing = grouped.get(key)
        if existing is None:
            existing = {
                'crc': int(row['crc']),
                'name': row['name'],
                'category': row['category'],
                'category_label': row['category_label'],
                'sub_type': row['sub_type'],
                'manufacturer': row['manufacturer'],
                'size': row['size'],
                'grade': row['grade'],
                'is_wikelo': bool(row['is_wikelo']),
                'is_crafting': bool(row['is_crafting']),
                'is_comp_board': bool(row['is_comp_board']),
                'is_ship_component': bool(row['is_ship_component']),
                'is_crafted': is_crafted,
                'crafted_quality': row.get('crafted_quality'),
                'crafted_ingredients': list(row.get('crafted_ingredients') or ()),
                'is_cargo_scu': bool(row.get('is_cargo_scu')),
                'location_id': row['location_id'],
                'location_name': row['location_name'],
                'system': row['system'],
                'storage_kind': row['storage_kind'],
                'container': row['container'],
                'quantity': qty,
                '_tier_map': {},
            }
            grouped[key] = existing
        else:
            existing['quantity'] += qty

        if mq is not None and uscu_unit is not None:
            q_int = int(mq)
            lot_uscu = qty * int(uscu_unit)
            tier = existing['_tier_map'].get(q_int)
            if tier is None:
                existing['_tier_map'][q_int] = {'quality': q_int, 'units': qty, 'uscu': lot_uscu}
            else:
                tier['units'] += qty
                tier['uscu'] += lot_uscu

    out: list[dict] = []
    for entry in grouped.values():
        tier_map = entry.pop('_tier_map', {})
        if tier_map:
            tiers = sorted(tier_map.values(), key=lambda t: (-t['quality'], -t['uscu']))
            for t in tiers:
                t['scu'] = round(t['uscu'] / 1_000_000.0, 4)
            total_uscu = sum(t['uscu'] for t in tiers)
            entry['quality_tiers'] = tiers
            entry['total_uscu'] = total_uscu
            entry['total_scu'] = round(total_uscu / 1_000_000.0, 4)
            entry['max_quality'] = tiers[0]['quality']
            entry['min_quality'] = tiers[-1]['quality']
        else:
            entry['quality_tiers'] = []
            entry['total_uscu'] = 0
            entry['total_scu'] = 0.0
            entry['max_quality'] = None
            entry['min_quality'] = None
        out.append(entry)

    out.sort(key=lambda r: (-r['quantity'], r['name'].lower(), r['location_name'].lower()))
    return out


class KnickKnacksService:
    """Fetches and caches read-only live inventory snapshots for the signed-in account."""

    def __init__(self, directory: Path | str, catalog: KnickKnacksCatalog | None = None) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog or KnickKnacksCatalog()
        self.state_path = self.directory / 'knick_knacks_state.json'
        self._lock = threading.Lock()
        self._syncing = False
        self._last_sync = 0.0
        self.state = self._load_cached_state()

    def _load_cached_state(self) -> dict:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding='utf-8'))
                if isinstance(data, dict) and isinstance(data.get('items'), list):
                    return data
            except (OSError, ValueError):
                pass
        return self._empty_state('idle', 'Open SynthScan while signed in to sync your spare items.')

    def _empty_state(self, status: str, message: str) -> dict:
        return {
            'schema': 1,
            'status': status,
            'message': message,
            'syncing': False,
            'updated_at': 0,
            'mounted_excluded_count': 0,
            'total_quantity': 0,
            'unique_items': 0,
            'locations': [],
            'category_counts': {},
            'items': [],
            'account_counts': {},
            'account_items': [],
            'ship_counts': {},
            'ships': [],
        }

    def publish(self, state: dict | None = None) -> None:
        from telemetry_ipc import publish_json
        with self._lock:
            payload = dict(state if state is not None else self.state)
            payload['syncing'] = self._syncing
            self.state = payload
        publish_json(self.state_path, payload)

    def _query_inventory(self, acct, own_geid: str, inventory_id: str) -> tuple[list[dict], list[dict], list[dict]]:
        from google.protobuf.json_format import MessageToDict
        nodes: list[dict] = []
        edges: list[dict] = []
        snapshots: list[dict] = []
        after = ''
        while True:
            rq = acct.message('sc.external.services.entitygraph.v1.EntityQueryRequest')
            rq.body.scope.type = 2
            rq.body.query.inventory_id = inventory_id
            rq.body.query.projection.tree.enabled = True
            rq.body.query.projection.outgoing_edges = True
            rq.body.query.projection.snapshots = True
            pf = rq.body.query.filter.property_filter
            pf.property = 'owner_id'
            pf.operator = 5
            pf.values.add().string_value = own_geid
            rq.body.query.pagination.first = 200
            if after:
                rq.body.query.pagination.after = after
            res = acct.read('entitygraph', 'EntityGraphService', 'EntityQuery', rq)
            d = MessageToDict(res, preserving_proto_field_name=True)
            body = d.get('body') or {}
            graph = body.get('results') or {}
            nodes.extend(graph.get('nodes') or ())
            edges.extend(graph.get('edges') or ())
            snapshots.extend(body.get('snapshots') or ())
            pi = body.get('page_info') or {}
            if not pi.get('has_next_page') or not pi.get('end_cursor'):
                break
            after = str(pi['end_cursor'])
        return nodes, edges, snapshots

    def _query_entitlements(self, acct) -> tuple[list[dict], list[dict]]:
        from google.protobuf.json_format import MessageToDict
        ents: list[dict] = []
        snaps: list[dict] = []
        try:
            req_e = acct.message('sc.external.services.entitlement.v2.QueryEntitlementsStreamRequest')
            for chunk in acct.read_stream('entitlement', 'ExternalEntitlementService', 'QueryEntitlementsStream', req_e):
                d = MessageToDict(chunk, preserving_proto_field_name=True)
                ents.extend(d.get('results') or ())
            req_s = acct.message('sc.external.services.entitlement.v2.QuerySnapshotsWithEntitlementsStreamRequest')
            for chunk in acct.read_stream('entitlement', 'ExternalEntitlementService', 'QuerySnapshotsWithEntitlementsStream', req_s):
                d = MessageToDict(chunk, preserving_proto_field_name=True)
                snaps.extend(d.get('results') or ())
        except Exception:
            return [], []
        return ents, snaps

    def refresh_sync(self) -> dict:
        from google.protobuf.json_format import MessageToDict
        from game_account import OwnAccount

        acct = OwnAccount()
        ent_raw: list[dict] = []
        snap_raw: list[dict] = []
        try:
            own_geid = acct.subject.rsplit(':', 1)[-1]
            req = acct.message('sc.external.services.entitygraph.v1.GetInventoriesRequest')
            req.body.owner_id = own_geid
            invs_resp = acct.read('entitygraph', 'EntityGraphService', 'GetInventories', req)
            invs_dict = MessageToDict(invs_resp, preserving_proto_field_name=True)
            inv_ids = [
                str((inv.get('properties') or {}).get('inventory_properties', {}).get('id') or '')
                for inv in ((invs_dict.get('body') or {}).get('inventories') or ())
            ]
            inv_ids = [i for i in inv_ids if i and ':Entitlement:' not in i]

            all_raw: list[dict] = []
            mounted_total = 0
            with ThreadPoolExecutor(max_workers=5) as pool:
                ent_fut = pool.submit(self._query_entitlements, acct)
                futs = {pool.submit(self._query_inventory, acct, own_geid, iid): iid for iid in inv_ids}
                for fut in as_completed(futs):
                    iid = futs[fut]
                    nodes, edges, snaps = fut.result()
                    rows, m_cnt = extract_inventory_items(self.catalog, iid, nodes, edges, snaps)
                    all_raw.extend(rows)
                    mounted_total += m_cnt
                ent_raw, snap_raw = ent_fut.result()
        finally:
            acct.close()

        items = aggregate_items(all_raw)
        account_items, account_counts = extract_entitlement_items(self.catalog, ent_raw, snap_raw)
        ships, ship_counts = build_fleet_summary(self.catalog, account_items)
        loc_map: dict[str, dict] = {}
        cat_counts: dict[str, int] = {
            'all': 0,
            'crafted': 0,
            'ship_components': 0,
            'mining_crafting': 0,
            'wikelo': 0,
            'comp_boards': 0,
            'gear_weapons': 0,
            'other': 0,
        }
        total_qty = 0
        for row in items:
            qty = int(row['quantity'])
            total_qty += qty
            cat_counts['all'] += qty
            c = row['category']
            if c in cat_counts:
                cat_counts[c] += qty
            if row.get('is_crafted'):
                cat_counts['crafted'] += qty
            if row.get('is_wikelo') and c != 'wikelo':
                cat_counts['wikelo'] += qty
            if row.get('is_crafting') and c != 'mining_crafting':
                cat_counts['mining_crafting'] += qty
            if row.get('is_comp_board') and c != 'comp_boards':
                cat_counts['comp_boards'] += qty

            lid = str(row['location_id'])
            entry = loc_map.setdefault(lid, {
                'id': lid,
                'name': row['location_name'],
                'system': row['system'],
                'unique': 0,
                'quantity': 0,
            })
            entry['unique'] += 1
            entry['quantity'] += qty

        locs = sorted(loc_map.values(), key=lambda x: (-x['quantity'], x['name'].lower()))
        now_ts = int(time.time())
        return {
            'schema': 1,
            'status': 'ok',
            'message': f'{len(items):,} spare stacks across {len(locs)} locations · {mounted_total:,} ship/equipped items excluded',
            'syncing': False,
            'updated_at': now_ts,
            'mounted_excluded_count': mounted_total,
            'total_quantity': total_qty,
            'unique_items': len(items),
            'locations': locs,
            'category_counts': cat_counts,
            'items': items,
            'account_counts': account_counts,
            'account_items': account_items,
            'ship_counts': ship_counts,
            'ships': ships,
        }


class KnickKnacksRunner:
    """Background non-blocking runner plugged into FinderServices extras."""

    def __init__(self, directory: Path | str, owner: int = 0) -> None:
        self.directory = Path(directory)
        self.owner = owner
        self.service = KnickKnacksService(self.directory)
        self.commands_dir = self.directory / 'knick_knacks_commands'
        self.due = 0.0
        self._thread: threading.Thread | None = None
        self.service.publish()

    def _consume_commands(self) -> bool:
        if not self.commands_dir.exists():
            return False
        requested = False
        for path in sorted(self.commands_dir.glob('*.json')):
            try:
                cmd = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(cmd, dict) and cmd.get('action') == 'knick_knacks_refresh':
                    requested = True
            except (OSError, ValueError):
                pass
            path.unlink(missing_ok=True)
        return requested

    def _run_refresh(self) -> None:
        try:
            next_state = self.service.refresh_sync()
        except Exception as exc:
            with self.service._lock:
                self.service._syncing = False
                prev = dict(self.service.state)
                prev['status'] = 'offline' if 'expired' in str(exc).lower() or 'unavailable' in str(exc).lower() else 'error'
                prev['message'] = f'Waiting for active Star Citizen session ({exc})'
                prev['syncing'] = False
            self.service.publish(prev)
            return
        with self.service._lock:
            self.service._syncing = False
            self.service._last_sync = time.time()
        self.service.publish(next_state)

    def tick(self, current_patch: str = '') -> None:
        force = self._consume_commands()
        now = time.time()
        if self._thread and self._thread.is_alive():
            if force:
                self.service.publish()
            return
        if not force and now < self.due:
            return
        self.due = now + 300.0
        with self.service._lock:
            if self.service._syncing:
                return
            self.service._syncing = True
        self.service.publish()
        self._thread = threading.Thread(target=self._run_refresh, name='KnickKnacksSync', daemon=True)
        self._thread.start()

    def close(self) -> None:
        pass
