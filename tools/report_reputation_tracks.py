"""Build the per-scope research matrix; unknown balances stay unknown."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def record_path(value):
    return value.replace('\\', '/').split('libs/foundry/records/', 1)[-1]


def main():
    folder = ROOT / 'research/reputation_12913470'
    audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
    lines = ['# Per-track reputation research matrix', '',
             'Build 12913470. These are extracted configurations, not live-account verification.', '',
             'Each organization + scope is a separate balance. Shared career names must not merge balances. '
             'All current balances, party payout rules and bar-normalization formulas remain unverified.', '',
             '| Scope | Referenced organizations/contacts | Configured minima | Gated standings | Nonzero drift standings | Mission definitions with rewards |',
             '|---|---|---|---:|---:|---:|']
    details = []
    for scope in audit['scopes']:
        organizations = sorted({t['faction'] for t in audit['faction_tracks'] if t['scope'] == scope['name']})
        referenced_missions = []
        for mission in audit['missions']:
            if any(record_path(r['references'].get('reputationScope') or '') == record_path(scope['source'])
                   for outcome in mission['outcomes'] for r in outcome['rewards']):
                referenced_missions.append(mission['id'])
        standings = sorted(scope['standings'], key=lambda s: s['minimum'])
        minima = ', '.join(f"{s['minimum']:,}" for s in standings)
        gated = sum(bool(s['gated']) for s in standings)
        drift = sum(bool(s['drift']) for s in standings)
        lines.append(f"| {scope['name']} | {', '.join(organizations) or 'No UI association found'} | {minima} | {gated} | {drift} | {len(referenced_missions)} |")
        details.append(dict(scope=scope['name'], organizations=organizations, standings=standings,
                            mission_ids=referenced_missions, current_balance=None,
                            party_distribution='unverified', bar_normalization='unverified',
                            live_balance_source='unverified'))
    lines.extend(['', '## Interpretation', '',
                  '* Counts include tests and unreleased/obsolete variants; each needs an availability check.',
                  '* Gated standings can require an additional unlock, even when the point threshold is met.',
                  '* Nonzero drift is a configured value, not a validated running timer or decay direction.',
                  '* No UI association does not prove a scope is unused; mission/service references are separate evidence.',
                  '* Repeated history entries or task names are not proof of a payout amount.',
                  '* Never estimate the current balance by assuming that an existing account started at zero.',
                  '* Use observed before/after balances to measure payouts. If other reputation changes occur in the interval, attribution is ambiguous.',
                  '* GetScoreHistory returns score/timestamp series in the extracted service API. That is not, by itself, a task-completion counter.',
                  '* For shared contracts, determine the eligible recipients and the actual awarded delta; party size alone is insufficient evidence.',
                  '* Refresh or invalidate observations when build, character or progression/reset context changes.', ''])
    (folder / 'TRACK_MATRIX.md').write_text('\n'.join(lines), encoding='utf-8')
    (folder / 'track_evaluations.json').write_text(json.dumps(details, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {len(details)} track evaluations; every current balance remains explicitly unknown.')


if __name__ == '__main__':
    main()
