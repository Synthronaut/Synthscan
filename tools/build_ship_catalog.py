"""Build data/ship_catalog.json mapping earnable/buyable ships (aUEC dealerships, Wikelo Emporium, PYAM Exec Hangar) to EntityClassDefinition CRCs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_knick_knacks_catalog import DEFAULT_P4K, STARBREAKER, cig_guid_crc, load_global_ini  # noqa: E402

_EXEC_HANGAR_SHIPS = [
    (2651921316, 'Anvil F7A Hornet Mk II (PYAM Exec)', 'Anvil Aerospace', 'Fighter', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (981430424, 'Anvil F8C Lightning (PYAM Exec)', 'Anvil Aerospace', 'Fighter', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (3494349459, 'Drake Corsair (PYAM Exec)', 'Drake Interplanetary', 'Exploration', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (4155388182, 'Drake Cutlass Black (PYAM Exec)', 'Drake Interplanetary', 'Multi-Role', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (1054717367, 'Gatac Syulen (PYAM Exec)', 'Gatac Manufacture', 'Starter / Cargo', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (2002062392, 'RSI Meteor PYAM Exec', 'Roberts Space Industries', 'Combat', 'Comp-Boards 1–7 -> Executive Hangar vault reward', False),
    (3428858608, 'Mirai Guardian MX Wikelo War Special', 'Mirai', 'Combat', 'Comp-Boards 1–7 -> Executive Hangar vault reward', True),
    (1109514387, 'RSI Scorpius Stealth (PYAM Exec)', 'Roberts Space Industries', 'Fighter', 'Comp-Boards 1–7 -> Executive Hangar vault reward', True),
]

_WIKELO_CRC_OVERRIDES = {
    'aegis sabre firebird wikelo war special': 275843731,
    'aegis sabre peregrine wikelo speedy special': 2356408140,
    'anvil f7 hornet mk wikelo': 1525197528,
    'crusader c1 spirit wikelo special': 1642540745,
    'misc starlancer max wikelo work special': 2769979140,
    'mirai guardian qi wikelo special': 1142225182,
    'mirai guardian wikelo war special': 1419531993,
    'rsi scorpius wikelo sneak special': 1109514387,
    'rsi ursa medivac wikelo special': 3476742557,
    'rsi zeus mk ii cl': 2429699167,
    'rsi zeus mk ii es wikelo work special': 2482308662,
}

_DEALERSHIP_CRC_OVERRIDES = {
    'anvil c8r pisces rescue': 1525546665,
    'argo csv sm': 3532703979,
    'argo mpuv tractor': 3967469714,
    'tumbril nova': 133218683,
}

_EXCLUDED_HULL_FRAGMENTS = (
    'prisonpod', 'atcdatamanager', 'seataccess', 'component_cover', 'shieldfluff',
    'ballisticcannon', '_decoy', '_noise', '_backpack', '_module_', 'pu_ai_', 'unmanned',
    '_tutorial', '_cinematic', '_template', '_s42', '_sq42',
)


def _fetch_uex(endpoint: str) -> list[dict]:
    req = urllib.request.Request(
        f'https://api.uexcorp.space/2.0/{endpoint}',
        headers={'User-Agent': 'SynthScan/1.0'},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    return list(payload.get('data') or ())


def _vehicle_role(v: dict) -> str:
    if v.get('is_ground_vehicle'):
        return 'Ground Vehicle'
    for flag, label in (
        ('is_mining', 'Mining'),
        ('is_salvage', 'Salvage'),
        ('is_medical', 'Medical'),
        ('is_cargo', 'Cargo'),
        ('is_racing', 'Racing'),
        ('is_exploration', 'Exploration'),
        ('is_bomber', 'Bomber'),
        ('is_interdiction', 'Interdiction'),
        ('is_military', 'Combat'),
        ('is_starter', 'Starter'),
    ):
        if v.get(flag):
            return label
    return 'Ship'


def _scan_p4k_vehicle_guids(p4k: Path, gini: dict[str, str]) -> dict[str, list[tuple[int, str, str]]]:
    """Map normalized vehicle display name & short record -> [(crc, record_short, localized_name), ...]."""
    out: dict[str, list[tuple[int, str, str]]] = {}
    kk_cat = ROOT / 'data' / 'knick_knacks_catalog.json'
    if kk_cat.exists():
        data = json.loads(kk_cat.read_text(encoding='utf-8'))
        for crc_str, v in (data.get('vehicle_names') or {}).items():
            crc = int(crc_str)
            short = str(v.get('record') or '').strip()
            disp = str(v.get('name') or '').strip()
            low = short.lower()
            if not short or any(f in low for f in _EXCLUDED_HULL_FRAGMENTS):
                continue
            out.setdefault(low, []).append((crc, short, disp))
            if disp:
                nk = re.sub(r'[^a-z0-9]+', ' ', disp.lower()).strip()
                out.setdefault(nk, []).append((crc, short, disp))
        if out:
            return out
    if not STARBREAKER.exists() or not p4k.exists():
        return out
    proc = subprocess.Popen(
        [str(STARBREAKER), 'dcb', 'query', '--p4k', str(p4k), 'EntityClassDefinition'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
    )
    prefixes = (
        'AEGS_', 'ANVL_', 'ARGO_', 'BANU_', 'CNOU_', 'CRUS_', 'DRAK_', 'ESPR_',
        'GAMA_', 'GATAC_', 'GRIN_', 'KRIG_', 'MISC_', 'MRAI_', 'ORIG_', 'RSI_',
        'TMBL_', 'VNCL_', 'XIAN_',
    )
    cur_name = ''
    assert proc.stdout is not None
    for line in proc.stdout:
        if line.startswith('  "_RecordName_":'):
            m = re.search(r'"([^"]+)"\s*,?\s*$', line)
            cur_name = m.group(1) if m else ''
        elif line.startswith('  "_RecordId_":'):
            m = re.search(r'([0-9a-f-]{36})', line)
            if not m or not cur_name:
                continue
            short = cur_name.removeprefix('EntityClassDefinition.')
            low = short.lower()
            if not short.startswith(prefixes) or any(f in low for f in _EXCLUDED_HULL_FRAGMENTS):
                continue
            crc = cig_guid_crc(m.group(1))
            disp = gini.get(f'vehicle_name{low}') or gini.get(f'vehicle_name_{low}') or ''
            out.setdefault(low, []).append((crc, short, disp))
            if disp:
                nk = re.sub(r'[^a-z0-9]+', ' ', disp.lower()).strip()
                out.setdefault(nk, []).append((crc, short, disp))
    proc.wait()
    return out


def _norm_key(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def build_ship_catalog(output: Path = ROOT / 'data' / 'ship_catalog.json', p4k: Path = DEFAULT_P4K) -> dict:
    gini = load_global_ini()
    vehs = _fetch_uex('vehicles')
    prices = _fetch_uex('vehicles_purchases_prices_all')
    p4k_index = _scan_p4k_vehicle_guids(p4k, gini)

    # Index prices per UEX id_vehicle
    buy_by_vid: dict[int, list[dict]] = {}
    for pr in prices:
        vid = pr.get('id_vehicle')
        amt = int(pr.get('price_buy') or 0)
        term = str(pr.get('terminal_name') or '').strip()
        if vid and amt > 0 and term:
            buy_by_vid.setdefault(int(vid), []).append({'terminal': term, 'price': amt})

    ships_by_key: dict[str, dict] = {}
    name_to_crc: dict[str, int] = {}

    # 1. Dealership buyable vehicles from UEX
    for v in vehs:
        vid = int(v.get('id') or 0)
        offers = sorted(buy_by_vid.get(vid) or [], key=lambda x: x['price'])
        if not offers:
            continue
        uuid = str(v.get('uuid') or '').strip()
        name_full = str(v.get('name_full') or v.get('name') or '').strip()
        slug = str(v.get('slug') or '').replace('-', '_')
        nk_full = _norm_key(name_full)
        crc = _DEALERSHIP_CRC_OVERRIDES.get(nk_full, 0)
        if not crc:
            if len(uuid.replace('-', '')) == 32:
                crc = cig_guid_crc(uuid)
            elif slug in p4k_index:
                crc = p4k_index[slug][0][0]
            elif nk_full in p4k_index:
                crc = p4k_index[nk_full][0][0]
        if not crc or not name_full:
            continue
        best = offers[0]
        dealers = [o['terminal'] for o in offers]
        dealer_str = ', '.join(dict.fromkeys(dealers))
        name_to_crc[nk_full] = crc
        key = f'dealer:{crc}'
        ships_by_key[key] = {
            'crc': crc,
            'name': name_full,
            'company': str(v.get('company_name') or ''),
            'role': _vehicle_role(v),
            'channel': 'dealership',
            'channel_label': 'In-Game Dealership',
            'price_auec': int(best['price']),
            'dealer_label': dealer_str,
            'recipe': '',
            'scu': int(v.get('scu') or 0),
        }

    # 2. Executive Hangar ships
    for crc, name, comp, role, rec_str, also_wikelo in _EXEC_HANGAR_SHIPS:
        name_to_crc[_norm_key(name)] = crc
        entry = {
            'crc': crc,
            'name': name,
            'company': comp,
            'role': role,
            'channel': 'exec_hangar',
            'channel_label': 'Executive Hangar',
            'price_auec': 0,
            'dealer_label': 'PYAM-EXHANG-0-1 (Pyro)',
            'recipe': rec_str,
            'scu': 0,
        }
        if also_wikelo:
            entry['also_wikelo'] = True
        ships_by_key[f'exec:{crc}'] = entry

    # 3. Wikelo Emporium barter ships
    wpath = ROOT / 'data' / 'wikelo_data.json'
    if wpath.exists():
        wdata = json.loads(wpath.read_text(encoding='utf-8'))
        for ws in wdata.get('ships') or ():
            reward = str(ws.get('reward') or '').strip()
            # Filter out ATLS color swaps and placeholder unknowns
            if not reward or reward.startswith('[Unknown:') or reward.startswith('ATLS ') and 'Color' in reward:
                continue
            # Last semicolon piece if bundled with armor (e.g. "Most Special Wolf")
            ship_name = reward.split(';')[-1].strip()
            nk = _norm_key(ship_name)
            recipe = str(ws.get('recipe') or ws.get('cost') or '').strip()
            if nk == 'mirai guardian mx wikelo war special':
                if f'exec:{3428858608}' in ships_by_key and recipe:
                    ships_by_key[f'exec:{3428858608}']['recipe'] = f'PYAM Executive Hangar vault reward (or Wikelo: {recipe})'
                continue
            if nk == 'rsi scorpius wikelo sneak special':
                if f'exec:{1109514387}' in ships_by_key and recipe:
                    ships_by_key[f'exec:{1109514387}']['recipe'] = f'PYAM Executive Hangar vault reward (or Wikelo: {recipe})'
                continue
            crc = _WIKELO_CRC_OVERRIDES.get(nk, 0)
            if not crc:
                hits = p4k_index.get(nk)
                if hits:
                    crc = hits[0][0]
                else:
                    tokens = [t for t in nk.split() if t not in {'wikelo', 'special', 'war', 'work', 'sneak', 'savior', 'speedy', 'mod', 'aegis', 'anvil', 'argo', 'crusader', 'drake', 'esperia', 'kruger', 'misc', 'mirai', 'origin', 'rsi', 'aopoa'}]
                    for k, lst in p4k_index.items():
                        if all(t in k for t in tokens) and ('collector' in k or len(tokens) >= 2):
                            crc = lst[0][0]
                            break
            if not crc:
                base_name = re.sub(r'\s+wikelo.*$', '', ship_name, flags=re.I).strip()
                crc = name_to_crc.get(_norm_key(base_name)) or 0
            if not crc:
                continue
            mfg = ship_name.split(' ', 1)[0] if ' ' in ship_name else ''
            ships_by_key[f'wikelo:{crc}:{nk}'] = {
                'crc': crc,
                'name': ship_name,
                'company': mfg,
                'role': 'Wikelo Special',
                'channel': 'wikelo',
                'channel_label': 'Wikelo Emporium',
                'price_auec': 0,
                'dealer_label': 'Wikelo Emporium (Dasi / Selo / Kinga)',
                'recipe': recipe,
                'scu': 0,
            }

    catalog = {
        'schema': 1,
        'ships': sorted(ships_by_key.values(), key=lambda x: (x['channel'], x['name'].lower())),
    }
    output.write_text(json.dumps(catalog, separators=(',', ':')), encoding='utf-8')
    return catalog


if __name__ == '__main__':
    res = build_ship_catalog()
    out = ROOT / 'data' / 'ship_catalog.json'
    by_ch: dict[str, int] = {}
    for s in res['ships']:
        by_ch[s['channel']] = by_ch.get(s['channel'], 0) + 1
    print(f'Wrote {out} ({out.stat().st_size:,} bytes): {len(res["ships"])} earnable ships {by_ch}')
