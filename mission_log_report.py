"""Readable mission/wallet views. Unknown observations stay unknown."""
from datetime import datetime
from html import escape
import math
from mission_log import CATEGORIES, format_duration


def number(value, signed=False):
    if value is None:
        return '—'
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return '—'
    return (f'{value:+,.2f}' if signed else f'{value:,.2f}').rstrip('0').rstrip('.')


def clock(at):
    return datetime.fromtimestamp(at).strftime('%m-%d %H:%M:%S') if at else 'Unknown'


def mission_detail(row):
    lines = [row['title'], f"Outcome: {row.get('status') or 'Active'}", f"Analysis: {row['analysis_status']}",
             f"Accepted (log): {clock(row.get('accepted_log_at'))} | Ended: {clock(row.get('ended_at'))}",
             'Duration: '+format_duration(row.get('duration_seconds') if row.get('ended_at') else row.get('elapsed_seconds')),
             row.get('timing_note', 'Acceptance time was not observed.'),
             f"Participants: {row.get('participants') or 'Unknown'}"]
    lines.append('Mission role: '+('Owner' if row.get('is_owner') is True else 'Shared recipient' if row.get('is_owner') is False else 'Unknown'))
    if row.get('last_participants') and not row.get('participants'):
        lines.append(f"Last count was {row['last_participants']}; observation is too old for split comparisons.")
    if row.get('own_share') is not None:
        lines.append(f"Service participation share: {row['own_share']:.4g} (not proof of a reputation rule)")
    elif row.get('own_share_values'):
        lines.append(f"Service share values: {row['own_share_values']} (not interpreted as a reputation-split rule)")
    for comparison in row['comparisons']:
        lines.extend([f"{comparison['faction']} / {comparison['scope']}: base {number(comparison['base'])}; observed net {number(comparison['observed'], True)}",
                      f"  Equal split: {number(comparison['equal_split'])}; {comparison['match']}",
                      f"  Base source: {comparison['amount_source']}"])
    lines.append(f"Listed aUEC: {number(row['base_money'])}; equal split: {number(row['money_comparison']['equal_split'])}; wallet net: {number(row['observed_money'], True)}")
    for window in row['windows']:
        lines.append(f"{window['kind']} {window['track']}: {number(window['before'])} → {number(window['after'])} ({number(window['delta'], True)}) | {clock(window['start'])}–{clock(window['end'])} | {window['reason']}")
    lines.extend(['', 'A balance window is a correlation, not a transaction receipt. Purchases, transfers, other rewards and penalties can affect it.',
                  'Unobserved changes stay unknown. Equal-split and full-reward matches are comparisons, not confirmed game rules.', f"Mission ID: {row['id']}"])
    return '\n'.join(lines)


