"""Persistent mission evidence and conservative reward comparisons.

Balance changes are observations, not transaction receipts. A single-completion
window is a correlation; overlapping completions are never divided by guessing.
"""
from datetime import datetime
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from session_overview import stamp

CATEGORIES = {'unclassified': 'Unclassified', 'mission_reward': 'Mission reward',
              'player_transfer': 'Player transfer', 'repair': 'Repairs', 'refuel': 'Refueling',
              'store_purchase': 'Store purchase', 'vehicle_purchase': 'Vehicle / equipment',
              'cargo_trade': 'Cargo trading', 'fees': 'Fees / fines', 'other': 'Other'}

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def clean_title(value):
    return re.sub(r'\s*\[(?:\d+ Rep|BP|ALL BP).*$', '', str(value)).strip()[:500]


def load_retail_price_index(directory):
    """Index known retail purchase prices from item_shops and directory_vehicles for automatic purchase matching."""
    price_map = {}
    if not directory:
        return price_map
    dir_path = Path(directory)
    uuid_names = {}
    for candidate in (Path('data/local_game_library.json'), dir_path / 'local_game_library.json'):
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding='utf-8'))
                for entry in data.get('entries', []):
                    uuid_names[entry.get('id')] = (entry.get('name', 'Item'), 'vehicle_purchase' if entry.get('kind') in ('Ship', 'Vehicle') else 'store_purchase')
            except Exception:
                pass
            break
    vpath = dir_path / 'directory_vehicles.json'
    vmap = {}
    if vpath.exists():
        try:
            vdata = json.loads(vpath.read_text(encoding='utf-8'))
            for r in vdata.get('rows', []):
                vmap[r.get('id')] = r.get('name', 'Vehicle')
        except Exception:
            pass
    shops_dir = dir_path / 'item_shops'
    if shops_dir.exists():
        for f in shops_dir.glob('*.json'):
            try:
                content = json.loads(f.read_text(encoding='utf-8'))
                item_id = content.get('item_id', f.stem)
                if item_id in vmap:
                    name, cat = vmap[item_id], 'vehicle_purchase'
                elif item_id in uuid_names:
                    name, cat = uuid_names[item_id]
                else:
                    name, cat = f.stem, 'store_purchase'
                for row in content.get('rows', []):
                    p = row.get('price')
                    if p and p > 0:
                        cost = int(round(p))
                        price_map.setdefault(cost, dict(name=name, category=cat, item_id=item_id,
                                                        shop=row.get('shop') or row.get('location', '').split('→')[-1].strip(),
                                                        location=row.get('location')))
            except Exception:
                pass
    return price_map


def wallet_classification(window, missions, catalog, rep_by_mission=None, price_index=None):
    """Inferred mission windows and purchase matches stay distinct from player labels and receipts."""
    manual = window.get('annotation') or {}
    if manual:return dict(manual)
    delta = window.get('delta', 0)
    if delta < 0 and price_index:
        cost = abs(int(round(delta)))
        match = price_index.get(cost)
        if match:
            return dict(category=match['category'], source=f"Retail price match: {match['name']}",
                        item_name=match['name'], item_id=match.get('item_id'), shop=match.get('shop'),
                        price_match=True)
    result = dict(category='unclassified', source='Unclassified')
    if (window.get('kind') != 'wallets' or window.get('track', '').upper() != 'AUEC'
            or delta <= 0 or not window.get('associated')
            or window.get('reason') != 'Single completion in window' or len(window.get('missions', [])) != 1):
        return result
    mission = missions.get(window['missions'][0], {})
    if mission.get('status') != 'Complete':return result
    definition = mission.get('definition_snapshot') or catalog.get(mission.get('definition_id'), {})
    giver = definition.get('mission_giver')
    reward_organizations = list(dict.fromkeys(r['faction'] for r in definition.get('rewards', []) if r.get('faction')))
    if not reward_organizations and not giver and rep_by_mission:
        names = catalog.get('_names', {})
        for r in rep_by_mission.get(mission['id'], []):
            if r.get('delta', 0) > 0:
                ent = r['track'].partition('|')[0]
                fname = names.get(ent, ent)
                if fname and fname not in reward_organizations:
                    reward_organizations.append(fname)
    return dict(category='mission_reward', source='Mission completion correlation',
                mission_id=mission['id'], mission_title=mission['title'],
                mission_giver=giver,
                reward_organizations=reward_organizations)


