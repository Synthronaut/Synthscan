"""Exact SynthStrings HUD labels; never rewrite mission prose or item identities."""
import json
from pathlib import Path

SHORT_LABELS = {
    'actor_species_creature_kopion': '<EM3>Kopion</EM3>',
    'actor_species_creature_kopion_cave': '<EM3>Cave Kopion</EM3>',
    'actor_species_creature_kopion_forest': '<EM3>Forest Kopion</EM3>',
    'actor_species_creature_kopion_irradiated': '<EM3>Irradiated Kopion</EM3>',
    'actor_species_creature_kopion_savannah': '<EM3>Savannah Kopion</EM3>',
    'actor_species_creature_kopion_tundra': '<EM3>Tundra Kopion</EM3>',
    'actor_species_creature_marok': '<EM3>Marok</EM3>',
    'actor_species_creature_quazigrazer': '<EM3>QzG</EM3>',
    'actor_species_creature_quazigrazer_boreal': '<EM3>QzG</EM3>',
    'actor_species_creature_quazigrazer_desert': '<EM3>QzG</EM3>',
    'actor_species_creature_quazigrazer_grassland': '<EM3>QzG</EM3>',
    'actor_species_creature_quazigrazer_jungle': '<EM3>QzG</EM3>',
    'actor_species_creature_quazigrazer_tundra': '<EM3>QzG</EM3>',
    'actor_species_creature_valakkar': '<EM3>Valakkar (Adult)</EM3>',
    'actor_species_creature_valakkar_apex_irradiated': '<EM3>Irradiated Valakkar (Apex)</EM3>',
    'actor_species_creature_valakkar_irradiated': '<EM3>Irradiated Valakkar (Adult)</EM3>',
    'actor_species_creature_valakkar_juvenile': '<EM3>Vlk Jr</EM3>',
    'actor_species_creature_valakkar_juvenile_irradiated': '<EM3>Irr Vlk Jr</EM3>',
    'actor_species_creature_yormandi': '<EM3>Yormandi</EM3>',
    'harvestable_armillaria': '<EM3>BLU</EM3>',
    'hud_mining_asteroid_name_1': 'E-Type',
    'hud_mining_asteroid_name_2': 'M-Type',
    'hud_mining_asteroid_name_3': 'P-Type',
    'hud_mining_asteroid_name_4': 'Q-Type',
    'hud_mining_asteroid_name_5': 'C-Type',
    'hud_mining_asteroid_name_6': 'S-Type',
    'hud_mining_asteroid_name_7': 'I-Type',
    'hud_mining_fps_rock_name_1': 'APH',
    'hud_mining_fps_rock_name_2': 'DOL',
    'hud_mining_fps_rock_name_3': 'HAD',
    'hud_mining_rock_name_1': 'SHAL',
    'hud_mining_rock_name_2': 'GRAN',
    'hud_mining_rock_name_3': 'IGN',
    'hud_mining_rock_name_4': 'OBS',
    'hud_mining_rock_name_5': 'GNEI',
    'hud_mining_rock_name_6': 'QRTZ',
    'hud_mining_rock_name_7': 'FELS',
    'hud_mining_rock_name_8': 'ATAC',
    'hud_mining_rock_name_9': 'QUAN',
    'hud_mining_scanning_depositcomposition': 'Comp.',
    'hud_mining_scanning_instability': 'Inst:',
    'hud_mining_scanning_resistance': 'Res:',
    'hud_mining_scanning_scanprogress': 'Progress',
    'hud_mining_scanning_scanresults': 'Results',
    'hud_mining_scanning_signalstrength': 'Signal Str.',
    'hud_scanning_cat_harvestables': 'Harv',
    'items_commodities_agricium': 'AGR',
    'items_commodities_agricium_ore': 'AGR',
    'items_commodities_altruciatoxin': '<EM3>[!]</EM3> Altruciatoxin',
    'items_commodities_altruciatoxin_unprocessed': '<EM3>[!]</EM3> Revenant Tree Pollen',
    'items_commodities_aluminum': 'ALUM',
    'items_commodities_aluminum_ore': 'ALUM',
    'items_commodities_amiantpod': '<EM3>Pod</EM3>',
    'items_commodities_amioshiplague': '<EM3>AMI</EM3>',
    'items_commodities_aphorite': 'APH',
    'items_commodities_aphorite_raw': 'APH',
    'items_commodities_aslarite': 'ASL',
    'items_commodities_aslarite_raw': 'ASL',
    'items_commodities_beradom': 'BERA',
    'items_commodities_beradom_raw': 'BERA',
    'items_commodities_beryl': 'BER',
    'items_commodities_beryl_raw': 'BER',
    'items_commodities_bexalite': 'BEX',
    'items_commodities_bexalite_raw': 'BEX',
    'items_commodities_borase': 'BOR',
    'items_commodities_borase_ore': 'BOR',
    'items_commodities_carinite': 'CAR',
    'items_commodities_carinite_pure': 'CAR',
    'items_commodities_carinite_raw': 'CAR',
    'items_commodities_copper': 'COP',
    'items_commodities_copper_ore': 'COP',
    'items_commodities_corundum': 'COR',
    'items_commodities_corundum_raw': 'COR',
    'items_commodities_decaripod': '<EM3>Decari Pod</EM3>',
    'items_commodities_degnousroot': '<EM3>DEG</EM3>',
    'items_commodities_diamond': 'DIAM',
    'items_commodities_diamond_raw': 'DIAM',
    'items_commodities_dolivine': 'DOL',
    'items_commodities_dolivine_raw': 'DOL',
    'items_commodities_etam': "<EM3>[!]</EM3> E'tam",
    'items_commodities_feynmaline': 'FEYN',
    'items_commodities_feynmaline_raw': 'FEYN',
    'items_commodities_flareweedstalk': '<EM3>Stock</EM3>',
    'items_commodities_fotiascrub': '<EM3>Fotia Seedpod</EM3>',
    'items_commodities_gaspingweevileggs': '<EM3>[!]</EM3> Gasping Weevil Eggs',
    'items_commodities_glacosite': 'GLAC',
    'items_commodities_glacosite_raw': 'GLAC',
    'items_commodities_gold': 'GLD',
    'items_commodities_gold_ore': 'GLD',
    'items_commodities_goldenmedmon': '<EM3>MED</EM3>',
    'items_commodities_hadanite': 'HAD',
    'items_commodities_hadanite_raw': 'HAD',
    'items_commodities_heartofthewoods': '<EM3>Heart of the Woods</EM3>',
    'items_commodities_hephaestanite': 'HEPH',
    'items_commodities_hephaestanite_raw': 'HEPH',
    'items_commodities_inert_materials': 'INERT',
    'items_commodities_iron': 'IRON',
    'items_commodities_iron_ore': 'IRON',
    'items_commodities_jaclium': 'JAC',
    'items_commodities_jaclium_ore': 'JAC',
    'items_commodities_jahlium': 'JAH',
    'items_commodities_janalite': 'JAN',
    'items_commodities_janalite_raw': 'JAN',
    'items_commodities_laranite': 'LAR',
    'items_commodities_laranite_raw': 'LAR',
    'items_commodities_lindinium': 'LIND',
    'items_commodities_lindinium_ore': 'LIND',
    'items_commodities_maze': '<EM3>[!]</EM3> Maze',
    'items_commodities_neon': '<EM3>[!]</EM3> Neon',
    'items_commodities_ouratite': 'OUR',
    'items_commodities_pingala': '<EM3>Pingala Seeds</EM3>',
    'items_commodities_pitambu': '<EM3>PIT</EM3>',
    'items_commodities_prota': '<EM3>PRO</EM3>',
    'items_commodities_quantainium': 'QUAN',
    'items_commodities_quantainium_raw': 'QUAN',
    'items_commodities_quartz': 'QRTZ',
    'items_commodities_quartz_raw': 'QRTZ',
    'items_commodities_quasigrazeregg': 'QzG Egg',
    'items_commodities_quasigrazeregg_boreal': 'QzG Egg ',
    'items_commodities_quasigrazeregg_grassland': 'QzG Egg',
    'items_commodities_quasigrazeregg_jungle': 'QzG Egg',
    'items_commodities_quasigrazeregg_tundra': 'QzG Egg',
    'items_commodities_quasigrazertongue': 'QzG Tongue',
    'items_commodities_rantadung': '<EM3>DUNG</EM3>',
    'items_commodities_raw_ice': 'ICE',
    'items_commodities_raw_ouratite': 'OUR',
    'items_commodities_raw_silicon': 'SIL',
    'items_commodities_revenantpod': '<EM3>REV</EM3>',
    'items_commodities_riccite': 'RIC',
    'items_commodities_riccite_ore': 'RIC',
    'items_commodities_sadaryx': 'SAD',
    'items_commodities_sadaryx_raw': 'SAD',
    'items_commodities_saldynium': 'SALD',
    'items_commodities_saldynium_ore': 'SALD',
    'items_commodities_savrilium': 'SAV',
    'items_commodities_savrilium_ore': 'SAV',
    'items_commodities_silicon': 'SIL',
    'items_commodities_slam': '<EM3>[!]</EM3> SLAM',
    'items_commodities_stileron': 'STIL',
    'items_commodities_stileron_ore': 'STIL',
    'items_commodities_stonebugshell': '<EM3>Stone Bug Shell</EM3>',
    'items_commodities_sunsetberry': '<EM3>Sunset Berries</EM3>',
    'items_commodities_taranite': 'TAR',
    'items_commodities_taranite_raw': 'TAR',
    'items_commodities_tin': 'TIN',
    'items_commodities_tin_ore': 'TIN',
    'items_commodities_titanium': 'TITN',
    'items_commodities_titanium_ore': 'TITN',
    'items_commodities_torite': 'TOR',
    'items_commodities_torite_ore': 'TOR',
    'items_commodities_tungsten': 'TUNG',
    'items_commodities_tungsten_ore': 'TUNG',
    'items_commodities_widow': '<EM3>[!]</EM3> WiDoW',
    'items_commodities_wuotanseed': '<EM3>Wuotan Seed</EM3>',
    'mineabletype_primary_agricium': 'AGR',
    'mineabletype_primary_aluminium': 'ALUM',
    'mineabletype_primary_aslarite': 'ASL',
    'mineabletype_primary_bexalite': 'BEX',
    'mineabletype_primary_borase': 'BOR',
    'mineabletype_primary_copper': 'COP',
    'mineabletype_primary_corundum': 'Cor',
    'mineabletype_primary_gold': 'GLD',
    'mineabletype_primary_hephaestanite': 'HEPH',
    'mineabletype_primary_ice': 'ICE',
    'mineabletype_primary_iron': 'IRON',
    'mineabletype_primary_laranite': 'LAR',
    'mineabletype_primary_lindinium': 'LIND',
    'mineabletype_primary_ouratite': 'OUR',
    'mineabletype_primary_quantainium': 'QUAN',
    'mineabletype_primary_quartz': 'quart',
    'mineabletype_primary_riccite': 'RIC',
    'mineabletype_primary_savrillium': 'SAV',
    'mineabletype_primary_silicon': 'SIL',
    'mineabletype_primary_stileron': 'STIL',
    'mineabletype_primary_taranite': 'TAR',
    'mineabletype_primary_tin': 'TIN',
    'mineabletype_primary_titanium': 'TITN',
    'mineabletype_primary_torite': 'TOR',
    'mineabletype_primary_tungsten': 'Tun',
}