def present(view, catalog=None, mode='all', direction='', category='', query='', offset=0, limit=100):
    catalog = catalog or {}
    names = catalog.get('_names', {})
    by_id = {r['id']: r for r in view['rows']}
    entries = []
    mission_mode = mode in ('missions', 'rewards')
    if mode in ('all', 'missions', 'rewards') and not category:
        for row in view['rows']:
            if mode == 'rewards' and row.get('status') != 'Complete':
                continue
            detail = mission_detail(row)
            if query.casefold() not in detail.casefold():
                continue
            delta = row['observed_rep']
            values = [v for v in (delta, row['observed_money']) if v is not None]
            if direction and not any(v > 0 if direction == 'gains' else v < 0 for v in values):
                continue
            cells = ([row['local_time'], row['title'], row.get('status') or 'Active', format_duration(row.get('duration_seconds') if row.get('ended_at') else row.get('elapsed_seconds')), str(row.get('participants') or '—'),
                      number(row['base_rep']), number(delta, True), row['split'], number(row['base_money']), number(row['observed_money'], True)]
                     if mission_mode else [row['local_time'], 'Mission', row['title'], row.get('status') or 'Active',
                                           number(delta, True), number(row['observed_money'], True), row['analysis_status']])
            entries.append(dict(id='mission:'+row['id'], at=row.get('ended_at') or row.get('accepted_at') or row['first_seen_at'],
                                session=row.get('session', ''), cells=cells, detail=detail))
    if mode in ('all', 'reputation', 'wallet'):
        for change in view.get('changes', []):
            wallet = change['kind'] == 'wallets'
            annotation = change.get('annotation', {})
            classification = change.get('classification', annotation)
            inferred = classification.get('source') == 'Mission completion correlation'
            category_key = classification.get('category', 'unclassified')
            category_label = CATEGORIES.get(category_key, 'Unclassified')
            if inferred: category_label += ' (correlated)'
            if classification.get('price_match') and classification.get('item_name'):
                category_label = classification['item_name'] + ' (price match)'
            if category and (not wallet or category != category_key):
                continue
            if wallet and change['track'].upper() != 'AUEC':
                continue
            if mode == 'reputation' and wallet or mode == 'wallet' and not wallet:
                continue
            if direction and (change['delta'] <= 0 if direction == 'gains' else change['delta'] >= 0):
                continue
            titles = [view.get('mission_names', {}).get(m, by_id.get(m, {}).get('title', m)) for m in change['missions']]
            entity, _, scope = change['track'].partition('|')
            promo = change.get('promotion') or classification.get('promotion')
            title = 'aUEC wallet' if wallet else names.get(entity, 'Organization')+' / '+scope
            association = '; '.join(titles) or 'No matching mission'
            detail = (f"{title}\nObserved net change: {number(change['delta'], True)}\n"
                      f"Before: {number(change['before'])} at {clock(change['start'])}\n"
                      f"After: {number(change['after'])} at {clock(change['end'])}\n"
                      f"Analysis: {change['reason']}\nMissions in window: {association}\n"
                      f"Category: {category_label}"+(' (player classification)' if annotation else '')+'\n'
                      +f"Classification source: {classification.get('source', 'Unclassified')}\n"
                      +('Reward organization: '+', '.join(classification['reward_organizations'])+'\n' if classification.get('reward_organizations') else '')
                      +('Mission giver: '+classification['mission_giver']+'\n' if classification.get('mission_giver') else '')
                      +('Matched item: '+classification['item_name']+(' at '+classification['shop'] if classification.get('shop') else '')+'\n' if classification.get('price_match') and classification.get('item_name') else '')
                      + (f"Note: {annotation['note']}\n" if annotation.get('note') else '')+'\n'
                      + (f"PROMOTION MILESTONE: Promoted to {promo['rank']} (Threshold: {number(promo.get('threshold'))} rep)!\n\n" if promo else '')
                      +'These are balance observations. Changes between reads can combine multiple rewards, purchases, transfers or penalties. '
                      'The logger cannot reconstruct offsetting transactions from balance snapshots. No mission match is treated as an unexplained change, not a zero reward.')
            if query.casefold() not in detail.casefold():
                continue
            if wallet:
                detail += '\n\nRight-click this wallet entry to classify a cause you recognize. A label does not turn a net balance window into an itemized receipt.'
            promo_label = f"Promotion: {promo['rank']}" if promo else None
            cells = ([clock(change['end']), title if not wallet else category_label, promo_label or ('Increase' if change['delta'] > 0 else 'Decrease'),
                      number(change['before']), number(change['after']), number(change['delta'], True), association, change['reason']]
                     if mode in ('reputation', 'wallet') else
                     [clock(change['end']), 'Wallet' if wallet else ('Promotion' if promo else 'Reputation'),
                      (category_label+': '+classification.get('mission_title', title)) if wallet else (f"{title} (Promoted to {promo['rank']})" if promo else title),
                      promo_label or ('Increase' if change['delta'] > 0 else 'Decrease'),
                      '—' if wallet else number(change['delta'], True), number(change['delta'], True) if wallet else '—', change['reason']])
            entries.append(dict(id='change:'+change['id'], change_id=change['id'], is_wallet=wallet, category=category_key,
                                is_promotion=bool(promo), promotion=promo,
                                session=change.get('session', ''), at=change['end'], cells=cells, detail=detail))
    if mode == 'sessions':
        for session in view.get('sessions', []):
            rep = '\n'.join(f"{r['faction']} / {r['scope']}: {number(r['delta'], True)} ({number(r['before'])} → {number(r['after'])}); reads {clock(r['baseline_at'])}–{clock(r['last_read_at'])}" for r in session['reputation']) or 'No verified reputation change recorded.'
            wallet = '\n'.join(f"{r['currency']}: {number(r['delta'], True)} ({number(r['before'])} → {number(r['after'])}); reads {clock(r['baseline_at'])}–{clock(r['last_read_at'])}" for r in session['wallet']) or 'Wallet coverage unavailable.'
            detail = f"Session started {clock(session['started_at'])}\nEnded: {clock(session.get('ended_at'))}\nCompleted: {session['completed']} | Failed/other endings: {session['failed']} | Abandoned/cancelled: {session['abandoned']} | Active: {session['active']}\n\nReputation\n{rep}\n\nWallet\n{wallet}\n\nTotals are net differences between the first and last retained reads for each character in this session. Detailed logging may cover only part of the session."
            reconciliation = session.get('wallet_reconciliation', {})
            detail += (f"\n\nWallet reconciliation\nObserved increases: {number(reconciliation.get('observed_increases'), True)} aUEC"
                       f"\nObserved decreases: {number(reconciliation.get('observed_decreases'))} aUEC"
                       f"\nPlayer-classified net: {number(reconciliation.get('classified_net'), True)} aUEC"
                       f"\nCorrelated mission inflows: {number(reconciliation.get('inferred_mission_net'), True)} aUEC"
                       f"\nUnclassified net: {number(reconciliation.get('unclassified_net'), True)} aUEC"
                       '\nIncreases/decreases are totals of observed net windows, not itemized gross transactions.')
            if query.casefold() not in detail.casefold():
                continue
            auec = [r['delta'] for r in session['wallet'] if r['currency'] == 'AUEC' and r['delta'] is not None]
            entries.append(dict(id='session:'+session['id'], at=session['started_at'], detail=detail, session=session['id'],
                                cells=[clock(session['started_at']), clock(session.get('ended_at')) if session.get('ended_at') else 'Open', str(session['completed']),
                                       str(session['failed']), str(session['abandoned']), str(len(session['reputation']))+' tracks', number(sum(auec), True) if auec else '—']))
    entries.sort(key=lambda row: -row['at'])
    columns = ([['Time', 108], ['Mission', 240], ['Outcome', 82], ['Duration', 94], ['People', 54], ['Base rep', 68], ['Rep Δ', 65], ['Comparison', 150], ['Listed aUEC', 90], ['Wallet Δ', 90]] if mission_mode else
               [['Last read', 112], ['Account / track', 190], ['Direction', 76], ['Before', 90], ['After', 90], ['Net Δ', 85], ['Mission window', 180], ['Analysis', 170]] if mode in ('wallet', 'reputation') else
               [['Started', 120], ['Ended', 120], ['Completed', 95], ['Failed / other', 95], ['Abandoned', 95], ['Rep changes', 110], ['aUEC net', 120]] if mode == 'sessions' else
               [['Time', 110], ['Type', 85], ['Activity', 270], ['Outcome', 85], ['Rep net Δ', 85], ['aUEC net Δ', 100], ['Analysis', 220]])
    count = len(entries)
    offset = max(0, min(int(offset), max(0, ((count-1)//limit)*limit)))
    if mode == 'wallet':
        columns[1][0] = 'Category'
        columns[1][1] = 140
    return dict(columns=columns, entries=entries[offset:offset+limit], display_count=count, display_offset=offset, display_limit=limit,
                mode=mode, direction=direction)


def html_report(view, catalog=None):
    def table(headers, rows):
        return '<table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    parts = ['<!doctype html><meta charset="utf-8"><title>SynthScan mission & wallet report</title><style>body{font:15px system-ui;margin:36px;color:#182433}h1,h2{color:#164865}table{border-collapse:collapse;width:100%;margin:18px 0 35px}td,th{border-bottom:1px solid #ccd5dd;text-align:left;padding:9px;vertical-align:top}th{background:#edf4f8}p{max-width:1000px;line-height:1.5}</style><h1>SynthScan mission & wallet report</h1>',
             '<p>Generated '+escape(clock(view['written_at']))+'. Net balance changes are observations. Mission association and split matches are comparisons; they are not confirmed transaction receipts. Offsetting transactions between polls may be invisible.</p>']
    for mode, title in [('sessions', 'Session recaps'), ('missions', 'Mission outcomes and rewards'), ('reputation', 'Reputation changes, including losses'), ('wallet', 'Observed aUEC increases and decreases')]:
        data = present(view, catalog, mode=mode, limit=1_000_000)
        parts.extend(['<h2>'+title+'</h2>', table([c[0] for c in data['columns']], [r['cells'] for r in data['entries']])])
        if mode in ('sessions', 'missions'):
            for entry in data['entries']:
                summary = entry['cells'][0] if mode == 'sessions' else entry['cells'][1]
                parts.append('<details><summary>'+escape(summary)+' — evidence and reconciliation</summary><pre style="white-space:pre-wrap;line-height:1.5">'+escape(entry['detail'])+'</pre></details>')
        if mode == 'wallet':
            parts.append('<p>Wallet labels distinguish player classifications from mission-completion correlations. Unclassified net inflows/outflows remain visible. Purchases, transfers, repairs and fuel costs are not automatically itemized by the balance source.</p>')
    return '\n'.join(parts)
