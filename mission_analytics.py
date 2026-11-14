"""Faction, category, daily and session analytics derived only from observed ledger windows.

Every figure is a net balance window between reads. Money is credited to a faction only
when exactly one completed mission explains the window (the logger's own correlation);
everything else stays under Unattributed. Nothing here is an itemized receipt.
"""
from datetime import datetime

from mission_log import CATEGORIES
from reputation_ranks import standing_progression, primary_record_for_faction

CORRELATION = 'Mission completion correlation'
UNATTRIBUTED = 'Unattributed'


def _windows(view):
    return [w for w in view.get('changes', []) if w.get('reason') != 'Session boundary'
            and type(w.get('delta')) in (int, float)]


def _wallet(view):
    return [w for w in _windows(view) if w.get('kind') == 'wallets' and str(w.get('track', '')).upper() == 'AUEC']


def _balance_history(view, max_points=120):
    """Reconstruct a time-ordered balance curve from wallet windows, downsampled to max_points."""
    wins = sorted(
        [w for w in _wallet(view) if type(w.get('before')) in (int, float) and type(w.get('after')) in (int, float)],
        key=lambda w: w['start']
    )
    if not wins:
        return []
    pts = [{'at': wins[0]['start'], 'auec': int(wins[0]['before'])}]
    for w in wins:
        pts.append({'at': w['end'], 'auec': int(w['after'])})
    if len(pts) <= max_points:
        return pts
    # Downsample: always keep first and last
    step = (len(pts) - 1) / (max_points - 1)
    return [pts[round(i * step)] for i in range(max_points - 1)] + [pts[-1]]


def analyze(view, names=None, now=0, days=30):
    names = names or {}
    wallet = _wallet(view)
    gains = sum(w['delta'] for w in wallet if w['delta'] > 0)
    losses = -sum(w['delta'] for w in wallet if w['delta'] < 0)

    factions = {}

    def bucket(name):
        return factions.setdefault(name, dict(name=name, auec=0, missions=0, rep_net=0, mission_titles=[]))

    top = []
    for w in wallet:
        cls = w.get('classification') or {}
        if w['delta'] <= 0 or cls.get('source') != CORRELATION:
            continue
        giver = cls.get('mission_giver')
        orgs = cls.get('reward_organizations') or []
        name = names.get(giver, giver) if giver else (orgs[0] if orgs else UNATTRIBUTED)
        if name == UNATTRIBUTED:
            continue  # Keep unattributed out of faction bars; it appears in totals only
        entry = bucket(name)
        entry['auec'] += w['delta']
        entry['missions'] += 1
        top.append(dict(title=cls.get('mission_title', 'Mission'), faction=name, auec=w['delta'], at=w['end']))
    for w in _windows(view):
        if w.get('kind') != 'reputation':
            continue
        entity = str(w.get('track', '')).partition('|')[0]
        bucket(names.get(entity, 'Organization'))['rep_net'] += w['delta']

    latest_rep = view.get('latest_reputation', {})
    by_faction_records = {}
    if isinstance(latest_rep, dict):
        for rec in latest_rep.values():
            if isinstance(rec, dict) and rec.get('entity'):
                fac_name = names.get(rec['entity'])
                if fac_name:
                    by_faction_records.setdefault(fac_name, []).append(rec)

    for fac_name, recs in by_faction_records.items():
        if fac_name not in factions:
            primary = primary_record_for_faction(recs)
            if primary and (primary.get('score') or 0) > 0:
                bucket(fac_name)

    ranked = sorted(factions.values(), key=lambda f: (-f['auec'], -abs(f['rep_net']), -(f.get('rep_score') or 0), f['name']))
    for f in ranked:
        f['avg_per_mission'] = round(f['auec']/f['missions']) if f['missions'] else None
        f.pop('mission_titles', None)
        recs = by_faction_records.get(f['name'], [])
        primary = primary_record_for_faction(recs)
        if primary:
            prog = standing_progression(primary.get('scope'), primary.get('score'))
            if prog:
                f['standing'] = prog['current_rank']
                f['next_standing'] = prog['next_rank']
                f['points_to_next'] = prog['points_needed']
                f['rep_progress_pct'] = prog['progress_pct']
                f['rep_score'] = prog['score']
                f['scope'] = prog['scope_display']
                f['is_max_rank'] = prog['is_max']
    attributed = sum(f['auec'] for f in ranked if f['name'] != UNATTRIBUTED)

    promotions = []
    for w in view.get('changes', []):
        promo = w.get('promotion')
        if promo:
            entity, _, scope = str(w.get('track', '')).partition('|')
            fac_name = names.get(entity, 'Organization')
            promotions.append(dict(
                faction=fac_name,
                rank=promo['rank'],
                threshold=promo.get('threshold'),
                previous_rank=promo.get('previous_rank'),
                scope=promo.get('scope', scope),
                scope_display=promo.get('scope_display', scope),
                delta=w.get('delta'),
                at=w.get('end', 0)
            ))
    promotions.sort(key=lambda p: -p['at'])

    categories = {}
    for w in wallet:
        cls = w.get('classification') or w.get('annotation') or {}
        key = cls.get('category', 'unclassified')
        # For price-matched purchases, upgrade the category label with the item name
        label = CATEGORIES.get(key, 'Unclassified')
        if cls.get('price_match') and cls.get('item_name'):
            label = cls['item_name']
        row = categories.setdefault(key + (('|' + cls.get('item_id', '')) if cls.get('price_match') else ''),
                                    dict(key=key, label=label, gain=0, loss=0))
        if w['delta'] > 0:
            row['gain'] += w['delta']
        else:
            row['loss'] += -w['delta']

    daily = {}
    for w in wallet:
        day = datetime.fromtimestamp(w['end']).strftime('%Y-%m-%d')
        row = daily.setdefault(day, dict(day=day, gain=0, loss=0))
        if w['delta'] > 0:
            row['gain'] += w['delta']
        else:
            row['loss'] += -w['delta']
    daily_rows = sorted(daily.values(), key=lambda r: r['day'])[-days:]
    for row in daily_rows:
        row['net'] = row['gain']-row['loss']

    sessions = []
    for s in view.get('sessions', [])[:12]:
        auec = [r['delta'] for r in s.get('wallet', []) if r.get('currency') == 'AUEC' and r.get('delta') is not None]
        sessions.append(dict(id=s.get('id', ''), started_at=s.get('started_at'), ended_at=s.get('ended_at'),
                             net=sum(auec) if auec else None, completed=s.get('completed', 0)))

    completed = sum(1 for r in view.get('rows', []) if r.get('status') == 'Complete')
    balance_history = _balance_history(view)
    return dict(totals=dict(gains=gains, losses=losses, net=gains-losses, attributed=attributed,
                            unattributed_gain=max(0, gains-attributed), missions_completed=completed),
                factions=ranked[:20], categories=sorted(categories.values(), key=lambda r: -(r['gain']+r['loss'])),
                daily=daily_rows, sessions=sessions,
                top_missions=sorted(top, key=lambda r: -r['auec'])[:8],
                balance_history=balance_history,
                promotions=promotions[:10],
                note='Net balance windows between reads. Faction money counts only single-completion windows; it is not an itemized receipt.')