def mission_timing(mission, now, accepted=None):
    """Wall time from an observed acceptance, never from an account poll."""
    end = mission.get('ended_at')
    stop = end if finite(end) else now
    valid = finite(accepted) and accepted > 0 and finite(stop) and stop >= accepted
    elapsed = stop - accepted if valid else None
    return dict(accepted_log_at=accepted if valid else None,
                elapsed_seconds=elapsed if valid and not end else None,
                duration_seconds=elapsed if valid and end else None,
                timing_status=('finished' if end else 'running') if valid else 'unknown',
                timing_note='Acceptance to outcome wall time; includes menus and time away.' if valid else 'Acceptance time was not observed; full duration is unknown.')


def format_duration(seconds):
    if not finite(seconds) or seconds < 0:return 'Start unknown'
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes:02}:{seconds:02}'


def split_comparison(base, observed, participants=None):
    """Describe numerical matches without claiming a server distribution rule."""
    result = dict(base=base, observed=observed, participants=participants,
                  equal_split=base / participants if finite(base) and participants else None,
                  fraction=None, effective_divisor=None, match='Unknown')
    if not finite(base) or base <= 0 or not finite(observed):
        return result
    result['fraction'] = observed / base
    if observed > 0:
        result['effective_divisor'] = base / observed
    close = lambda a, b: abs(a-b) <= max(.01, abs(b)*1e-6)
    if close(observed, base):
        result['match'] = 'Matches full amount'
    elif participants and participants > 1 and close(observed, base / participants):
        result['match'] = f'Matches 1/{participants} split'
    elif observed == 0:
        result['match'] = 'No change observed'
    else:
        result['match'] = f'{observed/base:.1%} of base; unexplained'
    return result


