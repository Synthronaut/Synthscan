import os
import glob
import re
import json
import time
import threading
import copy
from crafting_catalog import get_catalog
from datetime import datetime
from refinery_orders import atomic_json


def synchronized(method):
    def locked(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return locked

DEFAULT_SC_DIR = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE"
BLUEPRINT_LIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blueprints_library.json")

def categorize_blueprint(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["pistol", "battery", "crossbow", "smg", "shotgun", "rifle", "lumen", "rouge", "nighthunter", "mag", "optic", "suppressor"]):
        return "FPS Weapons & Gear"
    if any(k in n for k in ["helmet", "core", "arms", "legs", "backpack", "flight suit", "suit", "undersuit", "testudo", "morozov", "monde", "strata"]):
        return "Armor & Flight Suits"
    if any(k in n for k in ["mining", "scraper", "nozzle", "propulsor", "cryo-star", "ind/", "colossus", "huracan", "sedulity", "agni", "defiant", "th-01"]):
        return "Ship & Industrial"
    if any(k in n for k in ["cannon", "scattergun", "driver", "repeater", "laser", "distortion", "gatling", "broadsword", "sledge", "omnisky", "dominance"]):
        return "Ship Weapons"
    return "General Equipment"

def generate_default_cost(name: str, category: str) -> dict:
    """Compatibility API: return sourced SCU ingredients, never guessed costs."""
    catalog = get_catalog()
    item = catalog.resolve(name)
    return catalog.cost(item) if item else {}


BLUEPRINT_CATALOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blueprints_catalog.json")
BLUEPRINT_FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blueprints_favorites.json")

def classify_blueprint_meta(name: str, orig_cat: str = "") -> dict:
    n = name.lower()

    # 1. Ship Weapons
    if orig_cat == 'Ship Weapons' or any(k in n for k in ['cannon', 'gatling', 'repeater', 'scattergun', 'mass driver', 'broadsword', 'greatsword', 'longsword', 'dominance', 'attrition', 'cf-117', 'cf-227', 'cf-337', 'cf-447', 'cf-557', 'cf-667', 'm3a', 'm4a', 'm5a', 'm6a', 'm7a', 'm8a', 'omnisky', 'sledge', 'tarantula', 'yellowjacket', 'scorpion', 'mantis', 'revenant', 'ad4b', 'ad5b', 'ad6b', 'c-788', 'buzzsaw', 'sawbuck', 'shredder', 'singe', 'draugar', 'nn-13', 'nn-14', 'nn-15', 'xj1', 'xj2', 'xj3', 'strife', 'lightstrike']):
        size = 'Size 1'
        if any(k in n for k in ['cf-117', 'm3a', 'nn-13', 'xj1', 'longsword', 'buzzsaw', 'omnisky iii', 'sledge i ', 'gt-210', 'dominance-1', 'lightstrike i ']):
            size = 'Size 1'
        elif any(k in n for k in ['cf-227', 'm4a', 'nn-14', 'xj2', 'greatsword', 'sawbuck', 'strife', 'omnisky vi', 'sledge ii ', 'gt-215', 'dominance-2', 'lightstrike ii ']):
            size = 'Size 2'
        elif any(k in n for k in ['cf-337', 'm5a', 'nn-15', 'xj3', 'broadsword', 'shredder', 'singe', 'sledge iii ', 'gt-220', 'dominance-3', 'lightstrike iii ']):
            size = 'Size 3'
        elif any(k in n for k in ['c-788', 'ad4b', 'cf-447', 'm6a', 'revenant', 'attrition-4']):
            size = 'Size 4'
        elif any(k in n for k in ['ad5b', 'cf-557', 'm7a', 'draugar', 'attrition-5']):
            size = 'Size 5'
        elif any(k in n for k in ['ad6b', 'cf-667', 'm8a', 'attrition-6', 'omnisky xviii']):
            size = 'Size 6'
        elif 'mark 1' in n: size = 'Size 1'
        elif 'mark 2' in n: size = 'Size 2'
        elif 'mark 3' in n: size = 'Size 3'

        dmg = 'Laser'
        if any(k in n for k in ['m3a', 'm4a', 'm5a', 'm6a', 'm7a', 'm8a', 'lightstrike', 'omnisky', 'dominance', 'repeater', 'cf-', 'attrition', 'singe']):
            dmg = 'Laser'
        elif any(k in n for k in ['nn-13', 'nn-14', 'nn-15', 'xj1', 'xj2', 'xj3', 'distortion']):
            dmg = 'Distortion'
        else:
            dmg = 'Ballistic'

        return {'main': 'Ship Weapons', 'size': size, 'dmg': dmg, 'sub': f'{size} {dmg}'}

    # 2. Flight Suits & Undersuits
    if any(k in n for k in ['flight suit', 'undersuit', 'pembroke', 'novikov']):
        return {'main': 'Flight Suits', 'size': None, 'dmg': None, 'sub': 'Flight Suits'}

    # 3. Armor
    if any(k in n for k in ['helmet', 'core', 'arms', 'legs', 'backpack', 'strata', 'orc-', 'adp', 'testudo', 'morozov', 'antium', 'defiance', 'truedef', 'lynx', 'calico', 'dust devil', 'manticore', 'monde']):
        sub = 'All Armor'
        if 'helmet' in n: sub = 'Helmets'
        elif 'core' in n: sub = 'Cores'
        elif 'arms' in n: sub = 'Arms'
        elif 'legs' in n: sub = 'Legs'
        elif 'backpack' in n: sub = 'Backpacks'
        return {'main': 'Armor', 'size': None, 'dmg': None, 'sub': sub}

    # 4. FPS Gear vs FPS Weapons
    if any(k in n for k in ['magazine', 'battery', 'crate', 'ammo', 'medpen', 'magnabloom']):
        sub = 'Consumables & Supplies'
        if 'magazine' in n: sub = 'Magazines & Ammo'
        elif 'battery' in n: sub = 'Batteries'
        return {'main': 'FPS Gear', 'size': None, 'dmg': None, 'sub': sub}

    if any(k in n for k in ['smg', 'rifle', 'shotgun', 'pistol', 'sniper', 'lmg', 'crossbow', 'karna', 'p8-sc', 'c54', 's71', 'parallax', 'pulse', 'quartz', 'r97', 'arclight', 'atzkav', 'coda', 'custodian', 'deadrig', 'devastator', 'gallant', 'killshot', 'lumin', 'p6-lr', 'ravager', 'ripper', 'scalpel', 'tripledown', 'yubarev', 'zenith', 'novian']):
        sub = 'All Weapons'
        if 'pistol' in n: sub = 'Pistols'
        elif 'smg' in n: sub = 'SMGs'
        elif 'shotgun' in n: sub = 'Shotguns'
        elif any(k in n for k in ['rifle', 'sniper', 'lmg']): sub = 'Rifles & Snipers'
        return {'main': 'FPS Weapons', 'size': None, 'dmg': None, 'sub': sub}

    # 5. Industrial Components
    if any(k in n for k in ['mining', 'laser', 'scraper', 'nozzle', 'propulsor', 'th-01', 'cryo-star', 'colossus', 'huracan', 'sedulity', 'agni', 'defiant', 'hofstede', 'helix', 'arbor', 'klein', 'lancet', 'lawson', 'pitman', 'marlin', 'rn-7s', 'norfield', 'lindstrom', 'harkin', 'clearcut', 'module', 'gadget', 'surge', 'stampede', 'focus', 'brandt', 'torpid', 'boremax', 'waveshift']):
        sub = 'Industrial Modules'
        if any(k in n for k in ['mining', 'laser', 'scraper', 'clearcut']): sub = 'Mining Lasers & Scrapers'
        elif any(k in n for k in ['propulsor', 'th-01', 'cryo-star', 'colossus', 'huracan', 'sedulity', 'agni', 'defiant']): sub = 'Industrial Propulsors'
        elif any(k in n for k in ['nozzle', 'marlin', 'rn-7s', 'norfield', 'lindstrom', 'harkin']): sub = 'Fuel Nozzles'
        return {'main': 'Industrial Components', 'size': None, 'dmg': None, 'sub': sub}

    # 6. Ship Components
    sub = 'All Ship Components'
    if any(k in n for k in ['5ca', '6ca', '7ca', '5ma', '6ma', '7ma', '5sa', '6sa', '7sa', 'shield', 'palisade', 'rampart', 'fr-']): sub = 'Shield Generators'
    elif any(k in n for k in ['vk-00', 'siren', 'beacon', 'crossfield', 'pontes', 'ts-2', 'quantum']): sub = 'Quantum Drives'
    elif any(k in n for k in ['quadracell', 'supernova', 'overdrive', 'power']): sub = 'Power Plants'
    elif any(k in n for k in ['ultra-flow', 'glacier', 'polar', 'blastchill', 'aufeis', 'avalanche', 'cooler']): sub = 'Coolers'
    return {'main': 'Ship Components', 'size': None, 'dmg': None, 'sub': sub}

class BlueprintManager:
    def __init__(self, sc_dir=DEFAULT_SC_DIR):
        self.lock = threading.RLock()
        self.load_errors = set()
        self.sc_dir = sc_dir
        self.blueprints = {}
        self.catalog = {}
        self.favorites = set()
        self.watcher_thread = None
        self.watching = False
        self.load_library()

    def load_library(self):
        if os.path.exists(BLUEPRINT_LIB_FILE):
            try:
                with open(BLUEPRINT_LIB_FILE, "r", encoding="utf-8") as f:
                    self.blueprints = json.load(f)
                if not isinstance(self.blueprints, dict) or not all(isinstance(v, dict) for v in self.blueprints.values()):
                    raise ValueError('Invalid ownership records')
            except Exception:
                self.load_errors.add(BLUEPRINT_LIB_FILE)
                self.blueprints = {}
        else:
            self.blueprints = {}

        if os.path.exists(BLUEPRINT_CATALOG_FILE):
            try:
                with open(BLUEPRINT_CATALOG_FILE, "r", encoding="utf-8") as f:
                    self.catalog = json.load(f)
            except Exception:
                self.catalog = {}
        else:
            self.catalog = {}

        if os.path.exists(BLUEPRINT_FAVORITES_FILE):
            try:
                with open(BLUEPRINT_FAVORITES_FILE, "r", encoding="utf-8") as f:
                    raw_favorites = json.load(f)
                if not isinstance(raw_favorites, list) or not all(isinstance(v, str) for v in raw_favorites):
                    raise ValueError('Invalid favorites records')
                self.favorites = set(raw_favorites)
            except Exception:
                self.load_errors.add(BLUEPRINT_FAVORITES_FILE)
                self.favorites = set()
        else:
            self.favorites = set()

    @synchronized
    def save_library(self):
        if BLUEPRINT_LIB_FILE in self.load_errors:
            raise ValueError('Blueprint ownership file could not be read; original preserved')
        atomic_json(BLUEPRINT_LIB_FILE, self.blueprints)

    @synchronized
    def scan_all_logs(self, custom_dir=None):
        base_dir = custom_dir or self.sc_dir
        pattern = re.compile(r"Received Blueprint:\s*(.*?):")
        new_count = 0
        
        all_logs = glob.glob(os.path.join(base_dir, "logbackups", "*.log"))
        game_log = os.path.join(base_dir, "Game.log")
        if os.path.exists(game_log):
            all_logs.append(game_log)
            
        for log_path in all_logs:
            fname = os.path.basename(log_path)
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        m = pattern.search(line)
                        if m:
                            bp_name = m.group(1).strip()
                            if bp_name:
                                ts_match = re.match(r"<(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
                                ts = ts_match.group(1) if ts_match else datetime.now().isoformat()
                                new_count += int(self.record_log_unlock(bp_name, ts, fname))
            except Exception:
                continue

        if new_count > 0:
            self.save_library()
        return new_count, len(self.blueprints)

    @synchronized
    def add_or_update_blueprint(self, name: str, category: str = None, cost: dict = None, source: str = "Manual / OCR"):
        cat = category or categorize_blueprint(name)
        c = cost or generate_default_cost(name, cat)
        ts = datetime.now().isoformat()
        is_new = name not in self.blueprints
        self.blueprints[name] = {
            "name": name,
            "category": cat,
            "unlocked_at": self.blueprints.get(name, {}).get("unlocked_at", ts),
            "source": source,
            "cost": c
        }
        self.save_library()
        return is_new

    @synchronized
    def remove_blueprint(self, name: str) -> bool:
        original = copy.deepcopy(self.blueprints)
        item = get_catalog().resolve(name)
        keys = [n for n in self.blueprints if n == name or
                (item and (resolved := get_catalog().resolve(n)) and resolved['id'] == item['id'])]
        if not keys:
            return False
        for key in keys:
            del self.blueprints[key]
        try:
            self.save_library()
        except Exception:
            self.blueprints = original
            raise
        return True


    @synchronized
    def unlock_batch(self, items: list, source: str = "Manual Batch") -> int:
        if BLUEPRINT_LIB_FILE in self.load_errors:
            raise ValueError('Unreadable ownership file; import stopped to preserve it')
        catalog = get_catalog()
        original = copy.deepcopy(self.blueprints)
        owned = {b['id'] for n in self.blueprints if (b := catalog.resolve(n))}
        added = 0
        for item in items:
            name = item if isinstance(item, str) else item.get('name')
            if not name:
                continue
            bp = catalog.resolve(item.get('id') or name) if isinstance(item, dict) else catalog.resolve(name)
            key = 'catalog:' + bp['id'] if bp and not catalog.resolve(name) else name
            if key in self.blueprints or (bp and bp['id'] in owned):
                continue
            self.blueprints[key] = dict(name=name, catalog_id=bp['id'] if bp else None,
                                         category=bp['category'] if bp else categorize_blueprint(name),
                                         unlocked_at=datetime.now().isoformat(), source=source,
                                         cost=catalog.cost(bp) if bp else {})
            if bp:
                owned.add(bp['id'])
            added += 1
        if added:
            try:
                self.save_library()
            except Exception:
                self.blueprints = original
                raise
        return added


    @synchronized
    def save_favorites(self):
        if BLUEPRINT_FAVORITES_FILE in self.load_errors:
            raise ValueError('Unreadable favorites file; original preserved')
        atomic_json(BLUEPRINT_FAVORITES_FILE, sorted(self.favorites))


    @synchronized
    def toggle_favorite(self, name: str) -> bool:
        original = self.favorites.copy()
        item = get_catalog().resolve(name)
        matches = [v for v in self.favorites if v == name or
                   (item and (resolved := get_catalog().resolve(v)) and resolved['id'] == item['id'])]
        if matches:
            self.favorites.difference_update(matches)
        else:
            self.favorites.add(name)
        try:
            self.save_favorites()
        except Exception:
            self.favorites = original
            raise
        return not bool(matches)


    def is_favorite(self, name: str) -> bool:
        def _clean(s):
            return re.sub(r'^(Civ|Ind)/\d+/[A-Z]\s+', '', s).strip().lower()
        if name in self.favorites:
            return True
        c_name = _clean(name)
        for f in self.favorites:
            if _clean(f) == c_name:
                return True
        return False

    def get_stats(self):
        rows = self.get_blueprints()
        owned = sum(b['is_unlocked'] for b in rows)
        return dict(total_owned=owned, total_catalog=len(rows), total_missing=len(rows)-owned,
                    total_favorites=sum(b['is_favorite'] for b in rows),
                    percentage=owned / len(rows) * 100 if rows else 0)


    @synchronized
    def get_blueprints(self, category=None, search=None, status_filter="ALL"):
        main = category[0] if isinstance(category, (list, tuple)) else category
        rows = get_catalog().library(self.blueprints, self.favorites, search=search or '',
                                     category=main or 'All', status=status_filter)
        if isinstance(category, (list, tuple)) and len(category) > 1 and category[1] not in (None, 'All', 'ALL'):
            rows = [b for b in rows if category[1] in (b['type'], b['meta']['size'])]
        return rows



    def get_categories(self):
        return ['All'] + sorted({b['category'] for b in self.get_blueprints()})



    @synchronized
    def record_log_unlock(self, name, timestamp, source):
        added = self.unlock_batch([name], source=source)
        if added:
            self.blueprints[name]['unlocked_at'] = timestamp
            self.save_library()
        return bool(added)

    def start_game_log_watcher(self, on_new_blueprint_cb=None):
        if self.watching:
            return
        self.watching = True
        game_log = os.path.join(self.sc_dir, 'Game.log')
        def watch_loop():
            last_size = os.path.getsize(game_log) if os.path.exists(game_log) else 0
            pattern = re.compile(r'Received Blueprint:\s*(.*?):')
            while self.watching:
                time.sleep(2)
                try:
                    current_size = os.path.getsize(game_log)
                    if current_size < last_size:
                        last_size = 0
                    if current_size == last_size:
                        continue
                    with open(game_log, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_size)
                        lines = f.readlines()
                        last_size = f.tell()
                    for line in lines:
                        match = pattern.search(line)
                        if not match or not match[1].strip():
                            continue
                        name = match[1].strip()
                        stamp = re.match(r'<(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                        stamp = stamp[1] if stamp else datetime.now().isoformat()
                        if self.record_log_unlock(name, stamp, 'Live Game.log') and on_new_blueprint_cb:
                            on_new_blueprint_cb(self.blueprints[name])
                except OSError:
                    continue
        self.watcher_thread = threading.Thread(target=watch_loop, daemon=True)
        self.watcher_thread.start()


    def stop_watcher(self):
        self.watching = False

def parse_fabricator_screen(img_input):
    """Return review candidates; a visible name alone never proves ownership."""
    from screen_readers import read_image, fabricator_candidates
    return fabricator_candidates(read_image(img_input))


