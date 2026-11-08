"""Background source checks. A download is never treated as an applied update.

Only public metadata is requested; no player/account data leaves this service.
Community code is compared as data, never imported or executed.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import subprocess
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from telemetry_ipc import read_shared_json, publish_json

ROOT = Path(__file__).resolve().parent
INTERVAL = 6 * 3600
RETRY = 300
LIMIT = 4 * 1024 * 1024
TABLES = ('MiningData.h', 'MiningHardware.h', 'CraftingData.h', 'RefiningData.h', 'RefineryData.h')


def optional_json(path, limit=1024*1024):
    try:
        data=read_shared_json(path,limit=limit)
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}


def stamp(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 else 0


def feed_entries(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Unsupported release feed')
    root=ET.fromstring(raw)
    if root.tag!='{http://www.w3.org/2005/Atom}feed':raise ValueError('Unexpected release feed')
    entries=root.findall('{http://www.w3.org/2005/Atom}entry')
    if not entries:raise ValueError('Empty release feed')
    return entries


def version_key(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:[-.]([A-Za-z0-9.-]+))?',value)
    if not match:raise ValueError('Unsupported release version')
    suffix=match[4]
    parts=tuple((1,int(p)) if p.isdigit() else (0,p.lower()) for p in re.split('[.-]',suffix or ''))
    return (*map(int,match.groups()[:3]),int(suffix is None),parts)


def download(url, opener=urllib.request.urlopen, limit=LIMIT):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'SynthScan-DataUpdates/1.0', 'Cache-Control': 'no-cache',
        'Accept': 'application/json, text/plain, text/html;q=0.5'})
    with opener(request, timeout=12) as response:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.netloc != urlsplit(url).netloc:
            raise ValueError('Unexpected update source redirect')
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Update metadata exceeds size limit')
    return raw


def check_bedrock():
    pinned = json.loads((ROOT / 'native/synthscan-upstream.json').read_text(encoding='utf-8'))
    # Resolve one revision first, so all file comparisons describe the same tree.
    # Public Atom feeds avoid GitHub API token requirements and shared-IP API
    # rate limits. Every table is then pinned to this exact commit.
    entry=feed_entries(download('https://github.com/SC-Ravaxx/Bedrock/commits/HEAD.atom'))[0]
    identity=entry.findtext('{http://www.w3.org/2005/Atom}id','')
    match=re.search(r'(?:/|:)([a-f0-9]{40})$',identity)
    revision=match[1] if match else ''
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Upstream revision is unavailable')
    changed = []
    for name in TABLES:
        try:raw = download(f'https://raw.githubusercontent.com/SC-Ravaxx/Bedrock/{revision}/include/{name}',limit=16*1024*1024)
        except urllib.error.HTTPError as error:
            if error.code==404:
                changed.append(name+' (removed)');continue
            raise
        if hashlib.sha256(raw).hexdigest() != pinned['files']['include/' + name]:
            changed.append(name)
    code_changed=revision!=pinned['commit']
    return dict(status='review_required' if changed or code_changed else 'unchanged', revision=revision,
        installed_revision=pinned['commit'], changed_tables=changed,
        detail=('New upstream tables need integration: ' + ', '.join(changed)) if changed else
               ('Monitored tables match our pinned source; newer upstream application code is available for review.' if code_changed else
                'Monitored upstream tables match our pinned source. Installed-patch compatibility is checked separately.'),
        url='https://github.com/SC-Ravaxx/Bedrock')


def check_scmdb():
    text = download('https://scmdb.net/').decode('utf-8-sig')
    if not re.search(r'<title>[^<]*SCMDB', text, re.I):
        raise ValueError('SCMDB returned an unexpected page')
    assets = sorted(set(re.findall(r'(?:src|href)=["\x27]([^"\x27]*assets/[^"\x27]+\.js)["\x27]', text)))
    if not assets:
        raise ValueError('SCMDB release metadata is unavailable')
    return dict(status='unverified', revision=hashlib.sha256('\n'.join(assets).encode()).hexdigest(),
        detail='Website revision observed. No supported game-data feed is configured; LIVE/PTU data freshness cannot be verified automatically.',
        url='https://scmdb.net/')


def check_extractor():
    entry=feed_entries(download('https://github.com/diogotr7/StarBreaker/releases.atom'))[0]
    identity=entry.findtext('{http://www.w3.org/2005/Atom}id','')
    tag=identity.rsplit('/',1)[-1]
    if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?', tag):
        raise ValueError('Unexpected extractor version')
    return dict(status='unchanged' if tag.lstrip('v') == '0.3.2' else 'review_required', revision=tag,
        detail='Using pinned StarBreaker v0.3.2. New extractor releases require compatibility checks before adoption.',
        url='https://github.com/diogotr7/StarBreaker/releases')


def check_app_release():
    from setup_status import version
    entry=feed_entries(download('https://github.com/Synthronaut/Synthscan/releases.atom'))[0]
    identity=entry.findtext('{http://www.w3.org/2005/Atom}id','')
    tag=identity.rsplit('/',1)[-1];installed=version()
    if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?',tag):raise ValueError('Unexpected app release version')
    current=installed!='development' and version_key(installed)>=version_key(tag)
    return dict(status='unchanged' if current else ('development' if installed=='development' else 'release_available'),
        revision=tag,detail=f'Installed: {installed}. Latest published release: {tag}. Install app releases from SynthScan Releases.',
        url='https://github.com/Synthronaut/Synthscan/releases')


def local_reference_status():
    from installation import game_directory, output_root
    from reference_catalogs import catalogue_path
    try:
        build = json.loads((game_directory(True) / 'build_manifest.id').read_text(encoding='utf-8'))['Data']
    except (OSError, ValueError, KeyError):
        return dict(status='unavailable', detail='Choose the installed Star Citizen folder in Setup & reputation.')
    try:
        data = json.loads(catalogue_path(output_root(), 'local_game_catalog.json').read_text(encoding='utf-8'))
        provenance = data.get('native_provenance', {})
        same = provenance.get('build', {}).get('BuildId') == build['BuildId']
        complete = same and provenance.get('export_schema') == 2
        library=json.loads(catalogue_path(output_root(),'local_game_library.json').read_text(encoding='utf-8'))
        complete=complete and library.get('provenance',{}).get('weapon_stats_schema')==1 and library.get('provenance',{}).get('ship_stats_schema')==2 and library.get('provenance',{}).get('build',{}).get('BuildId')==build['BuildId']
        partial = bool(provenance.get('failures') or provenance.get('unmatched_entries') or provenance.get('ambiguous_entries'))
        return dict(status=('partial' if partial else 'current') if complete else 'refresh_required', build=build['BuildId'],
            patch=build.get('Branch', ''), enriched=provenance.get('enriched_entries', 0),
            detail=(f"Local recipes rebuilt: {provenance.get('enriched_entries',0)} matched, {len(provenance.get('added_entries',[]))} added, {len(provenance.get('failures',[]))} undecoded. Older unmatched references remain labelled. Native tables and unlock annotations have separate status."
                    if complete else 'Local references need rebuilding for this game build or exporter version. Saved records are preserved.'))
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status='refresh_required', build=build['BuildId'], patch=build.get('Branch', ''),
                    detail='No complete local reference generation is available. Rebuild local references.')


class DataUpdateService:
    def __init__(self, directory, checks=None, local_check=local_reference_status,exclusive=False):
        self.directory = Path(directory)
        self.path = self.directory / 'data_update_status.json'
        self.checks = checks if checks is not None else {'bedrock':check_bedrock,'extractor':check_extractor}
        self.app_updates=None;self.reference_sources=None
        if checks is None:
            from app_updates import AppUpdateService
            from reference_sources import ReferenceSourceService
            self.app_updates=AppUpdateService(directory);self.reference_sources=ReferenceSourceService(directory)
        self.local_check = local_check
        saved = optional_json(self.path)
        self.rows = saved.get('sources', {})
        if not isinstance(self.rows, dict): self.rows = {}
        self.rows={k:v for k,v in self.rows.items() if k in self.checks and isinstance(v,dict)}
        for row in self.rows.values():
            for key in ('checked_at','last_success_at'):row[key]=stamp(row.get(key,0))
        self.pool = None
        self.futures = {}
        self.attempts = {}
        self.local = {}
        self.next_local = 0
        self.last_command = saved.get('last_command','')
        self.refresh_future = None
        self.refresh_attempted = -float('inf')
        self.refresh_result = ''
        self.exclusive=exclusive;self.lock=None

    def tick(self, now=None, force=False, game_running=True):
        if self.exclusive and self.lock is None:
            from app_lifecycle import SingleInstance
            lock=SingleInstance('data-updates')
            if not lock.acquired:
                lock.close();return optional_json(self.path)
            self.lock=lock
        now = time.time() if now is None else now
        command = optional_json(self.directory / 'data_update_command.json')
        if command.get('id') != self.last_command and 0 <= now-stamp(command.get('at', 0)) < 60:
            self.last_command = command.get('id', '')
            force = True
        if now >= self.next_local or force:
            self.next_local = now + 30
            try:
                self.local = self.local_check()
                if not isinstance(self.local,dict):raise ValueError('Invalid local reference status')
            except (OSError,ValueError,TypeError,KeyError):
                self.local=dict(status='unavailable',detail='Local reference status could not be read. Existing catalogs were not changed.')
        if self.refresh_future is not None and self.refresh_future.done():
            try:
                code=self.refresh_future.result()
                self.refresh_result='References rebuilt. The item directory reloads automatically; other compiled tables require an app release.' if code==0 else 'Reference rebuild deferred or failed; see reference_refresh.log. Existing references retained.'
            except Exception:self.refresh_result='Reference rebuild failed; existing references retained.'
            self.refresh_future=None;self.next_local=0
        if self.local.get('status')=='refresh_required' and not game_running and self.refresh_future is None and now-self.refresh_attempted>=RETRY:
            self.refresh_attempted=now
            if self.pool is None:self.pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix='data-updates')
            self.refresh_future=self.pool.submit(rebuild_references,self.directory)
        for name, check in self.checks.items():
            future = self.futures.get(name)
            if future is not None and future.done():
                previous = self.rows.get(name, {})
                try:
                    result = future.result()
                    if not isinstance(result, dict) or not result.get('status'): raise ValueError('Invalid source result')
                    self.rows[name] = dict(result, checked_at=now, last_success_at=now,
                        previous_revision=previous.get('revision', ''),
                        source_changed=bool(previous.get('revision') and previous['revision'] != result.get('revision')))
                except Exception as exc:
                    self.rows[name] = dict(previous, status='unavailable', checked_at=now,
                        error=type(exc).__name__, detail='Update source unavailable; last known references retained. Freshness is not confirmed.')
                del self.futures[name]
            row = self.rows.get(name, {})
            age = now-row.get('checked_at', 0)
            interval = RETRY if row.get('status') == 'unavailable' else INTERVAL
            if name not in self.futures and now-self.attempts.get(name, -float('inf')) >= 30 and (force or not 0 <= age < interval):
                self.attempts[name] = now
                if self.pool is None: self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='data-updates')
                self.futures[name] = self.pool.submit(check)
        checking=list(self.futures)
        if self.app_updates:
            self.rows['synthscan']=self.app_updates.tick(game_running,force)
            if self.app_updates.future is not None:checking.append('synthscan')
        if self.reference_sources:
            self.rows['scmdb']=self.reference_sources.tick(force)
            if self.reference_sources.future is not None:checking.append('scmdb')
        snapshot = dict(schema=1, at=now, local=self.local, sources=self.rows, checking=checking,last_command=self.last_command,
            rebuilding=self.refresh_future is not None,refresh_result=self.refresh_result,
            deferred=bool(game_running and self.local.get('status')=='refresh_required'))
        publish_json(self.path, snapshot)
        return snapshot

    def close(self):
        if self.app_updates:self.app_updates.close()
        if self.reference_sources:self.reference_sources.close()
        if self.pool: self.pool.shutdown(wait=False, cancel_futures=True)
        if self.lock:self.lock.close();self.lock=None


def status_lines(directory, now=None):
    now = time.time() if now is None else now
    state = optional_json(Path(directory) / 'data_update_status.json')
    lines = []
    application=optional_json(Path(directory)/'app_update_status.json')
    if application:
        lines+=['Automatic application updates — '+str(application.get('status','unknown')).replace('_',' '),str(application.get('detail','')),
                'Installed: '+str(application.get('installed_version','unknown'))]
        last=application.get('last_install') or {}
        if last:lines+=['Last activation: '+str(last.get('phase','unknown'))+' · '+str(last.get('version','unknown'))]
        lines+=['']
    native_source=optional_json(Path(directory)/'mining_reference_status.json')
    if native_source:lines+=['Native mining reference — '+str(native_source.get('status','unknown')),str(native_source.get('detail','')), '']
    catalog=optional_json(Path(directory)/'item_directory_catalog.json')
    if catalog:
        lines+=['Item directory — automatic local refresh',
                'Catalog: '+str((catalog.get('build') or {}).get('Branch','unknown')),
                'Updated: '+time.strftime('%Y-%m-%d %H:%M',time.localtime(stamp(catalog.get('updated_at',0)))),
                'Item/component shop prices refresh daily; ship purchase prices and the vehicle index refresh every 12 hours. Results cache offline.',
                'Vehicles indexed: '+str(catalog.get('vehicles',0))+' · checked '+(time.strftime('%Y-%m-%d %H:%M',time.localtime(stamp(catalog.get('vehicles_checked_at',0)))) if catalog.get('vehicles_checked_at') else 'waiting for first successful download'),
                'Reported patch and age appear with each shop quote.', '']
    local = state.get('local', {})
    if not isinstance(local,dict):local={}
    if local:
        lines += ['Installed game: ' + local.get('patch', 'Unknown'),
                  'Local references — ' + str(local.get('status', 'unavailable')).replace('_', ' '), str(local.get('detail', '')), '']
    try:
        native=json.loads((ROOT/'data/mining_hardware.json').read_text(encoding='utf-8'))['provenance']
        lines += ['Bundled native mining / crafting tables — reference data',
            'Bundled mining hardware patch: '+native.get('game_version','unknown')+'. Matching SCMDB updates replace numeric mining stats; new equipment identities and calculation changes arrive in signed app releases.', '']
    except (OSError,ValueError,KeyError,TypeError):
        lines += ['Bundled native tables — version unavailable','']
    if state.get('rebuilding'):lines+=['Rebuilding references in the background…','']
    elif state.get('deferred'):lines+=['Local rebuild will start after Star Citizen closes.','']
    elif state.get('refresh_result'):lines += [state['refresh_result'],'']
    names = {'synthscan':'SynthScan application','bedrock': 'Bedrock mining / crafting tables', 'scmdb': 'SCMDB', 'extractor': 'Game-file extractor'}
    sources=state.get('sources',{})
    if not isinstance(sources,dict):sources={}
    for key, name in names.items():
        row = sources.get(key, {})
        if not isinstance(row,dict):row={}
        checked = stamp(row.get('checked_at', 0))
        stale = not 0 <= now-checked < INTERVAL
        status = 'checking' if key in (state.get('checking') or []) else ('check overdue' if stale else str(row.get('status', 'not checked')).replace('_', ' '))
        lines += [name + ' — ' + status, str(row.get('detail', 'Waiting for the first background check.'))]
        if checked: lines.append('Last check: ' + time.strftime('%Y-%m-%d %H:%M', time.localtime(checked)))
        lines.append('')
    hangar = optional_json(Path(directory) / 'hangar_update_status.json')
    fresh = 0 <= now-stamp(hangar.get('at', 0)) < 15
    lines += ['Contested-zone Executive Hangars — ' + (hangar.get('reason', 'Awaiting background sync') if fresh else 'background status unavailable'),
              'Timing source: ' + (hangar.get('source_modified') or 'unknown')]
    for key, label in [('fetched_at', 'Schedule checked'), ('reset_checked_at', 'Official reset feed checked')]:
        checked_stamp = stamp(hangar.get(key, 0))
        lines.append(label + ': ' + (time.strftime('%Y-%m-%d %H:%M', time.localtime(checked_stamp)) if checked_stamp else 'not yet confirmed'))
    return '\n'.join(lines)


def rebuild_references(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    with (directory/'reference_refresh.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-B',str(ROOT/'reference_update.py')],cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,timeout=2400,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    return result.returncode