class MissionLog:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'mission_log.sqlite3', timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, at REAL NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, mission TEXT, at REAL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reputation(character TEXT, at REAL, body TEXT NOT NULL,
                PRIMARY KEY(character,at));
            CREATE TABLE IF NOT EXISTS wallets(character TEXT, at REAL, body TEXT NOT NULL,
                PRIMARY KEY(character,at));
            CREATE TABLE IF NOT EXISTS participants(mission TEXT, character TEXT, at REAL, body TEXT NOT NULL,
                PRIMARY KEY(mission,character,at));
            CREATE TABLE IF NOT EXISTS annotations(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS mission_time ON missions(at);
        ''')
        self.db.commit()
        self._price_index = None
        self._price_index_time = 0
        version = self.meta('schema')
        if version is not None and version != 1:
            self.db.close()
            raise ValueError('Unknown mission-log schema; existing database preserved')
        with self.db:self.set_meta('schema', 1)

    def close(self):
        self.db.close()

    def meta(self, key, default=None):
        row = self.db.execute('SELECT body FROM metadata WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        self.db.execute('INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET body=excluded.body',
                        (key, json.dumps(value, allow_nan=False)))

    def session_at(self, at, fallback=''):
        eligible = [(sid, s.get('started_at', 0)) for sid,s in self.meta('sessions', {}).items() if s.get('started_at', 0) <= at]
        return max(eligible, key=lambda pair: pair[1])[0] if eligible else fallback

    def mission(self, event, character='', session=''):
        mid = str(event.get('mission_id') or event.get('id') or '')
        at = event.get('at') or stamp(event.get('event_timestamp', ''))
        if not mid or not finite(at) or at <= 0:
            return
        row = self.db.execute('SELECT body FROM missions WHERE id=?', (mid,)).fetchone()
        session = self.session_at(at, session)
        old = json.loads(row[0]) if row else dict(id=mid, title='Contract ' + mid[:8],
                                                character=character, session=session, first_seen_at=at, status='Observed')
        update = {k: event[k] for k in ('definition_id', 'objective') if event.get(k)}
        if event.get('title') or event.get('name'):
            update['title'] = clean_title(event.get('title') or event['name'])
        if character and not old.get('character'):
            update['character'] = character
        if session and not old.get('session'):
            update['session'] = session
        status = event.get('status')
        if event.get('type') == 'contract_completed':
            status = 'Complete'
        if status == 'Accepted':
            update['accepted_at'] = min(old.get('accepted_at', at), at)
            update['last_active_at'] = max(old.get('last_active_at', 0), at)
            if not old.get('ended_at'):
                update['status'] = status
                if session:update['session'] = session
            if session:update['accepted_session'] = old.get('accepted_session', session)
        elif status and at >= old.get('ended_at', 0):
            update.update(status=status, ended_at=at)
            if session:update.update(session=session, ended_session=session)
        if event.get('shared'):
            update['shared'] = True
            if not old.get('accepted_at') and not old.get('ended_at'):
                update['status'] = 'Shared offer'
        old.update(update)
        event_id = hashlib.sha256(json.dumps([mid, at, event], sort_keys=True).encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',
                            (event_id, mid, at, json.dumps(event, allow_nan=False)))
            self.db.execute('INSERT INTO missions VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET at=excluded.at,body=excluded.body',
                            (mid, old.get('ended_at') or old.get('accepted_at') or at,
                             json.dumps(old, allow_nan=False)))

    def reputation(self, snapshot):
        if (not isinstance(snapshot, dict) or snapshot.get('source') != 'authenticated_reputation_service'
                or snapshot.get('own_character_verified') is not True or snapshot.get('complete') is not True
                or not snapshot.get('character_key') or not finite(snapshot.get('read_at'))
                or snapshot['read_at'] <= 0 or not isinstance(snapshot.get('records'), list)):
            return False
        records = {}
        for record in snapshot['records']:
            if not isinstance(record, dict) or not finite(record.get('score')) or not record.get('entity') or not record.get('scope'):
                return False
            key = record['entity'] + '|' + record['scope']
            if key in records:
                return False
            records[key] = {k: record[k] for k in ('entity', 'scope', 'score', 'updated_at') if k in record}
        if not records:
            return False
        value = dict(character=snapshot['character_key'], read_at=snapshot['read_at'], records=records,
                     request_started_at=snapshot.get('request_started_at'), source=snapshot['source'],
                     session=self.session_at(snapshot['read_at'], snapshot.get('play_session', '')), provenance=snapshot.get('restored_from', 'Live verified read'))
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO reputation VALUES(?,?,?)',
                            (value['character'], value['read_at'], json.dumps(value, allow_nan=False)))
        return True

    def wallet(self, snapshot):
        if (not isinstance(snapshot, dict) or snapshot.get('own_character_verified') is not True
                or snapshot.get('source') != 'authenticated_ledger_service' or not snapshot.get('character_key')
                or not finite(snapshot.get('read_at')) or not snapshot.get('balances')):
            return False
        if any(not finite(v) or v < 0 for v in snapshot['balances'].values()):
            return False
        value = dict(character=snapshot['character_key'], read_at=snapshot['read_at'], balances=snapshot['balances'],
                     session=self.session_at(snapshot['read_at'], snapshot.get('play_session', '')))
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO wallets VALUES(?,?,?)',
                            (value['character'], value['read_at'], json.dumps(value, allow_nan=False)))
        return True

    def participation(self, mission, character, at):
        count = mission.get('participants')
        if not character or not finite(at) or type(count) is not int or not 1 <= count <= 100:
            return
        value = dict(participants=count, read_at=at, source=mission.get('source', 'own_mission_service'))
        for key in ('own_share', 'own_share_values', 'payout', 'currency', 'definition_id', 'is_owner', 'share_values'):
            if mission.get(key) is not None:
                value[key] = mission[key]
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO participants VALUES(?,?,?,?)',
                            (mission['id'], character, at, json.dumps(value, allow_nan=False)))

    def _missions(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT body FROM missions ORDER BY at DESC')]

    def freeze_definitions(self, catalog):
        """Keep historical comparisons from changing when game definitions update."""
        with self.db:
            for mission in self._missions():
                definition = catalog.get(mission.get('definition_id'), {})
                if not mission.get('definition_snapshot') and (definition.get('rewards') or finite(definition.get('payout'))):
                    mission['definition_snapshot'] = dict(definition, captured_at=time.time())
                    self.db.execute('UPDATE missions SET body=? WHERE id=?',
                                    (json.dumps(mission,allow_nan=False),mission['id']))

    def annotate(self, change_id, category, note=''):
        if category not in CATEGORIES or not isinstance(note, str) or len(note) > 2000:
            raise ValueError('Choose a valid wallet category and a shorter note')
        changes = self.intervals('wallets', self._missions(), {})
        if not any(w['id'] == change_id and w['track'] == 'AUEC' for w in changes):
            raise ValueError('That wallet observation is unavailable')
        with self.db:
            self.db.execute('INSERT INTO annotations VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                            (change_id, json.dumps(dict(category=category, note=note, source='Player classification', at=time.time()))))

    def intervals(self, table, missions, catalog, grace=10, max_gap=90):
        previous = {}
        result = []
        for character, at, body in self.db.execute(f'SELECT character,at,body FROM {table} ORDER BY at'):
            sample = json.loads(body)
            before = previous.get(character)
            previous[character] = sample
            if not before:
                continue
            old = before['records'] if table == 'reputation' else before['balances']
            new = sample['records'] if table == 'reputation' else sample['balances']
            for key in old.keys() & new.keys():
                left = old[key]['score'] if table == 'reputation' else old[key]
                right = new[key]['score'] if table == 'reputation' else new[key]
                if right == left:
                    continue
                candidates = []
                other_endings = []
                for m in missions:
                    if m.get('character') != character or not m.get('ended_at'):
                        continue
                    if not before['read_at']-grace <= m['ended_at'] <= at+grace:
                        continue
                    if m.get('status') != 'Complete':
                        other_endings.append(m['id'])
                        continue
                    rewards = (m.get('definition_snapshot') or catalog.get(m.get('definition_id'), {})).get('rewards', [])
                    if (table == 'reputation' and rewards and all(r.get('entity') and r.get('scope') for r in rewards)
                            and not any(r['entity']+'|'+r['scope'] == key for r in rewards)):
                        continue
                    candidates.append(m['id'])
                endings = list(dict.fromkeys(candidates+other_endings))
                reason = ('Session boundary' if before.get('session') != sample.get('session') else
                          'Long gap between reads' if at-before['read_at'] > max_gap else
                          'Overlapping mission endings' if len(endings) > 1 else
                          'Single non-completion in window' if other_endings else
                          'Single completion in window' if len(candidates) == 1 else 'Unmatched balance change')
                change_id = hashlib.sha256(json.dumps([table, character, before['read_at'], at, key]).encode()).hexdigest()[:24]
                item = dict(id=change_id, kind=table, character=character, start=before['read_at'], end=at,
                            session=sample.get('session', ''),
                            track=key, before=left, after=right, delta=right-left,
                            missions=endings, other_endings=other_endings, reason=reason,
                            associated=len(endings) == 1 and reason in ('Single completion in window', 'Single non-completion in window'))
                if table == 'reputation' and right > left:
                    try:
                        from reputation_ranks import detect_promotion
                        promo = detect_promotion(key.partition('|')[2], left, right)
                        if promo:
                            item['promotion'] = promo
                    except Exception:
                        pass
                result.append(item)
        return result

    def view(self, catalog=None, query='', session='', outcome='', offset=0, limit=100, now=None):
        # A published report must use one database snapshot even while the
        # recorder is committing the next account observation in another process.
        self.db.execute('SAVEPOINT mission_view')
        try:
            value = self._view(catalog, query, session, outcome, offset, limit, now)
            self.db.execute('RELEASE mission_view')
            return value
        except Exception:
            self.db.execute('ROLLBACK TO mission_view')
            self.db.execute('RELEASE mission_view')
            raise

    def _view(self, catalog=None, query='', session='', outcome='', offset=0, limit=100, now=None):
        catalog = catalog or {}
        now = time.time() if now is None else now
        missions = self._missions()
        accepted = {}
        for mid, at, body in self.db.execute('SELECT mission,at,body FROM events'):
            event = json.loads(body)
            if event.get('status') != 'Accepted' or event.get('source') == 'own_mission_service':
                continue
            # Merged journals can carry Accepted on later objectives or markers.
            # Only a raw acceptance or its preserved timestamp starts the clock.
            if event.get('source') != 'game_log' and not finite(event.get('accepted_log_at')):
                continue
            start = event.get('accepted_log_at') or at
            if finite(start) and start > 0:
                accepted[mid] = min(accepted.get(mid, start), start)
        intervals = self.intervals('reputation', missions, catalog) + self.intervals('wallets', missions, catalog)
        annotations = {row[0]: json.loads(row[1]) for row in self.db.execute('SELECT id,body FROM annotations')}
        mission_index = {m['id']: m for m in missions}
        # Pre-build rep-by-mission for faction fallback attribution
        rep_by_mission = {}
        for interval in intervals:
            if interval['kind'] == 'reputation':
                for mid in interval.get('missions', []):
                    rep_by_mission.setdefault(mid, []).append(interval)
        # Load retail price index (cached, refreshed at most once per view call)
        price_index = load_retail_price_index(self.directory)
        for window in intervals:
            window['annotation'] = annotations.get(window['id'], {})
            window['classification'] = wallet_classification(window, mission_index, catalog,
                                                             rep_by_mission=rep_by_mission,
                                                             price_index=price_index)
        by_mission = {}
        for interval in intervals:
            for mid in interval['missions']:
                by_mission.setdefault(mid, []).append(interval)
        rows = []
        for mission in missions:
            if session and mission.get('session') != session:
                continue
            if query.casefold() not in mission['title'].casefold():
                continue
            state = mission.get('status', '')
            group = ('active' if state == 'Accepted' and not mission.get('ended_at') else 'observed' if not mission.get('ended_at') else 'completed' if state == 'Complete' else
                     'abandoned' if state.lower() in ('abandon', 'abandoned', 'cancel', 'cancelled', 'canceled') else 'failed')
            if outcome and group != outcome:
                continue
            definition = mission.get('definition_snapshot') or catalog.get(mission.get('definition_id'), {})
            ended = mission.get('ended_at')
            cutoff = (ended or now) + 10
            row = self.db.execute('SELECT at,body FROM participants WHERE mission=? AND character=? AND at<=? ORDER BY at DESC LIMIT 1',
                                  (mission['id'], mission.get('character', ''), cutoff)).fetchone()
            participant = json.loads(row[1]) if row else {}
            participant_age = max(0, (ended or now)-row[0]) if row else None
            count = participant.get('participants') if participant_age is not None and participant_age <= 90 else None
            windows = by_mission.get(mission['id'], [])
            rep = [w for w in windows if w['kind'] == 'reputation']
            wallet = [w for w in windows if w['kind'] == 'wallets' and w['track'].upper() == 'AUEC']
            comparisons = []
            for reward in definition.get('rewards', []) if mission.get('status') == 'Complete' or not ended else []:
                key = reward.get('entity', '')+'|'+reward.get('scope', '')
                matched = [w for w in rep if w['track'] == key]
                observed = matched[0]['delta'] if len(matched) == 1 and matched[0]['associated'] else None
                comparisons.append(dict(split_comparison(reward.get('configured_amount'), observed, count),
                                        faction=reward.get('faction', 'Organization'), scope=reward.get('scope', ''),
                                        entity=reward.get('entity', ''), amount_source=reward.get('amount_source', 'Extracted configuration')))
            payout = participant.get('payout', definition.get('payout')) if not ended or mission.get('status') == 'Complete' else None
            observed_money = wallet[0]['delta'] if len(wallet) == 1 and wallet[0]['associated'] else None
            money = split_comparison(payout, observed_money, count)
            ambiguous = any(not w['associated'] for w in windows)
            status = ('Active' if not ended else 'Not completed' if mission.get('status') != 'Complete' else
                      'Ambiguous window' if ambiguous else 'Observed window' if windows else
                      'Waiting for balance change' if now-ended < 120 else 'No attributable balance change')
            base = sum(c['base'] for c in comparisons if finite(c['base'])) if comparisons else None
            observed_rep = sum(w['delta'] for w in rep) if rep and not ambiguous and len({w['track'] for w in rep}) == len(rep) else None
            matches = ', '.join(dict.fromkeys(c['match'] for c in comparisons if c['observed'] is not None)) or 'Unknown'
            rows.append(dict(mission, **mission_timing(mission, now, accepted.get(mission['id'])), local_time=datetime.fromtimestamp(ended or mission.get('accepted_at') or mission['first_seen_at']).strftime('%m-%d %H:%M:%S'),
                             participants=count, last_participants=participant.get('participants'), participant_age=participant_age,
                             participant_source=participant.get('source'), own_share=participant.get('own_share'),
                             is_owner=participant.get('is_owner'), share_values=participant.get('share_values'),
                             own_share_values=participant.get('own_share_values'),
                             base_rep=base, observed_rep=observed_rep, comparisons=comparisons, split=matches,
                             base_money=payout, observed_money=observed_money, money_comparison=money,
                             analysis_status=status, windows=windows))
        total = len(rows)
        offset = max(0, min(int(offset), max(0, ((total-1)//limit)*limit)))
        latest_rep_row = self.db.execute('SELECT body FROM reputation ORDER BY at DESC LIMIT 1').fetchone()
        latest_rep = json.loads(latest_rep_row[0]).get('records', {}) if latest_rep_row else {}
        return dict(schema=1, written_at=now, count=total, offset=offset, limit=limit,
                    rows=rows[offset:offset+limit],
                    sessions=[s for s in self.session_recaps(missions, catalog, intervals) if not session or s['id'] == session],
                    changes=sorted((w for w in intervals if not session or w.get('session') == session), key=lambda row: -row['end']),
                    mission_names={m['id']: m['title'] for m in missions},
                    reputation_reads=self.db.execute('SELECT COUNT(*) FROM reputation').fetchone()[0],
                    wallet_reads=self.db.execute('SELECT COUNT(*) FROM wallets').fetchone()[0],
                    latest_rep_at=self.db.execute('SELECT MAX(at) FROM reputation').fetchone()[0],
                    latest_wallet_at=self.db.execute('SELECT MAX(at) FROM wallets').fetchone()[0],
                    latest_reputation=latest_rep,
                    unmatched=[w for w in reversed(intervals) if not w['missions']][-100:],
                    coverage='Net changes between reads. A single-completion window is a correlation; other activity can affect balances.')

    def session_recaps(self, missions, catalog, intervals=None):
        sessions = self.meta('sessions', {})
        buckets = {}
        for table in ('reputation', 'wallets'):
            for body, in self.db.execute(f'SELECT body FROM {table} ORDER BY at'):
                sample = json.loads(body)
                key = (sample.get('session', ''), sample['character'], table)
                if key[0]:
                    bounds = buckets.setdefault(key, [sample, sample])
                    bounds[1] = sample
        names = catalog.get('_names', {})
        result = []
        for sid, metadata in sorted(sessions.items(), key=lambda pair: -pair[1].get('started_at', 0)):
            own = [m for m in missions if m.get('session') == sid]
            complete = [m for m in own if m.get('status') == 'Complete']
            abandoned = [m for m in own if m.get('status', '').lower() in ('abandon', 'abandoned', 'cancel', 'cancelled', 'canceled')]
            failed = [m for m in own if m.get('ended_at') and m not in complete and m not in abandoned]
            changes = []
            money = []
            for (session, character, kind), (before, after) in buckets.items():
                if session != sid:
                    continue
                if kind == 'reputation':
                    for key in before['records'].keys() & after['records'].keys():
                        record = after['records'][key]
                        delta = record['score']-before['records'][key]['score']
                        if delta:
                            changes.append(dict(character=character, faction=names.get(record['entity'], 'Organization'),
                                                scope=record['scope'], delta=delta, before=before['records'][key]['score'], after=record['score'],
                                                baseline_at=before['read_at'], last_read_at=after['read_at']))
                else:
                    for currency in before['balances'].keys() & after['balances'].keys():
                        money.append(dict(character=character, currency=currency, before=before['balances'][currency],
                                          after=after['balances'][currency], delta=after['balances'][currency]-before['balances'][currency] if after['read_at'] != before['read_at'] else None,
                                          baseline_at=before['read_at'], last_read_at=after['read_at']))
            result.append(dict(metadata, completed=len(complete), failed=len(failed), abandoned=len(abandoned),
                               active=sum(m.get('status') == 'Accepted' and not m.get('ended_at') for m in own), reputation=changes, wallet=money))
            windows = [w for w in intervals or [] if w['kind'] == 'wallets' and w['track'] == 'AUEC'
                       and w.get('session') == sid and w['reason'] != 'Session boundary']
            result[-1]['wallet_reconciliation'] = dict(
                observed_increases=sum(w['delta'] for w in windows if w['delta'] > 0),
                observed_decreases=-sum(w['delta'] for w in windows if w['delta'] < 0),
                classified_net=sum(w['delta'] for w in windows if w.get('annotation', {}).get('category', 'unclassified') != 'unclassified'),
                inferred_mission_net=sum(w['delta'] for w in windows if w.get('classification', {}).get('source') == 'Mission completion correlation'),
                unclassified_net=sum(w['delta'] for w in windows if w.get('classification', w.get('annotation', {})).get('category', 'unclassified') == 'unclassified'))
        return result

    def export(self, path, catalog=None):
        path = Path(path).resolve()
        if path.suffix.lower() not in ('.csv', '.json', '.html') or path.parent == self.directory.resolve():
            raise ValueError('Choose a CSV, JSON or HTML export outside the application data folder')
        self.db.execute('SAVEPOINT mission_export')
        try:
            view = self.view(catalog, limit=1_000_000)
            if path.suffix.lower() == '.json':
                view['evidence'] = {table: [json.loads(row[0]) for row in self.db.execute(f'SELECT body FROM {table}')]
                                    for table in ('events', 'reputation', 'wallets', 'participants', 'annotations')}
            self.db.execute('RELEASE mission_export')
        except Exception:
            self.db.execute('ROLLBACK TO mission_export')
            self.db.execute('RELEASE mission_export')
            raise
        if path.suffix.lower() == '.json':
            path.write_text(json.dumps(view, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        elif path.suffix.lower() == '.html':
            from mission_log_report import html_report
            path.write_text(html_report(view, catalog), encoding='utf-8')
        else:
            fields = ['record_type', 'id', 'local_time', 'title', 'status', 'accepted_log_at', 'ended_at', 'duration_seconds', 'timing_status', 'timing_note', 'participants', 'base_rep', 'observed_rep',
                      'split', 'base_money', 'observed_money', 'track', 'before', 'after', 'net_change', 'category', 'classification_source', 'mission_title', 'mission_giver', 'reward_organizations', 'analysis_status']
            with path.open('w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.DictWriter(stream, fields, extrasaction='ignore')
                writer.writeheader()
                rows = [dict(row, record_type='mission') for row in view['rows']]
                rows += [dict(record_type=w['kind'], local_time=datetime.fromtimestamp(w['end']).isoformat(),
                              title='; '.join(view['mission_names'].get(mid, mid) for mid in w['missions']), track=w['track'],
                              before=w['before'], after=w['after'], net_change=w['delta'], analysis_status=w['reason'],
                              category=w.get('classification', w.get('annotation', {})).get('category', 'unclassified'),
                              classification_source=w.get('classification', w.get('annotation', {})).get('source', ''),
                              mission_title=w.get('classification', {}).get('mission_title', ''),
                              mission_giver=w.get('classification', {}).get('mission_giver') or '',
                              reward_organizations='; '.join(w.get('classification', {}).get('reward_organizations', []))) for w in view['changes']]
                for row in rows:
                    # Spreadsheet text must not turn a mission title into a formula.
                    writer.writerow({k: "'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v
                                     for k, v in row.items() if k in fields})
        return len(view['rows'])