_FPS_ROCK_ALIASES = {
    'aphorite': 'hud_mining_fps_rock_name_1',
    'dolivine': 'hud_mining_fps_rock_name_2',
    'hadanite': 'hud_mining_fps_rock_name_3',
    'quantainium': 'hud_mining_rock_name_9',
}

_HARVESTABLE_ALIASES = {
    'armillaria': 'harvestable_armillaria',
    'bluemoon': 'harvestable_armillaria',
    'bluemoon fungus': 'harvestable_armillaria',
    'fotia seedpod': 'items_commodities_fotiascrub',
    'pingala seeds': 'items_commodities_pingala',
    'sunset berries': 'items_commodities_sunsetberry',
    'sunset berry': 'items_commodities_sunsetberry',
    'wuotan seeds': 'items_commodities_wuotanseed',
    'wuotan seed': 'items_commodities_wuotanseed',
}

_CREATURE_PREFIXES = {
    'quazigrazer': 'actor_species_creature_quazigrazer',
    'quasigrazer': 'actor_species_creature_quazigrazer',
    'kopion': 'actor_species_creature_kopion',
    'valakkar': 'actor_species_creature_valakkar',
    'marok': 'actor_species_creature_marok',
    'yormandi': 'actor_species_creature_yormandi',
}


def _strip_em(val):
    for tag in ('<EM1>', '</EM1>', '<EM2>', '</EM2>', '<EM3>', '</EM3>', '<EM4>', '</EM4>'):
        val = val.replace(tag, '')
    return val


