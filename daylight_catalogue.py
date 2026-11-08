"""Bounded public-data refresh and local-only destination preferences."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import time
import urllib.request
from daylight import Body, Site, finite, vector, observed_phase
from refinery_orders import atomic_json

SOURCE = 'https://dydrmr.github.io/VerseTime/data/'
BUNDLED = Path(__file__).resolve().parent/'data/daylight_catalogue.json'
MAX_BYTES = 2*1024*1024


def parse_sources(bodies_csv, locations_csv):
    """Never execute upstream scripts. Parse just the two public CSV tables."""
    rows = list(csv.DictReader(io.StringIO(bodies_csv)))
    places = list(csv.DictReader(io.StringIO(locations_csv)))
    if not 2 <= len(rows) <= 1000 or not 1 <= len(places) <= 20000:
        raise ValueError('Unexpected daylight catalogue size')
    def xyz(row):
        return list(vector([row['coordinate'+axis] for axis in 'XYZ']))
    stars = {r['name']: r for r in rows if r['type'] == 'Star'}
    models = []
    for row in rows:
        if row['type'] not in ('Planet', 'Moon'):
            continue
        star = stars.get(row['parentStar'])
        if not star:
            raise ValueError('Missing star for '+row['name'])
        model = dict(name=row['name'], system=star['name'], radius_km=finite(row['bodyRadius']),
                     period_seconds=finite(row['rotationRate'])*3600,
                     correction_degrees=finite(row['rotationCorrection']), center_km=xyz(row),
                     quaternion=[finite(row['quaternion'+axis]) for axis in 'WXYZ'],
                     star_km=xyz(star), star_radius_km=finite(star['bodyRadius']))
        Body.from_record(model)
        models.append(model)
    by_name = {b['name']: b for b in models}
    sites = []
    excluded = {'space station', 'commarray', 'asteroid cluster', 'asteroid base', 'orbital laser platform'}
    for row in places:
        body = by_name.get(row['parentBody'])
        if not body or row['type'].lower() in excluded or row.get('private') == '1':
            continue
        if any(not row.get('coordinate'+axis, '').strip() for axis in 'XYZ'):
            continue  # Listed POI with no surveyed location; cannot forecast it.
        coords = xyz(row)
        height = math.sqrt(sum(v*v for v in coords))-body['radius_km']
        if height > max(150, body['radius_km']*.05):
            continue  # orbiting stations are not a surface sunrise destination
        Site(row['name'], tuple(coords))
        sites.append(dict(name=row['name'], body=body['name'], system=body['system'],
                          kind=row['type'], coordinates_km=coords))
    if not sites or len({(s['system'], s['body'], s['name']) for s in sites}) != len(sites):
        raise ValueError('Empty or duplicate daylight destinations')
    # Siege shares world time (CIG Inside CIG: Siege of Orison, ~08:00).
    # Do not invent platform coordinates: this is an explicitly labelled proxy.
    orison = next((s for s in sites if s['body'] == 'Crusader' and s['name'] == 'Orison'), None)
    if orison:
        sites.append(dict(orison, name='Siege of Orison (Orison reference)', kind='Event reference',
                          note='Uses Orison city coordinates and Crusader world time. Siege platform positions, horizon and current instance alignment still need field validation.'))
    signature = hashlib.sha256(json.dumps([models, sites], sort_keys=True).encode()).hexdigest()
    return dict(schema=1, source=SOURCE, signature=signature, bodies=models, sites=sites)


def validate_catalogue(data):
    if not isinstance(data, dict):
        raise ValueError('Daylight catalogue must be an object')
    if not isinstance(data.get('bodies'), list) or not isinstance(data.get('sites'), list):
        raise ValueError('Daylight catalogue needs body and destination tables')
    if data.get('schema') != 1 or not isinstance(data.get('signature'), str) or len(data['signature']) != 64:
        raise ValueError('Unsupported daylight catalogue')
    if not 1 <= len(data['bodies']) <= 1000 or not 1 <= len(data['sites']) <= 20000:
        raise ValueError('Unexpected daylight catalogue size')
    bodies = {}
    for row in data['bodies']:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= 256 for key in ('name','system')):
            raise ValueError('Invalid daylight body label')
        if row['name'] in bodies:
            raise ValueError('Duplicate body')
        bodies[row['name']] = Body.from_record(row)
    keys = set()
    for row in data['sites']:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= 256 for key in ('name','system','body')):
            raise ValueError('Invalid daylight destination label')
        if row['body'] not in bodies:
            raise ValueError('Destination has no body model')
        key = (row['system'], row['body'], row['name'])
        if key in keys:
            raise ValueError('Duplicate destination')
        keys.add(key)
        Site(row['name'], tuple(vector(row['coordinates_km'])))
    signature = hashlib.sha256(json.dumps([data['bodies'], data['sites']], sort_keys=True).encode()).hexdigest()
    if data['signature'] != signature:
        raise ValueError('Daylight catalogue signature mismatch')
    return data


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Daylight data exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'))


def load(directory):
    try:
        return validate_catalogue(read_json(Path(directory)/'daylight_catalogue.json'))
    except (OSError, ValueError, KeyError, TypeError):
        return validate_catalogue(read_json(BUNDLED))


def refresh(directory, opener=urllib.request.urlopen, now=None):
    texts = []
    for filename in ('bodies.csv', 'locations.csv'):
        request = urllib.request.Request(SOURCE+filename, headers={'User-Agent': 'SynthScan-Daylight/1.0'})
        with opener(request, timeout=12) as response:
            if response.geturl().split('/')[2] != 'dydrmr.github.io':
                raise ValueError('Unexpected daylight data host')
            content = response.read(MAX_BYTES+1)
        if len(content) > MAX_BYTES:
            raise ValueError('Daylight download exceeds size limit')
        texts.append(content.decode('utf-8-sig'))
    catalogue = validate_catalogue(parse_sources(*texts))
    catalogue['checked_at'] = time.time() if now is None else finite(now)
    atomic_json(Path(directory)/'daylight_catalogue.json', catalogue)
    return catalogue


def build_identity():
    try:
        from installation import game_directory
        from hangar_verification import installed_build
        game = game_directory()
        return installed_build(game) if game else None
    except (OSError, ValueError, KeyError):
        return None


def calibration(directory, catalogue, body_name, build, now=None):
    now = time.time() if now is None else finite(now)
    try:
        row = read_json(Path(directory)/'daylight_calibration.json')[body_name]
        age = now-finite(row['at'])
        offset = finite(row['phase_offset'])
        if abs(offset) > math.pi or not build or row['build'] != build['fingerprint']:
            raise ValueError('Game build changed')
        if row['signature'] != catalogue['signature'] or not 0 <= age <= 7*86400:
            raise ValueError('Calibration expired or model changed')
        return offset, 'Local observation · '+time.strftime('%b %d', time.localtime(row['at']))
    except (OSError, ValueError, KeyError, TypeError):
        patch = ' for '+build['patch'] if build else ''
        return 0.0, 'Community estimate · not calibrated'+patch


def save_observation(directory, catalogue, row, build, at, kind):
    if not build:
        raise ValueError('Locate the installed game before recording a patch-specific observation')
    body = Body.from_record(next(b for b in catalogue['bodies'] if b['name'] == row['body']))
    site = Site(row['name'], tuple(vector(row['coordinates_km'])))
    offset = observed_phase(body, site, at, kind)
    path = Path(directory)/'daylight_calibration.json'
    try:
        previous = read_json(path)
        if not isinstance(previous, dict):
            raise ValueError('Invalid saved calibration; no observations overwritten')
    except FileNotFoundError:
        previous = {}
    previous[row['body']] = dict(at=finite(at), kind=kind, site=row['name'], phase_offset=offset,
                                 build=build['fingerprint'], signature=catalogue['signature'])
    atomic_json(path, previous)
