"""Verified feature downloads and reproducible, immutable app assemblies.

Only a signed catalog can authorize executable files. Selection is local; the
server receives ordinary public asset requests, never this PC's player data.
Activation uses the normal application transaction and keeps its rollback.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import tempfile
import time
import zipfile

from app_updates import (MAX_ARCHIVE, MAX_UNPACKED, HEX, allowed_url, digest,
                         load, request, safe_member, version_key, write)
from feature_modules import FEATURES, installed, resolve, RETIRED
from update_signing import canonical, strict_json, verify

SCHEMA = 1
MANIFEST = 'component.json'
# Only recognition may replace the screen-free native engine. These files are
# supplied by the same signed release, not arbitrary user-selected overlays.
REPLACEMENTS = {'dist/native/SynthScan.exe', 'dist/native/build_manifest.json'}


def catalog(raw, trust, now=None):
    now = time.time() if now is None else now
    value = verify(raw, trust)
    if value.get('schema') != 1 or value.get('kind') != 'modules' or value.get('platform') != 'windows-x64':
        raise ValueError('Unsupported module catalog')
    version_key(value.get('version'))
    if type(value.get('sequence')) is not int or value['sequence'] <= 0:
        raise ValueError('Invalid catalog sequence')
    if not all(type(value.get(k)) in (int, float) for k in ('issued_at', 'expires_at')) or not 0 < value['issued_at'] <= now + 300 or not now < value['expires_at'] <= value['issued_at'] + 2 * 366 * 86400:
        raise ValueError('Module catalog is expired or has an invalid date')
    if value.get('minimum_manager', 1) > SCHEMA: raise ValueError('Install a newer SynthScan to use these modules')
    packages = value.get('packages')
    if not isinstance(packages, dict) or not {'core', *FEATURES}.issubset(packages) or len(packages)>64:
        raise ValueError('Catalog has an incomplete or unknown feature set')
    for name, item in packages.items():
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',name):raise ValueError('Invalid module identity')
        if not isinstance(item, dict) or item.get('id') != name or item.get('version') != value['version']:
            raise ValueError('Incompatible module version')
        for key, limit in [('size', MAX_ARCHIVE), ('unpacked_size', MAX_UNPACKED)]:
            if type(item.get(key)) is not int or not 0 < item[key] <= limit: raise ValueError('Invalid module size')
        if not HEX.fullmatch(str(item.get('sha256', ''))): raise ValueError('Invalid module checksum')
        if not HEX.fullmatch(str(item.get('inventory_sha256', ''))): raise ValueError('Invalid module inventory checksum')
        dependencies=item.get('requires',[])
        if not isinstance(dependencies,list) or any(not isinstance(v,str) or v not in packages or v in (name,'core') for v in dependencies) or len(dependencies)>32:raise ValueError('Invalid module dependencies')
        expected = [] if name == 'core' else list(FEATURES[name][1]) if name in FEATURES else dependencies
        if dependencies != expected: raise ValueError('Incompatible module dependencies')
        allowed_url(item.get('url', ''), trust)
    return value


def check_sequence(folder, value, raw):
    previous = load(Path(folder) / 'catalog-sequence.json')
    fingerprint = hashlib.sha256(raw).hexdigest()
    if value['sequence'] < previous.get('sequence', 0) or (value['sequence'] == previous.get('sequence') and previous.get('sha256') != fingerprint):
        raise ValueError('Catalog rollback or sequence reuse rejected')
    return dict(sequence=value['sequence'], sha256=fingerprint)


def inspect_package(path, item, destination=None, occupied=None):
    """Verify all contents before extraction; reject Windows path aliases/links."""
    if Path(path).stat().st_size != item['size'] or digest(path) != item['sha256']:
        raise ValueError('Module archive changed: ' + item['id'])
    with zipfile.ZipFile(path) as zipped:
        members = {}; folded = set(); total = 0
        for member in zipped.infolist():
            if member.is_dir(): continue
            relative = safe_member(member.filename)
            if relative.casefold() in folded: raise ValueError('Duplicate module path')
            if stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG) or member.external_attr & 0x400 or member.flag_bits & 1:
                raise ValueError('Unsupported module archive member')
            folded.add(relative.casefold()); members[relative] = member; total += member.file_size
        if len(members) > 50000 or total != item['unpacked_size'] or total > MAX_UNPACKED:
            raise ValueError('Invalid unpacked module size')
        if MANIFEST not in members or members[MANIFEST].file_size > 8 * 1024 * 1024:
            raise ValueError('Module has no bounded integrity inventory')
        inventory = strict_json(zipped.read(members[MANIFEST]))
        if hashlib.sha256(zipped.read(members[MANIFEST])).hexdigest()!=item['inventory_sha256']:raise ValueError('Module inventory authentication failed')
        files = inventory.get('files')
        if inventory.get('schema') != 1 or inventory.get('id') != item['id'] or inventory.get('version') != item['version'] or not isinstance(files, dict) or set(files) != set(members) - {MANIFEST}:
            raise ValueError('Module inventory does not match its catalog')
        for relative, expected in files.items():
            if not HEX.fullmatch(str(expected)): raise ValueError('Invalid module file digest')
            if relative in {'active_version.txt', 'activation_pending.txt', 'release_integrity.json', 'module_lock.json'} or relative.startswith('versions/'):
                raise ValueError('Module attempts to write application activation state')
            prior = (occupied or {}).get(relative.casefold())
            if prior is not None and (item['id'] != 'mining_recognition' or relative not in REPLACEMENTS):
                raise ValueError('Conflicting module files: ' + relative)
        # Hash without loading large native DLLs/models into memory.
        for relative, expected in files.items():
            h = hashlib.sha256()
            with zipped.open(members[relative]) as stream:
                while block := stream.read(1024 * 1024): h.update(block)
            if h.hexdigest() != expected: raise ValueError('Module file checksum mismatch: ' + relative)
        if destination is not None:
            for relative in files:
                target = Path(destination) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                # Destination is a fresh private staging tree, never a profile.
                with zipped.open(members[relative]) as source, target.open('wb') as output: shutil.copyfileobj(source, output)
                if occupied is not None: occupied[relative.casefold()] = item['id']
        return inventory


def fetch_catalog(root, directory, trust=None, opener=request, now=None):
    from app_updates import config
    trust = trust or config(root)
    url = trust.get('modules_manifest_url')
    if not url: raise ValueError('This installation has no trusted module channel')
    with opener(url, trust) as response: raw = response.read(256 * 1024 + 1)
    value = catalog(raw, trust, now)
    folder = Path(directory) / 'updates'; folder.mkdir(parents=True, exist_ok=True)
    sequence = check_sequence(folder, value, raw)
    path = folder / ('catalog-' + sequence['sha256'] + '.json')
    if not path.exists(): path.write_bytes(raw)
    write(folder / 'catalog-sequence.json', sequence)
    return value, sequence['sha256']


def selection_token(catalog_hash, selected):
    return hashlib.sha256(canonical(dict(schema=1, catalog=catalog_hash, modules=resolve(selected)))).hexdigest()


def prepare(root, directory, selected=None, trust=None, opener=request, progress=lambda text: None, now=None):
    """Download first; failed downloads leave the active app and choice intact."""
    from app_updates import config
    trust = trust or config(root)
    value, catalog_hash = fetch_catalog(root, directory, trust, opener, now)
    if version_key(value['version']) < version_key(load(Path(root) / 'release.json').get('version', '0.0.0')):
        raise ValueError('Module catalog is older than the installed application')
    automatic=selected is None
    selected = resolve(installed(root) if automatic else selected)
    token = selection_token(catalog_hash, selected)
    if load(Path(root) / 'module_lock.json').get('token') == token:
        return dict(status='current', version=value['version'], detail='Selected features are up to date.')
    if automatic and load(Path(directory)/'updates/failed.json').get('sha256')==token:
        return dict(status='rejected',version=value['version'],detail='This assembly failed readiness. Keeping the working app until a corrected release or an explicit feature retry.')
    folder = Path(directory) / 'updates'; cache = folder / 'modules-cache'; cache.mkdir(exist_ok=True)
    items = [value['packages'][name] for name in ['core', *selected]]
    if sum(v['unpacked_size'] for v in items) > MAX_UNPACKED: raise ValueError('Selected installation exceeds size limit')
    needed = sum(v['size'] + v['unpacked_size'] for v in items)
    if shutil.disk_usage(folder).free < needed + 128 * 1024 * 1024: raise OSError('Not enough free space to download and prepare selected features')
    for item in items:
        archive = cache / (item['sha256'] + '.zip')
        if not archive.exists() or archive.stat().st_size != item['size'] or digest(archive) != item['sha256']:
            progress('Downloading ' + ('Core' if item['id'] == 'core' else FEATURES[item['id']][0]) + '…')
            fd, name = tempfile.mkstemp(prefix='download-', suffix='.part', dir=cache)
            try:
                h = hashlib.sha256(); received = 0
                with os.fdopen(fd, 'wb') as stream, opener(item['url'], trust) as response:
                    while block := response.read(1024 * 1024):
                        received += len(block)
                        if received > item['size']: raise ValueError('Module download exceeds its declared size')
                        h.update(block); stream.write(block)
                    stream.flush(); os.fsync(stream.fileno())
                if received != item['size'] or h.hexdigest() != item['sha256']: raise ValueError('Module download checksum mismatch')
                os.replace(name, archive)
            finally:
                if os.path.exists(name): os.unlink(name)
        inspect_package(archive, item)
    # The detached updater verifies this catalog and these archives again.
    plan = dict(schema=1, kind='modules', sha256=token, catalog=catalog_hash, modules=selected, version=value['version'])
    write(folder / 'pending.json', plan)
    progress('Downloads verified. Close Star Citizen and SynthScan windows to apply safely.')
    return dict(status='staged', version=value['version'], detail='Selected features downloaded and verified; activation waits until the game and app windows are idle.')


def activation_payload(current, directory, pending, trust=None, now=None):
    from app_updates import config
    trust = trust or config(current); folder = Path(directory) / 'updates'
    catalog_hash = pending.get('catalog', '')
    if not HEX.fullmatch(str(catalog_hash)): raise ValueError('Invalid staged module catalog identity')
    raw = (folder / ('catalog-' + catalog_hash + '.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != catalog_hash: raise ValueError('Staged module catalog changed')
    value = catalog(raw, trust, now); check_sequence(folder, value, raw)
    selected = resolve(pending.get('modules'))
    token = selection_token(catalog_hash, selected)
    if token != pending.get('sha256'):
        retired=set(pending['modules'])&RETIRED
        legacy=hashlib.sha256(canonical(dict(schema=1,catalog=catalog_hash,modules=sorted(set(selected)|retired)))).hexdigest()
        if not retired or legacy!=pending.get('sha256'):raise ValueError('Module selection changed after staging')
        token=legacy
    if version_key(value['version']) < version_key(load(Path(current) / 'release.json').get('version', '0.0.0')): raise ValueError('Staged modules would downgrade the app')
    items = [value['packages'][name] for name in ['core', *selected]]
    total = sum(i['unpacked_size'] for i in items)
    if total > MAX_UNPACKED: raise ValueError('Installation exceeds size limit')
    for item in items: inspect_package(folder / 'modules-cache' / (item['sha256'] + '.zip'), item)

    def unpack(destination):
        occupied = {}
        for item in items:
            inspect_package(folder / 'modules-cache' / (item['sha256'] + '.zip'), item, destination, occupied)
        release = load(Path(destination) / 'release.json')
        if release.get('version') != value['version'] or release.get('module_schema') != 1: raise ValueError('Core package is not compatible with the selected modules')
        release.update(modules=selected, selection_configured=True, edition='full' if 'mining_recognition' in selected else 'standard', screen_reading='mining_recognition' in selected)
        write(Path(destination) / 'release.json', release)
        write(Path(destination) / 'module_lock.json', dict(schema=1, token=token, catalog=catalog_hash, modules=selected, packages={i['id']: i['sha256'] for i in items}))
        # Standard editions cannot carry screen-reader components, including
        # latent dependencies accidentally left by a prior Full installation.
        if 'mining_recognition' not in selected:
            from edition_payload import forbidden_standard_path
            if any(forbidden_standard_path(p.relative_to(destination).as_posix()) for p in Path(destination).rglob('*') if p.is_file()): raise ValueError('Screen-reading components leaked into a screen-free assembly')
        integrity = {p.relative_to(destination).as_posix(): digest(p) for p in sorted(Path(destination).rglob('*')) if p.is_file()}
        write(Path(destination) / 'release_integrity.json', dict(version=value['version'], files=integrity))

    return dict(version=value['version'], sha256=token, unpacked_size=total, kind='modules'), unpack