def _keys_for_material(name, _seen=None):
    norm = ''.join(ch for ch in str(name).strip().lower() if ch.isalnum() or ch == '_')
    if not norm:
        return set()
    if _seen is None:
        _seen = set()
    if norm in _seen:
        return set()
    _seen.add(norm)
    keys = set()
    # Direct key match
    if norm in SHORT_LABELS:
        keys.add(norm)
    # Ore / commodity stems
    for prefix in ('mineabletype_primary_', 'items_commodities_'):
        for k in SHORT_LABELS:
            if k == prefix + norm or k.startswith(prefix + norm + '_'):
                keys.add(k)
        raw_k = prefix + 'raw_' + norm
        if raw_k in SHORT_LABELS:
            keys.add(raw_k)
    # Alias spelling (e.g. aluminium/aluminum, savrilium/savrillium, carinite/caranite)
    aliases = {'aluminum': 'aluminium', 'aluminium': 'aluminum', 'savrilium': 'savrillium', 'savrillium': 'savrilium', 'caranite': 'carinite', 'carinite': 'caranite', 'beradon': 'beradom', 'beradom': 'beradon'}
    alt = aliases.get(norm)
    if alt and alt not in _seen:
        keys |= _keys_for_material(alt, _seen)
    if norm in _FPS_ROCK_ALIASES:
        keys.add(_FPS_ROCK_ALIASES[norm])
    low = str(name).strip().lower()
    if low in _HARVESTABLE_ALIASES:
        keys.add(_HARVESTABLE_ALIASES[low])
    if norm in _CREATURE_PREFIXES:
        pref = _CREATURE_PREFIXES[norm]
        for k in SHORT_LABELS:
            if k.startswith(pref):
                keys.add(k)
    return keys


