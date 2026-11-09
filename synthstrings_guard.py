"""Local patch protection. No account access, network requests or game control.

An old full localization override must be removed before waiting for a patch to
settle. Recovery never installs an old full pack over a newer game build.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
import uuid

from installation import PROFILE, game_directory, valid_game
from game_text_lifecycle import Manager, INI, digest, load, save
from localization_lock import localization_lock

SETTLE_SECONDS = 120
MAX_TEXT = 64 * 1024 * 1024


def snapshot(game):
    """Cheap channel-specific identity, including manifest and archive edges.

    Size/mtime alone miss same-size builds and replaced installations. Extraction
    additionally bypasses the native text cache and checks this identity again.
    This is change detection, not a cryptographic hash of the entire archive.
    """
    game = Path(game).resolve()
    manifest = (game / 'build_manifest.id').read_bytes()
    if len(manifest) > 1024 * 1024:
        raise ValueError('Game build manifest exceeds the supported size')
    data = json.loads(manifest.decode('utf-8-sig'))['Data']
    build = str(data.get('BuildId') or data.get('RequestedP4ChangeNum') or '')
    if not build:
        raise ValueError('Game build identity is unavailable')
    archive = game / 'Data.p4k'
    with archive.open('rb') as stream:
        stat = os.fstat(stream.fileno())
        head = stream.read(65536)
        stream.seek(max(0, stat.st_size - 65536))
        tail = stream.read(65536)
        end = os.fstat(stream.fileno())
    identity = lambda s: (s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino)
    if identity(stat) != identity(end) or (game / 'build_manifest.id').read_bytes() != manifest:
        raise ValueError('Game files are changing during the patch check')
    facts = dict(game=os.path.normcase(str(game)), build=build,
                 manifest=digest(manifest), archive=list(identity(stat)),
                 edges=digest(head + tail))
    return dict(fingerprint=digest(json.dumps(facts, sort_keys=True).encode()),
                build=build, version=str(data.get('Version', '')),
                archive_mtime=stat.st_mtime, facts=facts)


def validate_render(base, rendered, min_keys=1000):
    """The output must contain every current CIG value, unchanged or appended to.

    Compare against a fresh baseline returned by the same extraction, not the
    installed override. Duplicate aliases, truncation and invalid UTF-8 fail shut.
    """
    def rows(raw):
        if not raw or len(raw) > MAX_TEXT or b'\0' in raw:
            raise ValueError('Localization is empty, oversized or contains NUL bytes')
        result = raw.decode('utf-8-sig').replace('\r\n', '\n').split('\n')
        if result[-1] == '':
            result.pop()
        return result
    original, candidate = rows(base), rows(rendered)
    if (base.startswith(b'\xef\xbb\xbf') != rendered.startswith(b'\xef\xbb\xbf') or
            not candidate or not candidate.pop().startswith('bedrock_game_texts=') or
            len(original) != len(candidate)):
        raise ValueError('Generated localization does not cover the complete current game text')
    changed = 0;keys = set()
    for line, new_line in zip(original, candidate):
        key, sep, value = line.partition('=')
        # CIG itself has shipped physical continuation rows. Preserve opaque
        # rows, comments and spacing exactly instead of trying to repair them.
        if not sep or not key or key != key.strip() or line.lstrip().startswith((';', '#')):
            if new_line != line:
                raise ValueError('Generated localization changed an original CIG row')
            continue
        normalized = key.casefold().removesuffix(',p')
        if normalized in keys or normalized == 'bedrock_game_texts':
            raise ValueError('Duplicate localization key or alias')
        keys.add(normalized)
        new_key, new_sep, new_value = new_line.partition('=')
        if new_key != key or not new_sep or not new_value.startswith(value):
            raise ValueError('Generated localization changed an original CIG value')
        changed += new_value != value
    if len(keys) < min_keys:
        raise ValueError('Current game text is unexpectedly small or incomplete')
    return dict(keys=len(keys), annotated=changed, source_sha256=digest(base),
                output_sha256=digest(rendered))


def current_pids():
    from app_lifecycle import game_process_ids
    return sorted(game_process_ids())


def record(manager, state, title, detail, source=None, affected=(), now=None, reason=''):
    """Persist transitions, including successes, without clearing restart debt."""
    now = time.time() if now is None else now
    path = manager.folder / 'guard_status.json'
    old = load(path)
    fingerprint = (source or {}).get('fingerprint', '')
    same = (old.get('state'), old.get('fingerprint'), old.get('detail')) == (state, fingerprint, detail)
    event = old.get('event_id') if same else hashlib.sha256(
        f'{manager.game}:{state}:{fingerprint}:{now}'.encode()).hexdigest()[:20]
    history = old.get('history', [])[-19:]
    if not same:
        history.append(dict(at=now, state=state, build=(source or {}).get('build', ''), title=title,detail=detail,reason=reason))
    try:
        suspended_pids = manager.read().get('files', {}).get(INI, {}).get('suspended_game_pids', [])
    except (OSError, ValueError, TypeError):
        suspended_pids = []
    value = dict(schema=1, game=str(manager.game), channel=manager.game.name,
                 state=state, title=title, detail=detail, fingerprint=fingerprint,reason=reason,
                 build=(source or {}).get('build', ''), version=(source or {}).get('version', ''),
                 event_id=event, at=old.get('at', now) if same else now,
                 affected_game_pids=sorted(set(old.get('affected_game_pids', [])) | set(affected) | set(suspended_pids)),
                 history=history)
    save(path, value)
    return value


def channels(profile=PROFILE):
    """Only known installations, their game channels and ownership journals."""
    found = set()
    try:
        configured = load(Path(profile) / 'installation.json').get('game_dir')
        if configured and valid_game(configured):
            game = Path(configured).resolve()
        elif Path(profile).resolve() == PROFILE.resolve():
            game = game_directory(True)
        else:
            raise FileNotFoundError('No game configured in this profile')
        found.add(game.resolve())
        for sibling in game.parent.iterdir():
            if sibling.is_dir() and (sibling / 'Data.p4k').is_file() and (sibling / 'build_manifest.id').is_file():
                found.add(sibling.resolve())
    except (OSError, ValueError, KeyError):
        pass
    for journal in (Path(profile) / 'game_text').glob('*/journal.json'):
        try:
            game = Path(load(journal)['game']).resolve()
            manager = Manager(game, profile)
            if manager.journal == journal.resolve():
                manager.read()
                found.add(game)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(found, key=str)


def inspect_channel(game, profile=PROFILE, now=None, pids=None, settled=False):
    """Fast protection first; return a rebuild job only after the patch settles."""
    now = time.time() if now is None else now
    pids = current_pids() if pids is None else pids
    manager = Manager(game, profile)
    with localization_lock(manager.game / INI, timeout_ms=100):
        state = manager.read()
        ini = manager.target(INI)
        if not state and not ini.exists():
            return None  # Never opt a player into SynthStrings automatically.
        if not state and ini.exists():
            raw = ini.read_bytes()
            if b'bedrock_game_texts=' not in raw and b'<EM4>BLUEPRINTS</EM4>' not in raw:
                return None  # Unrelated language packs are outside this feature.
        if state and not state.get('enabled', True):
            record(manager, 'disabled', 'SynthStrings is off', 'Your SynthStrings preference is off.', now=now)
            return None
        if state.get('phase') == 'conflict':
            record(manager, 'attention', 'Some game-text changes could not be restored',
                   'A previous removal found edits it could not safely undo. Open Text settings to review the recorded conflict; your current file has been preserved.', now=now,reason='cleanup_conflict')
            return None
        entry = state.get('files', {}).get(INI, {})
        try:
            source = snapshot(game)
        except (OSError, ValueError, KeyError, TypeError) as error:
            removed = manager.suspend(pids)
            record(manager, 'fallback' if removed or not ini.exists() else 'attention',
                   'SynthStrings is waiting for the game files',
                   'The game build cannot be verified. ' +
                   ('Packaged game text will be used.' if not ini.exists() else 'An externally owned localization file was preserved; open Setup.') +
                   ' ' + str(error), affected=pids if removed else (), now=now)
            return None
        if ini.exists() and not re.search(rb'(?m)^bedrock_game_texts=',ini.read_bytes().lstrip(b'\xef\xbb\xbf')):
            raw=ini.read_bytes()
            if entry.get('last_sha256')==digest(raw):
                observed=entry.get('observed_source')
                if not observed:
                    entry['observed_source']=source;manager.store(state)
                changed=bool(observed and observed['fingerprint']!=source['fingerprint'])
                record(manager,'attention' if changed else 'external',
                       'Your existing language pack may need updating' if changed else 'Using your existing language pack',
                       'The game build changed since this pack was recorded. SynthScan did not generate the full pack, so it has left it untouched. Text settings lets you back it up and switch to freshly generated SynthStrings.' if changed else
                       'This text file matches SynthScan\'s recorded copy. It is an existing language pack, not a full pack generated by SynthScan. No repair failure was detected, but compatibility with this build has not been verified. You can keep it, or use Text settings to back it up and switch to generated SynthStrings.',
                       source,now=now,reason='pack_build_changed' if changed else 'existing_pack')
            else:
                record(manager,'attention','Your language file was changed outside SynthScan',
                       'The current file differs from the last version recorded by SynthScan. It was left untouched. Text settings lets you keep it or back it up before generating a fresh pack.',source,now=now,reason='external_edit')
            return None
        if entry.get('source', {}).get('fingerprint') == source['fingerprint'] and ini.exists():
            if digest(ini.read_bytes()) != entry.get('last_sha256'):
                record(manager, 'attention', 'Your language file was changed outside SynthScan',
                       'The file differs from SynthScan\'s recorded version. It was left untouched. Open Text settings to keep it or back it up before rebuilding.', source, now=now,reason='external_edit')
                return None
            if load(manager.folder / 'guard_status.json').get('state') not in ('ready', 'adapted'):
                record(manager, 'ready', 'SynthStrings is ready', 'Text is prepared for this installed game build.', source, now=now)
            return None
        # Do this BEFORE the settle timer or a possibly slow archive read.
        removed = manager.suspend(pids)
        if ini.exists():
            record(manager, 'attention', 'Your language file could not be replaced safely',
                   'The existing text file could not be verified as an unchanged SynthStrings-generated pack. It was left untouched. Open Text settings to review it.',
                   source, now=now,reason='external_edit')
            return None
        observation_path = manager.folder / 'guard_observation.json'
        observation = load(observation_path)
        if observation.get('fingerprint') != source['fingerprint'] or observation.get('since', now) > now:
            observation = dict(fingerprint=source['fingerprint'], since=now)
            save(observation_path, observation)
        stable = now - (source['archive_mtime'] if settled else max(observation['since'], source['archive_mtime'])) >= SETTLE_SECONDS
        record(manager, 'updating' if stable else 'fallback',
               'SynthStrings is adapting to this patch' if stable else 'SynthStrings is temporarily using game defaults',
               'The old SynthStrings file is quarantined. ' +
               ('Checking fresh game text before enabling enhancements.' if stable else 'Waiting for the launcher patch files to settle; the launcher session will trigger a completion check.'),
               source, affected=pids if removed else (), now=now)
        return source if stable else None


def preflight(profile=PROFILE, games=None, pids=None, now=None, settled=False):
    """All channels are protected before any channel starts a slow rebuild."""
    jobs = []
    for game in channels(profile) if games is None else games:
        try:
            source = inspect_channel(game, profile, now, pids,settled)
            if source:
                jobs.append((Path(game), source))
        except TimeoutError:
            continue  # A guarded writer owns this channel and rechecks at commit.
        except (OSError, ValueError, KeyError, TypeError) as error:
            manager = Manager(game, profile)
            record(manager, 'attention', 'SynthStrings could not check the game files',
                   'The check stopped without replacing your text file. Open Text settings to retry. '+str(error), now=now,reason='check_failed')
    return jobs


def rebuild(game, profile=PROFILE, native=None, cancel=None):
    from game_text_lifecycle import apply_native
    # The renderer requires the exact compiled blueprint-row count. Its new
    # --render-texts protocol accepts '-' and loads the native ownership ledger.
    return apply_native(game, '-', profile, native, cancel)


def poll(profile=PROFILE, native=None):
    return process_jobs(preflight(profile), profile, native)


def process_jobs(jobs, profile=PROFILE, native=None, cancel=None):
    for game, source in jobs:
        if cancel is not None and cancel.is_set():
            break
        try:
            result = rebuild(game, profile, native, cancel=cancel)
        except TimeoutError:
            continue  # Another renderer owns the channel; quick checks continue.
        except (OSError, ValueError, RuntimeError) as error:
            manager = Manager(game, profile)
            with localization_lock(manager.game / INI):
                defaults = not manager.target(INI).exists()
                record(manager, 'fallback' if defaults else 'attention',
                       'SynthStrings is temporarily using game defaults' if defaults else 'SynthStrings could not rebuild the text pack',
                       ('The text update did not pass verification. You can play with game defaults; Text settings has a Check now button to retry. ' if defaults else
                        'The text update could not complete. The existing file was preserved; open Text settings for recovery options. ') + str(error), source,reason='rebuild_failed')


def view(profile=PROFILE, pids=()):
    """Persistent home-screen result; a new game process clears restart advice."""
    values = []
    for path in (Path(profile) / 'game_text').glob('*/guard_status.json'):
        try:
            value = load(path)
            if value.get('schema') != 1:
                continue
            # Old versions collapsed "pre-existing pack" and "external edit"
            # into one warning. Do not present that ambiguous historical notice
            # as a detected failure while waiting for the next explicit check.
            if not value.get('reason') and value.get('detail','').startswith('An externally owned or edited localization file was preserved.'):
                value.update(state='external',title='An existing text pack has not been verified',
                             detail='The earlier check preserved an existing language pack; it did not establish that the text was broken. Choose Check now in Text settings to verify it, or keep using your current pack.',reason='existing_pack_unverified')
            elif value.get('title')=='SynthStrings needs attention':
                detail=value.get('detail','')
                if 'changed outside SynthScan' in detail:
                    value.update(title='Your language file changed outside SynthScan',reason='external_edit')
                elif 'cleanup' in detail or 'conflict' in detail:
                    value.update(title='Earlier text changes could not be restored',reason='cleanup_conflict')
                else:
                    value.update(title='The earlier text check did not finish',reason='previous_check_failed')
                value['detail']=detail.replace('Open Setup','Open Text settings') if detail else 'The earlier version did not record a cause. Choose Check now in Text settings to get a specific result.'
            value['restart_required'] = bool(set(pids) & set(value.get('affected_game_pids', [])))
            value['history']=[event for event in value.get('history',[]) if event.get('detail')]
            values.append(value)
        except (OSError, ValueError, TypeError):
            continue
    if not values:
        return {}
    priority = dict(attention=5, fallback=4, updating=3, adapted=2, ready=1, disabled=0)
    values.sort(key=lambda v: (v['restart_required'], priority.get(v.get('state'), 0), v.get('at', 0)), reverse=True)
    result = dict(values[0], channels=values)
    if result['restart_required']:
        if result['state'] == 'attention':
            result['detail'] += ' Resolve the recovery issue in Setup before restarting Star Citizen.'
        else:
            result['title'] = 'Restart Star Citizen to refresh SynthStrings'
            result['detail'] += ' Restart Star Citizen once to load the prepared text. Text already loaded by the running game cannot be replaced.'
    result['warning'] = result['restart_required'] or result['state'] in ('attention', 'fallback')
    result['summary'] = {
        'adapted': 'Current game text is prepared. Enhancements will load the next time you start Star Citizen.',
        'ready': 'SynthStrings is prepared for the installed game build.',
        'fallback': 'Game defaults are prepared. The next launcher or patch-completion event will check again; Text settings also has Check now.',
        'updating': 'Game defaults are in place while SynthStrings checks the new patch.',
        'attention': result.get('detail','The last check could not finish. Open Text settings for the exact result.'),
        'external': result['detail'] if result.get('reason')=='existing_pack_unverified' else 'Using your existing text pack. Automatic rebuilding is not enabled for this pack. Text settings lets you keep it or switch to generated SynthStrings.',
        'disabled': 'SynthStrings is off. You can enable it again in Setup.',
    }.get(result['state'], '')
    if len(values) > 1:
        result['title'] = result['channel'] + ': ' + result['title']
    return result


def request_check(profile=PROFILE, trigger='manual', session=None):
    """Queue one explicit event; reopening a bridge does not create an event."""
    token=session or uuid.uuid4().hex
    identity=digest((trigger+':'+token).encode())
    path=Path(profile)/'game_text/requests'/(identity+'.json')
    if not path.exists():save(path,dict(id=identity,trigger=trigger,at=time.time()))
    return identity


def check_once(profile=PROFILE,native=None,cancel=None):
    return process_jobs(preflight(profile,settled=True),profile,native,cancel)


def check_event(profile,native,cancel,manual):
    if not manual:
        from app_lifecycle import launcher_process_ids
        if current_pids() or not launcher_process_ids():return 'deferred'
    return check_once(profile,native,cancel)


class GuardService:
    """Consume launcher/manual events. Never schedule recurring patch scans."""
    def __init__(self, profile=PROFILE, native=None):
        from app_lifecycle import SingleInstance
        self.lock = SingleInstance('strings-guard')
        self.profile, self.native = Path(profile), native
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='synthstrings-guard') if self.lock.acquired else None
        self.futures = {}
        self.stop = threading.Event()
        self.completed_path=self.profile/'game_text/check_events.json'
        self.completed=load(self.completed_path).get('completed',[])

    def tick(self):
        if not self.pool:
            from app_lifecycle import SingleInstance
            self.lock.close()
            self.lock = SingleInstance('strings-guard')
            if not self.lock.acquired:
                return
            self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='synthstrings-guard')
        for identity,future in list(self.futures.items()):
            if not future.done():continue
            try:
                if future.result()=='deferred':
                    del self.futures[identity];continue
            except Exception:logging.exception('SynthStrings event check failed')
            self.completed=(self.completed+[identity])[-64:]
            save(self.completed_path,dict(completed=self.completed))
            (self.profile/'game_text/requests'/(identity+'.json')).unlink(missing_ok=True)
            del self.futures[identity]
        for path in sorted((self.profile/'game_text/requests').glob('*.json')):
            identity=path.stem
            if identity in self.completed:
                path.unlink(missing_ok=True);continue
            if identity in self.futures:continue
            if len(self.futures)>=2:break
            request=load(path)
            if request.get('trigger')!='manual':
                from app_lifecycle import launcher_process_ids
                if not launcher_process_ids():
                    self.completed=(self.completed+[identity])[-64:]
                    save(self.completed_path,dict(completed=self.completed));path.unlink(missing_ok=True)
                    continue
                if current_pids():continue
            self.futures[identity]=self.pool.submit(check_event,self.profile,self.native,self.stop,request.get('trigger')=='manual')

    def close(self):
        self.stop.set()
        if self.pool:
            self.pool.shutdown(wait=False, cancel_futures=True)
        self.lock.close()
