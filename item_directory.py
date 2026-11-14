"""Item acquisition lookups. All network/extraction work runs off the UI thread."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.request
import uuid

from telemetry_ipc import publish_json, read_shared_json

SHOP_TTL = 24 * 3600  # UEX documents a daily cache for this endpoint.
VEHICLE_TTL = 12 * 3600
RETRY = 300


def item_guid(value):
    return str(uuid.UUID(value))


def lookup_identity(value):
    if isinstance(value,str) and re.fullmatch(r'market-[1-9][0-9]{0,8}-[0-9a-f]{12}',value):return value
    if isinstance(value,str) and re.fullmatch(r'vehicle-[1-9][0-9]{0,8}-[0-9a-f]{12}',value):
        return value
    return item_guid(value)


def is_component(entry):
    return entry.get('category')=='Ship components' or (
        '/entities/scitem/ships/' in entry.get('record','') and
        entry.get('type','').startswith(('Weapon','Missile','Mining','Salvage','TractorBeam','TowingBeam','ToolArm')))


def uex_json(resource):
    request=urllib.request.Request('https://api.uexcorp.uk/2.0/'+resource,headers={
        'User-Agent':'SynthScan-ItemDirectory/1.0','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=12) as response:
        if not response.geturl().startswith('https://api.uexcorp.uk/'):
            raise ValueError('Unexpected item source redirect')
        raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('UEX response exceeds limit')
    return json.loads(raw)


def vehicle_rows(payload,checked_at):
    if not isinstance(payload,dict) or payload.get('status')!='ok' or not isinstance(payload.get('data'),list):
        raise ValueError('Invalid vehicle catalog')
    if not payload['data'] or len(payload['data'])>5000:raise ValueError('Invalid vehicle catalog size')
    rows=[];seen=set()
    for vehicle in payload['data']:
        identifier=vehicle.get('id');name=vehicle.get('name_full') or vehicle.get('name')
        if not isinstance(identifier,int) or isinstance(identifier,bool) or not 0<identifier<10**9 or not isinstance(name,str) or not name:
            raise ValueError('Invalid vehicle identity')
        if identifier in seen:raise ValueError('Duplicate vehicle identity')
        seen.add(identifier)
        if vehicle.get('is_addon'):continue
        # Some UEX vehicles have no game UUID. Their exact UEX ID still works;
        # include an identity fingerprint so reused IDs cannot reuse old prices.
        fingerprint=hashlib.sha256(str(vehicle.get('uuid') or name).encode()).hexdigest()[:12]
        key=f'vehicle-{identifier}-{fingerprint}'
        kind='Vehicle' if vehicle.get('is_ground_vehicle') else 'Ship'
        maker=str(vehicle.get('company_name') or 'Unknown manufacturer')
        from finder_categories import vehicle_metadata, hangar_classification
        overview=vehicle_metadata(vehicle)
        hangar=hangar_classification(kind, None, overview.get('length'))
        specs=[]
        if overview.get('length'):specs.append(f"Length: {overview['length']:g} m")
        if hangar:specs.append(f"Expected hangar: {hangar}")
        spec_text = ('\n' + ' · '.join(specs) + '\n') if specs else ''
        detail=f"{name}\n{kind} · {maker}\n{spec_text}\nIn-game purchase locations and aUEC prices are checked separately from the vehicle catalog.\n"
        if vehicle.get('is_concept'):detail+='Listed as a concept by UEX; inclusion here does not imply in-game availability.\n'
        detail+='\nVehicle directory: UEX Corp · checked '+date(checked_at)
        rows.append(dict(id=key,item_id=key,name=name,kind=kind,category='Ground vehicles' if kind=='Vehicle' else 'Ships',
                         detail=detail,icon='',search=' '.join([name,str(vehicle.get('name') or ''),maker,kind]),uex_vehicle_id=identifier,game_vehicle_id=str(vehicle.get('uuid') or ''),ship_overview=overview))
    return rows


def fetch_vehicle_catalog():
    now=time.time()
    return dict(schema=2,checked_at=now,rows=vehicle_rows(uex_json('vehicles'),now),source='UEX Corp')


def saved_vehicles(directory):
    try:
        value=read_shared_json(Path(directory)/'directory_vehicles.json',limit=4*1024*1024)
        if not isinstance(value.get('rows'),list) or not value['rows']:raise ValueError('Invalid vehicle cache')
        for row in value['rows']:
            if lookup_identity(row['item_id'])!=row['id'] or row['kind'] not in ('Ship','Vehicle') or not isinstance(row['name'],str):
                raise ValueError('Invalid cached vehicle identity')
        return value
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return {}


def patch(value):
    found = re.search(r'\b(\d+\.\d+\.\d+)\b', str(value))
    return found[1] if found else ''


def stamp(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else 0


def date(value):
    try:return datetime.fromtimestamp(stamp(value), timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if stamp(value) else 'not reported'
    except (ValueError,OverflowError,OSError):return 'invalid source date'


def compact_location(value):
    parts=[part.strip() for part in str(value).split('→') if part.strip()]
    if len(parts)>1 and parts[0].casefold() in {'stanton','pyro','nyx','castra','terra','magnus'}:parts.pop(0)
    if len(parts)>1:
        for parent in reversed(parts[:-1]):
            parts[-1]=re.sub(r'(?:\s+[-–—]\s+|,\s*|\s*\()'+re.escape(parent)+r'\)?\s*$','',parts[-1],flags=re.I).strip()
    return ' → '.join(dict.fromkeys(part for part in parts if part))


def shop_rows(payload):
    if not isinstance(payload, dict) or payload.get('status') != 'ok' or not isinstance(payload.get('data'), list):
        raise ValueError('UEX did not return a valid item price list')
    if len(payload['data']) > 5000:
        raise ValueError('Item price list exceeds limit')
    result = {}
    for raw in payload['data']:
        if not isinstance(raw, dict):
            raise ValueError('Invalid shop record')
        price = raw.get('price_buy')
        # price_buy is what the player pays the shop. price_sell is not a purchase offer.
        if not stamp(price) or raw.get('terminal_is_player_owned') or not raw.get('terminal_name'):
            continue
        fields = ('star_system_name', 'planet_name', 'moon_name', 'orbit_name',
                  'space_station_name', 'city_name', 'outpost_name', 'terminal_name')
        location = list(dict.fromkeys(str(raw[k]) for k in fields if raw.get(k)))
        row = dict(terminal_id=raw.get('id_terminal'), location=compact_location(' → '.join(location)),
                   price=price, game_version=str(raw.get('game_version') or ''),
                   reported_at=stamp(raw.get('date_modified')))
        key = (row['terminal_id'], row['location'])
        if key not in result or row['reported_at'] > result[key]['reported_at']:
            result[key] = row
    return sorted(result.values(), key=lambda r: (r['price'], r['location']))


def fetch_shops(identifier):
    identifier = lookup_identity(identifier)
    if identifier.startswith('market-'):return dict(item_id=identifier,checked_at=time.time(),rows=[],source='Player market only')
    if identifier.startswith('vehicle-'):
        resource='vehicles_purchases_prices?id_vehicle='+identifier.split('-')[1]
    else:resource='items_prices?uuid='+identifier
    payload=uex_json(resource)
    rows=shop_rows(payload)
    if identifier.startswith('vehicle-') and any(row.get('id_vehicle')!=int(identifier.split('-')[1]) for row in payload['data']):
        raise ValueError('Vehicle price response has a different identity')
    return dict(item_id=identifier, checked_at=time.time(), rows=rows, source='UEX Corp')


def shop_view(cached, current_patch, now, error=''):
    """Presentation fields for native shop cards, retaining source dates and prices."""
    if not cached:return dict(rows=[], checked_label='', stale=False)
    checked=stamp(cached.get('checked_at'))
    ttl=VEHICLE_TTL if str(cached.get('item_id','')).startswith('vehicle-') else SHOP_TTL
    rows=[]
    for row in sorted(cached.get('rows', []), key=lambda r: (patch(r.get('game_version')) != current_patch, r['price'], r['location'])):
        parts=compact_location(row['location']).split(' → ')
        version=patch(row.get('game_version'))
        different=bool(current_patch and version and version!=current_patch)
        rows.append(dict(row,shop=parts[-1],place=' · '.join(parts[:-1]) or 'Location not reported',
                         reported_label='Reported '+date(row.get('reported_at')),
                         patch_label='Patch '+str(row.get('game_version') or 'unknown')+(' · different patch' if different else ''),
                         different_patch=different))
    return dict(rows=rows,checked_label=date(checked),stale=bool(error or not 0<=now-checked<ttl))


def shop_text(cached, current_patch, now, error=''):
    lines = ['IN-GAME PURCHASE LOCATIONS — UEX Corp']
    if not cached:
        return '\n'.join(lines + ['Shop lookup unavailable; trying again automatically.' if error else 'Checking shops in the background…'])
    checked = stamp(cached.get('checked_at'))
    ttl=VEHICLE_TTL if str(cached.get('item_id','')).startswith('vehicle-') else SHOP_TTL
    stale = not 0 <= now - checked < ttl
    lines.append('Last checked: ' + date(checked) + (' · cached / refresh overdue' if stale or error else ''))
    rows = sorted(cached.get('rows', []), key=lambda r: (patch(r.get('game_version')) != current_patch, r['price'], r['location']))
    if not rows:
        lines.append('No retail purchase listings reported by UEX. This does not prove the item is unavailable.')
    for row in rows:
        reported_patch = patch(row.get('game_version'))
        note = ' · DIFFERENT PATCH' if current_patch and reported_patch and reported_patch != current_patch else ''
        lines += [f"{compact_location(row['location'])} — {row['price']:,.0f} aUEC each",
                  f"  Reported {date(row.get('reported_at'))} · patch {row.get('game_version') or 'unknown'}{note}"]
    lines.append('Community-reported shop data; current stock is not guaranteed.')
    if error:
        lines.append('Refresh unavailable; keeping the last successful lookup and retrying automatically.')
    return '\n'.join(lines)


def source_lines(blueprint, catalog, briefings=False):
    lines = []
    if blueprint.get('unlock_source'):lines.append('Unlock data: '+blueprint['unlock_source']+' · checked '+date(blueprint.get('unlock_checked_at')))
    if blueprint.get('known_from_start'):
        lines.append('Listed as available from the start (reference annotation).')
    sources = catalog.sources(blueprint)
    if not sources and not blueprint.get('known_from_start'):
        lines.append('No known unlock source in this catalog; this does not mean it cannot be obtained.')
    for mission in sources:
        lines.append(' • ' + ' | '.join(str(mission.get(k) or 'Unknown') for k in ('title', 'faction', 'system', 'standing')))
        if briefings:
            lines.append(f"   Reward pool chance: {mission.get('chance', '?')}%; pool size: {mission.get('pool_size', '?')}. Individual blueprint chance is not specified.")
            lines.append(f"   Cooldown: {mission.get('cooldown', '?')} minutes")
    if sources:
        lines.append('Listed reward pools do not guarantee mission availability or a particular blueprint.' if blueprint.get('unlock_source') else 'Mission unlocks are community reference annotations, not live mission availability.')
    return lines


def build_workspace(destination):
    # Fresh catalog objects are needed after the atomic reference-generation swap.
    from crafting_catalog import CraftingCatalog
    from game_library import GameLibrary
    from native_workspace_data import library_export
    token=ItemDirectoryService.catalogue_token()
    game, crafting = GameLibrary(), CraftingCatalog()
    if game.error or not game.entries:
        raise ValueError(game.error or 'Empty item catalog')
    if ItemDirectoryService.catalogue_token()!=token:
        raise ValueError('Catalog generation changed while reading; retry with a complete generation')
    vehicles=saved_vehicles(Path(destination).parent)
    from finder_market import directory_rows,enrich_directory
    from material_qualities import bundled
    temporary=Path(destination).with_name('directory-build-'+uuid.uuid4().hex+'.json')
    try:
        library_export(temporary, game=game, catalog=crafting,extra_rows=vehicles.get('rows',[]))
        value=enrich_directory(json.loads(temporary.read_text(encoding='utf-8')),directory_rows(Path(destination).parent),crafting.data.get('material_qualities') or bundled())
        from directory_audit import validate
        value['audit']=validate(value['rows'])
        if not publish_json(destination,value):raise OSError('Could not publish item directory')
    finally:temporary.unlink(missing_ok=True)
    return dict(schema=1, revision=hashlib.sha256(Path(destination).read_bytes()).hexdigest(),
                updated_at=time.time(), build=game.data['provenance'].get('build', {}), entries=len(game.entries),
                vehicles=len(vehicles.get('rows',[])),vehicles_checked_at=vehicles.get('checked_at',0))


class ItemDirectoryService:
    """Small polling surface for the bridge; never waits for a lookup or export."""
    def __init__(self, directory, owner, fetch=fetch_shops, build=build_workspace, token=None,vehicle_fetch=fetch_vehicle_catalog):
        self.directory = Path(directory)
        self.owner = owner
        self.fetch, self.build = fetch, build
        self.token = token or self.catalogue_token
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='item-directory')
        self.vehicle_fetch=vehicle_fetch;self.vehicle_future=None
        vehicles=saved_vehicles(self.directory)
        self.next_vehicle_check=stamp(vehicles.get('checked_at'))+VEHICLE_TTL if vehicles.get('schema')==2 else 0
        self.export = None
        self.export_token = None
        self.next_export = 0
        self.active = None
        self.lookup = None
        self.lookup_id = None
        self.cache = {}
        self.retry = {}
        self.errors = {}
        self.next_poll = 0
        self.last_result = None
        self.current_patch = ''

    @staticmethod
    def catalogue_token():
        from installation import output_root,PROFILE
        root = output_root() / 'data'
        pointer = root / 'catalogue_current.json'
        source=PROFILE/'reference_source_current.json'
        source_revision=hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else ''
        market=PROFILE/'finder_market_index.json'
        source_revision+=':'+str(market.stat().st_mtime_ns if market.exists() else 0)
        if pointer.exists():return hashlib.sha256(pointer.read_bytes()).hexdigest(),source_revision
        return tuple((root / name).stat().st_mtime_ns for name in ('local_game_library.json', 'local_game_catalog.json')),source_revision

    def cached(self, identifier):
        if identifier not in self.cache:
            try:
                value = read_shared_json(self.directory / 'item_shops' / (identifier + '.json'), limit=512 * 1024)
                if value.get('item_id') != identifier or not isinstance(value.get('rows'), list):
                    raise ValueError('Invalid shop cache')
                if any(not isinstance(row,dict) or not stamp(row.get('price')) or not isinstance(row.get('location'),str) for row in value['rows']):
                    raise ValueError('Invalid cached shop row')
                self.cache[identifier] = value
            except (OSError, ValueError, TypeError):
                self.cache[identifier] = None
        return self.cache[identifier]

    def tick(self, now=None, current_patch=None):
        now = time.time() if now is None else now
        if now < self.next_poll:
            return
        self.next_poll = now + .25
        if current_patch:
            self.current_patch=patch(current_patch)
        if self.vehicle_future is not None and self.vehicle_future.done():
            try:
                value=self.vehicle_future.result()
                if not publish_json(self.directory/'directory_vehicles.json',value):raise OSError('Could not save vehicle catalog')
                self.next_vehicle_check=now+VEHICLE_TTL
                self.export_token=None;self.next_export=0
            except Exception:self.next_vehicle_check=now+RETRY
            self.vehicle_future=None
        if self.vehicle_fetch is not None and self.vehicle_future is None and now>=self.next_vehicle_check:
            self.vehicle_future=self.pool.submit(self.vehicle_fetch)
        if self.export is not None and self.export.done():
            try:
                status = self.export.result()
                if not current_patch:self.current_patch = patch(status.get('build', {}).get('Branch'))
                publish_json(self.directory / 'item_directory_catalog.json', status)
            except Exception:
                self.export_token = None
                self.next_export = now + RETRY
            self.export = None
        if now >= self.next_export and self.export is None:
            self.next_export = now + 30
            try:
                token = self.token()
                if token != self.export_token:
                    self.export_token = token
                    self.export = self.pool.submit(self.build, self.directory / 'workspace_library.json')
            except (OSError, ValueError):
                self.next_export = now + RETRY
        try:
            request = read_shared_json(self.directory / 'item_directory_request.json')
            if request.get('owner_pid') == self.owner and 0 <= now - stamp(request.get('at')) < 60:
                identifier = lookup_identity(request['item_id'])
                if request.get('request_id') and request.get('row_id'):
                    self.active = dict(request, item_id=identifier)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
        if self.lookup is not None and self.lookup.done():
            identifier = self.lookup_id
            try:
                result = self.lookup.result()
                if result.get('item_id') != identifier:
                    raise ValueError('Wrong item identity')
                self.cache[identifier] = result
                folder = self.directory / 'item_shops'
                folder.mkdir(parents=True, exist_ok=True)
                publish_json(folder / (identifier + '.json'), result)
                self.errors.pop(identifier, None)
            except Exception:
                self.errors[identifier] = 'lookup failed'
                self.retry[identifier] = now + RETRY
            self.lookup = None
        if not self.active:
            return
        identifier = self.active['item_id']
        cached = self.cached(identifier)
        age = now - stamp((cached or {}).get('checked_at'))
        ttl=VEHICLE_TTL if identifier.startswith('vehicle-') else SHOP_TTL
        if self.lookup is None and (not cached or not 0 <= age < ttl) and now >= self.retry.get(identifier, 0):
            self.lookup_id = identifier
            self.lookup = self.pool.submit(self.fetch, identifier)
        result = dict(owner_pid=self.owner, request_id=self.active['request_id'], row_id=self.active['row_id'],
                      item_id=identifier, loading=bool((not cached or not 0 <= age < ttl) and not self.errors.get(identifier)),
                      error=bool(self.errors.get(identifier)),
                      text=shop_text(cached, self.current_patch, now, self.errors.get(identifier, '')))
        result.update(shop_view(cached,self.current_patch,now,self.errors.get(identifier,'')))
        if result != self.last_result:
            publish_json(self.directory / 'item_directory_detail.json', result)
            self.last_result = result

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