def _targets_path(profile=None):
    if profile is not None:
        return Path(profile) / 'synthstrings_targets.json'
    try:
        from installation import PROFILE
        return Path(PROFILE) / 'synthstrings_targets.json'
    except Exception:
        return None


def load_targets(profile=None):
    p = _targets_path(profile)
    if not p or not p.exists():
        return {'cyan': [], 'red': [], 'amounts': {}, 'blueprint': None}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        amounts = data.get('amounts') if isinstance(data.get('amounts'), dict) else {}
        return {
            'cyan': [str(x) for x in (data.get('cyan') or []) if str(x).strip()],
            'red': [str(x) for x in (data.get('red') or []) if str(x).strip()],
            'amounts': {str(k): str(v) for k, v in amounts.items() if str(k).strip() and str(v).strip()},
            'blueprint': data.get('blueprint'),
        }
    except Exception:
        return {'cyan': [], 'red': [], 'amounts': {}, 'blueprint': None}


def save_targets(cyan=(), red=(), amounts=None, blueprint=None, profile=None):
    p = _targets_path(profile)
    if not p:
        raise ValueError('Profile path unavailable for synthstrings_targets.json')
    p.parent.mkdir(parents=True, exist_ok=True)
    clean_amounts = {str(k).strip(): str(v).strip() for k, v in (amounts or {}).items() if str(k).strip() and str(v).strip()}
    payload = {
        'cyan': [str(x).strip() for x in cyan if str(x).strip()],
        'red': [str(x).strip() for x in red if str(x).strip()],
        'amounts': clean_amounts,
        'blueprint': blueprint,
    }
    p.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return payload


