"""Small, filter-independent HUD projection of the existing mission ledger."""
from mission_log import format_duration as duration
from mission_log_report import number, clock


def snapshot(view, quest, session, *, now, recording, owner_pid=0, game_running=True, names=None):
    names = names or {}
    active_ids = set(quest.get('active_ids', [])) if game_running else set()
    selected = quest.get('selected_id')
    if not selected:
        matches = [row['id'] for row in view['rows'] if row['id'] in active_ids and row['title'] == quest.get('title')]
        if len(matches) == 1:selected = matches[0]
    row = next((row for row in view['rows'] if row['id'] == selected and row['id'] in active_ids and not row.get('ended_at')), None)
    active = {}
    if row:
        lines = []
        if row.get('objective'):lines.append('Objective: '+row['objective'])
        if row.get('base_money') is not None:lines.append('Listed payout: '+number(row['base_money'])+' aUEC')
        else:lines.append('Payout: source unavailable')
        count = row.get('participants')
        lines.append('Accepted participants: '+(str(count) if count else 'unknown'))
        if count and count > 1 and row.get('base_money') is not None:
            lines.append('Equal-split estimate: '+number(row['base_money']/count)+' aUEC each')
        for reward in row['comparisons'][:3]:
            lines.append(reward['faction']+' / '+reward['scope']+': '+number(reward['base'], True)+' base rep')
            if count and count > 1 and reward.get('equal_split') is not None:
                lines.append('Equal-split estimate: '+number(reward['equal_split'], True)+' rep each')
        active = dict(id=row['id'], title=row['title'], accepted_log_at=row.get('accepted_log_at'),
                      elapsed_seconds=row.get('elapsed_seconds'), timing_status=row.get('timing_status'),
                      lines=lines[:7], timing_note=row.get('timing_note'))
    changes = [w for w in view.get('changes', []) if session and w.get('session') == session]
    wallet = [w for w in changes if w['kind'] == 'wallets' and w['track'].upper() == 'AUEC']
    rep = [w for w in changes if w['kind'] == 'reputation']
    def entries(values, reputation=False):
        result = []
        for change in sorted(values, key=lambda w: -w['end'])[:4]:
            classification = change.get('classification') or change.get('annotation') or {}
            label = classification.get('category', 'unclassified').replace('_', ' ')
            if classification.get('source') == 'Mission completion correlation':label = 'Mission · '+classification.get('mission_title', '')
            if reputation:
                entity, _, scope = change['track'].partition('|')
                label = names.get(entity, 'Organization')+('' if scope.casefold()=='factionreputation' else ' / '+scope)
            result.append(dict(label=label, delta=change['delta'], at=change['end'],
                               before=change.get('before'), after=change.get('after'),
                               time=clock(change['end']), associated=change.get('associated', False),
                               classification_source=classification.get('source', ''),
                               reward_organizations=classification.get('reward_organizations', [])))
        return result
    ended = sorted((r for r in view['rows'] if r.get('ended_at')), key=lambda r: -r['ended_at'])[:4]
    runs = [dict(id=r['id'], title=r['title'], status=r.get('status'), duration_seconds=r.get('duration_seconds'),
                 duration=duration(r.get('duration_seconds')), at=r['ended_at'],
                 money=r.get('observed_money'), rep=r.get('observed_rep')) for r in ended]
    completions = sorted((r for r in view['rows'] if r.get('status') == 'Complete' and r.get('ended_at')),
                         key=lambda r: -r['ended_at'])
    completion = {}
    if completions:
        last = completions[0]
        comparisons = last.get('comparisons', [])
        comparison = comparisons[0] if len(comparisons) == 1 else {}
        count = last.get('participants')
        lines = ['Observed rep: '+number(last.get('observed_rep'), True)+' · configured base: '+number(last.get('base_rep')),
                 'Accepted participants: '+(str(count) if count else 'unknown')]
        for c in comparisons[:2]:
            track = c.get('entity', '')+'|'+c.get('scope', '')
            windows = [w for w in last.get('windows', []) if w['kind']=='reputation' and w['track']==track and w.get('associated')]
            if len(windows)==1:
                lines.append(c['faction']+': '+number(windows[0]['before'])+' → '+number(windows[0]['after']))
            lines.append(c['faction']+': '+c.get('match', 'Unknown'))
        lines.append('Observed aUEC: '+number(last.get('observed_money'), True))
        previous = last.get('session') != session
        completion = dict(id=last['id'], title=last['title'], at=last['ended_at'], time=('Previous session · ' if previous else '')+clock(last['ended_at']),
                          duration=duration(last.get('duration_seconds')), rep_observed=last.get('observed_rep'),
                          rep_base=last.get('base_rep'), participants=count, comparison=('Previous session · ' if previous else '')+comparison.get('match', 'Unknown'), lines=lines[:7])
    current = next((s for s in view.get('sessions', []) if s['id'] == session), {})
    funds = next((w for w in current.get('wallet', []) if w.get('currency') == 'AUEC'), {})
    return dict(schema=1, written_at=now, owner_pid=owner_pid, recording=recording,
                session=session, active=active, active_count=len(active_ids),
                wallet=dict(incoming=sum(w['delta'] for w in wallet if w['delta']>0),
                            outgoing=-sum(w['delta'] for w in wallet if w['delta']<0),
                            balance=funds.get('after'), entries=entries(wallet)),
                reputation=dict(entries=entries(rep, True)), runs=runs, latest_completion=completion,
                note='Observed net changes between reads; not itemized transactions.',
                timing_note='Wall time from acceptance to outcome; includes menus and time away.')
