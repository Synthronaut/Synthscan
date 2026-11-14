"""Reputation standing thresholds, rank progression, and promotion detection.

Loads verified Star Citizen reputation scope definitions and standings from game data.
Provides exact standing progression (current rank, next rank, rep needed, progress %)
and detects rank promotions across observed reputation windows.
"""
import json
import logging
from pathlib import Path

_SCOPES_CACHE = None
_LOGGER = logging.getLogger('synthscan.reputation')

# Scopes prioritised for player-facing rank progression
PREFERRED_CAREER_SCOPES = (
    'FactionReputation',
    'Hauling',
    'BountyHunter',
    'BountyHunter_BountyHuntersGuild',
    'Salvaging',
    'Security',
    'Security_MercenaryGuild',
    'Courier',
    'Courier_TransportGuild',
    'Maintenance',
    'Smuggling',
    'Theft',
    'Assassination',
    'MissionProviderReputation_Battaglia',
)


def load_scopes(audit_path=None):
    """Load and index scope standings from audit.json, caching the result in memory."""
    global _SCOPES_CACHE
    if _SCOPES_CACHE is not None and audit_path is None:
        return _SCOPES_CACHE

    path = None
    if audit_path:
        path = Path(audit_path)
    else:
        try:
            from installation import reference_paths
            ref = reference_paths()
            if 'audit' in ref and Path(ref['audit']).exists():
                path = Path(ref['audit'])
        except Exception:
            pass

        if not path or not path.exists():
            # Fallback to relative research directory
            candidate = Path(__file__).resolve().parent / 'research' / 'reputation_12913470' / 'audit.json'
            if candidate.exists():
                path = candidate

    if not path or not path.exists():
        _LOGGER.warning('reputation_ranks: audit.json not found at %s', path)
        return {}

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        scopes_dict = {}
        for s in data.get('scopes', []):
            name = s.get('name')
            if not name:
                continue
            standings = []
            for st in s.get('standings', []):
                s_name = (st.get('name') or '').strip()
                standings.append({
                    'name': s_name,
                    'minimum': int(st.get('minimum', 0)),
                    'gated': bool(st.get('gated', False)),
                    'localization_key': st.get('localization_key', '')
                })
            # Sort by minimum ascending
            standings.sort(key=lambda item: item['minimum'])
            scopes_dict[name] = {
                'name': name,
                'display_name': s.get('display_name') or name,
                'localization_key': s.get('localization_key', ''),
                'standings': standings
            }
        _SCOPES_CACHE = scopes_dict
        return _SCOPES_CACHE
    except Exception as exc:
        _LOGGER.exception('Failed to load reputation scopes: %s', exc)
        return {}


def standing_progression(scope_name, score):
    """Return rank progression info for a given scope and score.

    Returns dict with keys:
        current_rank: str
        next_rank: str | None
        current_min: int
        next_min: int | None
        score: int
        points_needed: int
        progress_pct: float (0.0 to 100.0)
        is_max: bool
        scope_display: str
    Or None if the scope is unknown or has no named standings.
    """
    if score is None or type(score) not in (int, float):
        return None

    scopes = load_scopes()
    sc = scopes.get(scope_name)
    if not sc:
        return None

    # Only consider standings with non-empty human-readable names
    valid = [s for s in sc['standings'] if s['name']]
    if not valid:
        return None

    score_val = int(round(score))

    # If score is non-negative, filter out negative prerequisite/penalty tiers like -1000
    positives = [s for s in valid if s['minimum'] >= 0]
    if positives and score_val >= 0:
        valid = positives

    cur = valid[0]
    for s in valid:
        if score_val >= s['minimum']:
            cur = s
        else:
            break

    next_s = next((s for s in valid if s['minimum'] > score_val), None)

    if next_s:
        cur_min = cur['minimum']
        next_min = next_s['minimum']
        tier_range = next_min - cur_min
        tier_progress = max(0, score_val - cur_min)
        pct = min(100.0, max(0.0, round((tier_progress / tier_range) * 100, 1))) if tier_range > 0 else 0.0
        return {
            'current_rank': cur['name'],
            'next_rank': next_s['name'],
            'current_min': cur_min,
            'next_min': next_min,
            'score': score_val,
            'points_needed': max(0, next_min - score_val),
            'progress_pct': pct,
            'is_max': False,
            'scope_display': sc.get('display_name') or scope_name,
        }
    else:
        return {
            'current_rank': cur['name'],
            'next_rank': None,
            'current_min': cur['minimum'],
            'next_min': None,
            'score': score_val,
            'points_needed': 0,
            'progress_pct': 100.0,
            'is_max': True,
            'scope_display': sc.get('display_name') or scope_name,
        }


def detect_promotion(scope_name, before_score, after_score):
    """Detect if a reputation change crossed a rank promotion threshold.

    Returns dict with keys {rank, threshold, previous_rank, scope, scope_display} or None.
    """
    if before_score is None or after_score is None:
        return None
    try:
        before_val = int(round(before_score))
        after_val = int(round(after_score))
    except (ValueError, TypeError):
        return None

    if after_val <= before_val:
        return None

    scopes = load_scopes()
    sc = scopes.get(scope_name)
    if not sc:
        return None

    valid = [s for s in sc['standings'] if s['name']]
    if not valid:
        return None

    # Filter out negative gate minimums if crossing positive numbers
    if before_val >= 0:
        valid = [s for s in valid if s['minimum'] >= 0]

    promotions = [s for s in valid if before_val < s['minimum'] <= after_val]
    if not promotions:
        return None

    highest = promotions[-1]
    # Previous rank before the threshold
    prev_ranks = [s for s in valid if s['minimum'] <= before_val]
    prev_rank_name = prev_ranks[-1]['name'] if prev_ranks else None

    return {
        'rank': highest['name'],
        'threshold': highest['minimum'],
        'previous_rank': prev_rank_name,
        'scope': scope_name,
        'scope_display': sc.get('display_name') or scope_name,
    }


def primary_record_for_faction(records):
    """Given a list or dict of reputation records for an entity, pick the best standing track."""
    if not records:
        return None
    rec_list = list(records.values()) if isinstance(records, dict) else list(records)
    if not rec_list:
        return None

    # Filter for scopes with known named standings
    scopes = load_scopes()
    valid_recs = [r for r in rec_list if r.get('scope') in scopes and any(s['name'] for s in scopes[r['scope']]['standings'])]
    if not valid_recs:
        return None

    # Match preferred career scopes in order
    for preferred in PREFERRED_CAREER_SCOPES:
        for r in valid_recs:
            if r.get('scope') == preferred:
                return r

    return valid_recs[0]