def effective_labels(targets=None, profile=None):
    labels = dict(SHORT_LABELS)
    t = load_targets(profile) if targets is None else targets
    amounts = {str(k).strip().lower(): str(v).strip() for k, v in (t.get('amounts') or {}).items() if str(v).strip()}
    for name in (t.get('red') or []):
        for k in _keys_for_material(name):
            if k in labels and '[!]' not in labels[k]:
                labels[k] = f'<EM4>{_strip_em(labels[k])}</EM4>'
    for name in (t.get('cyan') or []):
        amt = amounts.get(str(name).strip().lower())
        suffix = f' (need {amt})' if amt else ''
        for k in _keys_for_material(name):
            if k in labels and '[!]' not in labels[k]:
                labels[k] = f'<EM1>{_strip_em(labels[k])}{suffix}</EM1>'
    return labels


def apply_targets_to_global_ini(ini_path=None, targets=None, profile=None):
    from pathlib import Path as _Path
    if ini_path is None:
        try:
            from installation import game_directory
            ini_path = _Path(game_directory(True)) / 'Data/Localization/english/global.ini'
        except Exception:
            from synthstrings_sync import DEFAULT_INI_PATH
            ini_path = _Path(DEFAULT_INI_PATH)
    else:
        ini_path = _Path(ini_path)
    if not ini_path.exists():
        return False, 0
    raw = ini_path.read_bytes()
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig', errors='ignore')
    updated, changed = compact_mining_labels(text, targets=targets, profile=profile)
    if changed:
        from game_text_lifecycle import write_localization
        if profile is not None:
            write_localization(str(ini_path), updated.replace('\r\n', '\n').encode('utf-8-sig' if has_bom else 'utf-8'), profile=profile)
        else:
            write_localization(str(ini_path), updated.replace('\r\n', '\n').encode('utf-8-sig' if has_bom else 'utf-8'))
    return True, changed


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--profile', type=Path, default=None)
    p.add_argument('--ini', type=Path, default=None)
    args = p.parse_args()
    if args.apply:
        if args.profile is not None:
            import installation
            installation.PROFILE = args.profile
        ok, n = apply_targets_to_global_ini(ini_path=args.ini, profile=args.profile)
        print(json.dumps({'ok': ok, 'changed': n}))


def compact_mining_labels(text, targets=None, profile=None):
    labels = effective_labels(targets=targets, profile=profile)
    result = []
    changed = 0
    for line in text.splitlines(keepends=True):
        left, sep, value = line.partition("=")
        key = left.lstrip("\ufeff").split(",")[0].strip().casefold() if sep else ""
        label = labels.get(key)
        if label is not None:
            ending = "\r\n" if value.endswith("\r\n") else "\n" if value.endswith("\n") else ""
            new = left + "=" + label + ending
            changed += new != line
            line = new
        result.append(line)
    return "".join(result), changed
