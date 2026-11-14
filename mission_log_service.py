"""Owned background mission logger. Local snapshots + read-only own-account queries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time

from account_permission import require_account_access
from mission_log import MissionLog, clean_title
from questing import mission_event, own_missions, own_wallet
from session_overview import play_events, stamp
from telemetry_ipc import publish_json, read_shared_json


def read(path):
    try:
        return read_shared_json(path, limit=8*1024*1024) or {}
    except (OSError, ValueError):
        return {}


def load_catalog():
    from game_records import GameRecords, walk_nodes
    from installation import reference_paths
    paths = reference_paths()
    audit = json.loads(paths['audit'].read_text(encoding='utf-8'))
    manifest = json.loads((paths['game']/'build_manifest.id').read_text())
    if audit['build']['BuildId'] != manifest['Data']['BuildId']:
        raise ValueError('Reward definitions are for a different game build')
    store = GameRecords(paths['records'], paths['localization'])
    catalog = {}
    names = {}
    for path in (store.root/'libs/foundry/records/factions/factionreputation').rglob('*.json'):
        faction = store.read(path)['_RecordValue_']
        if faction.get('GEID'):
            names[f"urn:sc:reputations:{'npc' if faction.get('isNPC') else 'org'}:geid:{faction['GEID']}"] = store.text(faction.get('displayName'))
    catalog['_names'] = names
    for mission in audit['missions']:
        rewards = [o['rewards'] for o in mission['outcomes'] if any((r.get('configured_amount') or 0) > 0 for r in o['rewards'])]
        value = store.read(store.root/mission['source'])['_RecordValue_']
        rows = []
        if len(rewards) == 1:
            for r in rewards[0]:
                # Old audit rows without a stable service entity remain useful
                # as configuration, but cannot identify a balance track.
                rows.append(dict(r))
        catalog[mission['id'].lower()] = dict(title=mission['title'], rewards=rows,
                                               payout=(value.get('missionReward') or {}).get('reward'))
    career = paths['career']/'libs/foundry/records/contracts/contractgenerator'
    for path in career.rglob('*.json'):
        for contract in walk_nodes(json.loads(path.read_text(encoding='utf-8'))):
            if contract.get('_Type_') != 'CareerContract' or not contract.get('id'):
                continue
            rewards = []
            for result in (contract.get('contractResults') or {}).get('contractResults', []):
                if result.get('_Type_') != 'ContractResult_LegacyReputation' or not result.get('missionResults', [False])[0]:
                    continue
                params = result.get('contractResultReputationAmounts') or {}
                try:
                    faction = store.value(params['factionReputation'])
                    scope = store.value(params['reputationScope'])
                    try:
                        amount = store.value(params['reward'])['reputationAmount']
                        provenance = 'Extracted reward value'
                    except FileNotFoundError:
                        # The original game references some misspelled filenames
                        # not present in the partial export. Keep this explicitly
                        # weaker than a resolved numeric record.
                        match = re.search(r'positive_(\d+)\.json$', params['reward'])
                        if not match:
                            continue
                        amount = int(match[1])
                        provenance = 'Reward filename estimate; numeric record unavailable'
                    rewards.append(dict(entity=f"urn:sc:reputations:{'npc' if faction.get('isNPC') else 'org'}:geid:{faction['GEID']}",
                                        faction=store.text(faction.get('displayName')), scope=scope['scopeName'],
                                        configured_amount=amount, amount_source=provenance, reference=params['reward']))
                except (KeyError, ValueError, OSError):
                    continue
            strings = (contract.get('paramOverrides') or {}).get('stringParamOverrides', [])
            title = next((v.get('value') for v in strings if v.get('param') == 'Title'), '')
            catalog[contract['id'].lower()] = dict(title=store.text(title), rewards=rewards, payout=None,
                                                   source=str(path.relative_to(paths['career'])), build_id=audit['build']['BuildId'])
    return catalog


class Logger:
    def __init__(self, directory, game_log=None):
        self.directory = Path(directory)
        self.book = MissionLog(directory)
        self.catalog = self.book.meta('catalog', {})
        self.game_log = Path(game_log) if game_log else None
        self.character = ''
        self.session = ''
        self.started = 0
        self.next_catalog = 0
        self.file_stamps = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mission-log-read')
        self.future = None
        self.next_query = 0
        self.error = ''
        self.wallet_error = ''
        self.filters = dict(query='', session='', outcome='', offset=0)
        self.mode = 'all'
        self.direction = ''
        self.category = ''
        self.note = ''
        self.note_at = 0
        self.command_seen = set()
        if not self.book.meta('recording_since'):
            with self.book.db:
                self.book.set_meta('recording_since', time.time())

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.book.close()

    def identity(self):
        if self.game_log is None:
            from installation import game_directory
            self.game_log = game_directory(True)/'Game.log'
        with self.game_log.open('rb') as stream:
            head = stream.read(8192).decode('utf-8', errors='replace')
        match = re.search(r'^<([^>]+)>', head, re.M)
        started = stamp(match[1]) if match else None
        if not started:
            return
        self.started = started
        self.session = hashlib.sha256((str(self.game_log.resolve())+'|'+str(started)).encode()).hexdigest()[:24]
        with self.book.db:
            sessions = self.book.meta('sessions', {})
            sessions.setdefault(self.session, dict(id=self.session, started_at=started))
            self.book.set_meta('sessions', sessions)

    def changed(self, name):
        try:
            value = (self.directory/name).stat().st_mtime_ns
        except OSError:
            return False
        changed = self.file_stamps.get(name) != value
        self.file_stamps[name] = value
        return changed

    def event_line(self, line):
        match = re.match(r'<([^>]+)>', line)
        at = stamp(match[1]) if match else None
        if not at:
            return
        event = mission_event(line)
        if event:
            self.book.mission(dict(event, at=at, source='game_log'), self.character, self.session)
        for event in play_events(line):
            if event['type'] == 'contract_completed':
                self.book.mission(event, self.character, self.session)
        match = re.search(r'<MissionShared>.*missionId\[([^]]+)\]', line)
        if match:
            self.book.mission(dict(id=match[1], at=at, shared=True, source='game_log_share'), self.character, self.session)

    def tail_log(self):
        cursor = self.book.meta('log_cursor', {})
        position = cursor.get('position', 0) if cursor.get('session') == self.session else 0
        size = self.game_log.stat().st_size
        if position > size:
            position = 0
        with self.game_log.open('rb') as stream:
            stream.seek(position)
            end = position+4*1024*1024
            while stream.tell() < end:
                start = stream.tell()
                raw = stream.readline()
                if not raw:
                    break
                if not raw.endswith(b'\n'):
                    stream.seek(start)
                    break
                self.event_line(raw.decode('utf-8', errors='replace'))
            position = stream.tell()
        with self.book.db:
            self.book.set_meta('log_cursor', dict(session=self.session, position=position))

    def journal(self, value):
        for mission in value.get('missions', []):
            if isinstance(mission, dict):
                self.book.mission(mission, self.character, self.session)

    def context(self, value):
        context = value.get('questing') or {}
        title = clean_title(context.get('title', ''))
        count = next((re.fullmatch(r'Mission participants: (\d+)', line) for line in context.get('lines', [])
                      if re.fullmatch(r'Mission participants: (\d+)', line)), None)
        if not count or not self.character:
            return
        candidates = [m for m in self.book._missions() if m['id'] in context.get('active_ids', []) and m['title'] == title]
        if len(candidates) != 1:
            return
        age = re.fullmatch(r'Balances verified (\d+)s ago', context.get('footer', ''))
        if not age:
            return
        at = value.get('written_at', 0)-int(age[1])
        self.book.participation(dict(id=candidates[0]['id'], participants=int(count[1]),
                                     source='Selected mission HUD service observation'), self.character, at)

    def replay_evidence(self):
        path = self.directory/'mission_evidence.jsonl'
        if not path.exists():
            return
        position = self.book.meta('evidence_position', 0)
        if position > path.stat().st_size:
            position = 0
        with path.open('rb') as stream:
            stream.seek(position)
            for _ in range(500):
                start = stream.tell()
                raw = stream.readline()
                if not raw:
                    break
                if not raw.endswith(b'\n'):
                    stream.seek(start)
                    break
                try:
                    event = json.loads(raw)
                    value = event['data']
                    if event['kind'] == 'reputation':
                        self.book.reputation(dict(value, play_session=self.session if value.get('read_at', 0) >= self.started else ''))
                    elif event['kind'] == 'missions':
                        self.journal(value)
                    elif event['kind'] == 'context':
                        self.context(value)
                except (ValueError, KeyError, TypeError):
                    pass
            position = stream.tell()
        with self.book.db:
            self.book.set_meta('evidence_position', position)

    def ingest_service(self, value):
        if value.get('own_character_verified') is not True or not value.get('character_key'):
            return
        character = value['character_key']
        at = value.get('read_at', 0)
        for mission in value.get('missions', []):
            self.book.participation(mission, character, at)
            self.book.mission(dict(id=mission['id'], at=at, definition_id=mission.get('definition_id'),
                                   status='Accepted' if mission.get('state') in (1, 2, 3) else None, source='own_mission_service'),
                              character, self.session)
        if value.get('wallet'):
            self.book.wallet(dict(value['wallet'], play_session=self.session if value['wallet']['read_at'] >= self.started else ''))
        self.wallet_error = value.get('wallet_error', '')

    @staticmethod
    def query():
        from game_account import OwnAccount
        client = OwnAccount()
        try:
            value = dict(character_key=hashlib.sha256(client.subject.encode()).hexdigest(), own_character_verified=True)
            try:
                value['missions'] = own_missions(client)
            except Exception as error:
                value['missions'] = []
                value['mission_error'] = 'Participant read unavailable ('+type(error).__name__+')'
            value['read_at'] = time.time()
            try:
                value['wallet'] = own_wallet(client)
            except Exception as error:
                value['wallet_error'] = 'Wallet read unavailable ('+type(error).__name__+')'
            return value
        finally:
            client.close()

    def restore_sessions(self):
        value = read(self.directory/'session_overview.json')
        sessions = self.book.meta('sessions', {})
        for key in ('current', 'previous'):
            session = value.get(key)
            if not session:
                continue
            sessions[session['id']] = {k: session.get(k) for k in ('id', 'started_at', 'ended_at')}
            character = (session.get('rep_start') or {}).get('character', '')
            for event in session.get('contracts', {}).values():
                self.book.mission(event, character, session['id'])
            for label in ('rep_start', 'rep_latest'):
                sample = session.get(label)
                if not sample:
                    continue
                self.book.reputation(dict(source='authenticated_reputation_service', own_character_verified=True,
                                          complete=True, character_key=sample['character'], read_at=sample['read_at'],
                                          records=list(sample['records'].values()), play_session=session['id'],
                                          restored_from='saved verified session recap'))
        with self.book.db:
            self.book.set_meta('sessions', sessions)

    def reconcile_sessions(self):
        """Restore time-based tags for early captures and carried contracts."""
        sessions = self.book.meta('sessions', {})
        signature = hashlib.sha256(json.dumps(sessions, sort_keys=True).encode()).hexdigest()
        if signature == self.book.meta('normalized_sessions'):
            return
        starts = sorted((s.get('started_at', 0), sid) for sid,s in sessions.items())
        def session_at(at):
            eligible = [sid for start,sid in starts if start <= at]
            return eligible[-1] if eligible else ''
        with self.book.db:
            for table in ('reputation', 'wallets'):
                for character,at,body in self.book.db.execute(f'SELECT character,at,body FROM {table}').fetchall():
                    value = json.loads(body);sid=session_at(at)
                    if sid and value.get('session') != sid:
                        value['session']=sid
                        self.book.db.execute(f'UPDATE {table} SET body=? WHERE character=? AND at=?',
                                             (json.dumps(value,allow_nan=False),character,at))
            for mid,body in self.book.db.execute('SELECT id,body FROM missions').fetchall():
                value=json.loads(body)
                at=value.get('ended_at') or value.get('last_active_at') or value.get('accepted_at') or value['first_seen_at']
                sid=session_at(at)
                if sid:
                    value['session']=sid
                    if value.get('accepted_at'):value['accepted_session']=session_at(value['accepted_at'])
                    if value.get('ended_at'):value['ended_session']=sid
                    self.book.db.execute('UPDATE missions SET body=? WHERE id=?',(json.dumps(value,allow_nan=False),mid))
            self.book.set_meta('normalized_sessions',signature)

    def commands(self):
        folder = self.directory/'mission_log_commands'
        for path in sorted(folder.glob('*.json'))[:32]:
            try:
                request = read(path)
                if request.get('action') == 'view':
                    self.mode = request.get('mode', 'all') if request.get('mode', 'all') in ('all', 'missions', 'reputation', 'rewards', 'wallet', 'sessions') else 'all'
                    self.direction = request.get('direction', '') if request.get('direction', '') in ('gains', 'losses') else ''
                    from mission_log import CATEGORIES
                    self.category = request.get('category', '') if request.get('category') in CATEGORIES and self.mode in ('wallet', 'all') else ''
                    self.filters = dict(query=str(request.get('query', ''))[:200],
                                        session=self.session if request.get('current_session') else '',
                                        outcome=request.get('outcome', '') if self.mode in ('all', 'missions', 'rewards') and request.get('outcome', '') in ('completed', 'failed', 'abandoned', 'active') else '',
                                        offset=max(0, int(request.get('offset', 0))))
                elif request.get('action') == 'export':
                    count = self.book.export(request['path'], self.catalog)
                    self.note = f'Exported {count} missions and saved evidence.'
                elif request.get('action') == 'classify_wallet':
                    self.book.annotate(request['change_id'], request['category'], str(request.get('note', '')))
                    self.note = 'Wallet category saved as a player classification.'
                else:
                    raise ValueError('Unknown mission-log command')
            except (ValueError, KeyError, OSError, TypeError) as error:
                self.note = str(error) if isinstance(error, ValueError) else 'Could not process mission-log request.'
            if self.note:
                self.note_at = time.time()
            path.unlink(missing_ok=True)

    def catalog_stamp(self):
        """Game definitions are static: avoid rescanning them during every run."""
        if not self.game_log or not (self.game_log.parent/'build_manifest.id').exists():return None
        from installation import reference_paths
        paths = reference_paths()
        manifest = json.loads((paths['game']/'build_manifest.id').read_text(encoding='utf-8'))
        return dict(build=manifest['Data']['BuildId'], audit=str(paths['audit'].resolve()),
                    audit_at=paths['audit'].stat().st_mtime_ns,
                    localization_at=paths['localization'].stat().st_mtime_ns,
                    career=str(paths['career'].resolve()))

    def tick(self, now=None):
        now = time.time() if now is None else now
        allowed = True
        try:
            require_account_access(self.directory)
        except PermissionError:
            allowed = False
        if allowed:
            try:
                self.identity()
                snapshot = read(self.directory/'reputation_snapshot.json')
                self.character = snapshot.get('character_key', '') if snapshot.get('own_character_verified') else ''
                self.tail_log()
                if self.changed('questing_journal.json'):
                    self.journal(read(self.directory/'questing_journal.json'))
                self.replay_evidence()
                self.book.reputation(dict(snapshot, play_session=self.session))
                if self.changed('session_overview.json'):
                    self.restore_sessions()
                self.reconcile_sessions()
                self.context(read(self.directory/'session_state.json'))
                service = read(self.directory/'mission_service_snapshot.json')
                if service and self.changed('mission_service_snapshot.json'):
                    self.ingest_service(service)
                if self.future and self.future.done():
                    try:
                        self.ingest_service(self.future.result())
                        self.error = ''
                    except Exception as error:
                        self.error = 'Account read unavailable ('+type(error).__name__+')'
                    self.future = None
                missing_active = not service.get('missions') and any(m.get('status') == 'Accepted' and not m.get('ended_at') for m in self.book._missions())
                if now >= self.next_query and not self.future and (now-service.get('read_at', 0) > 45 or missing_active):
                    # Older already-running apps cannot publish participant/wallet
                    # observations. Supply those until the updated app is launched.
                    from app_lifecycle import game_process_ids
                    if game_process_ids():
                        self.future = self.pool.submit(self.query)
                        self.next_query = now+30
                if now >= self.next_catalog:
                    self.next_catalog = now+300
                    try:
                        fingerprint = self.catalog_stamp()
                        if not self.catalog or fingerprint is None or fingerprint != self.book.meta('catalog_fingerprint'):
                            self.catalog = load_catalog()
                            if fingerprint != self.catalog_stamp():raise ValueError('Game references changed during catalog read')
                            with self.book.db:
                                self.book.set_meta('catalog', self.catalog)
                                self.book.set_meta('catalog_fingerprint', fingerprint)
                    except Exception as error:
                        self.catalog = {}
                        self.error = 'Reward catalog unavailable ('+type(error).__name__+')'
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
                self.error = 'Mission capture delayed ('+type(error).__name__+')'
        self.commands()
        self.book.freeze_definitions(self.catalog)
        from mission_log_report import present
        full = self.book.view(self.catalog, now=now, limit=1_000_000)
        from mission_hud import snapshot as hud_snapshot
        context = read(self.directory/'session_state.json')
        native = read(self.directory/'native_status.json')
        hud = hud_snapshot(full, context.get('questing') or {}, self.session, now=now,
                           recording=allowed, owner_pid=native.get('pid', 0),
                           game_running=bool(context.get('game_pids')) and 0 <= now-context.get('written_at', 0) < 5,
                           names=self.catalog.get('_names', {}))
        publish_json(self.directory/'mission_hud.json', hud)
        value = (self.book.view(self.catalog, now=now, query='', session=self.filters['session'], outcome=self.filters['outcome'], limit=1_000_000)
                 if self.filters['session'] or self.filters['outcome'] else dict(full))
        if self.filters['outcome']:
            eligible = {m['id'] for m in value['rows']}
            value['changes'] = [w for w in value['changes'] if eligible.intersection(w['missions'])]
        value.update(present(value, self.catalog, mode=self.mode, direction=self.direction,
                             category=self.category, query=self.filters['query'], offset=self.filters['offset']))
        value.update(recording=allowed, recording_since=self.book.meta('recording_since'), current_session=self.session,
                     error=self.error, wallet_error=self.wallet_error, note=self.note, note_until=self.note_at+12)
        try:
            from mission_analytics import analyze
            value['analytics'] = analyze(full, self.catalog.get('_names', {}), now)
        except (ImportError, KeyError, TypeError, ValueError):
            value['analytics'] = {}
        for key in ('rows', 'changes', 'mission_names'):
            value.pop(key, None)
        value['sessions'] = value['sessions'][:30]
        publish_json(self.directory/'mission_log_view.json', value)
        return value


def run(directory, owner):
    from app_lifecycle import SingleInstance
    from native_bridge import owner_alive
    key = hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:16]
    single = SingleInstance('mission-log-'+key)
    if not single.acquired:
        return
    logger = Logger(directory)
    try:
        while True:
            if not owner_alive(owner):
                replacement = read(Path(directory)/'native_status.json').get('pid', 0)
                if not replacement or not owner_alive(replacement):
                    break
                owner = replacement
            try:
                logger.tick()
                publish_json(Path(directory)/'mission_log_status.json', dict(at=time.time(), owner_pid=owner, logger_pid=os.getpid(), running=True))
            except Exception as error:
                logging.warning('Mission log tick failed (%s)', type(error).__name__)
            time.sleep(1)
    finally:
        logger.close()
        single.close()
        publish_json(Path(directory)/'mission_log_status.json', dict(at=time.time(), owner_pid=owner, running=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--owner', type=int, required=True)
    args = parser.parse_args()
    logging.basicConfig(filename=args.directory/'mission_log.log', level=logging.INFO)
    run(args.directory, args.owner)
