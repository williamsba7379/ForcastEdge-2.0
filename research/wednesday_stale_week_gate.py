"""Isolated research-only validation. No production imports, writes, or network."""
from datetime import datetime, timezone

class GateError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def timestamp(value):
    try:
        x = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if x.tzinfo is None:
            raise ValueError('naive')
        return x.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        raise GateError('INVALID_TIMESTAMP')

def check(target, schedule, draft, shadow):
    """Fail closed before any freeze, grade, or write; returns validated IDs only."""
    if target.get('operation') != 'WEDNESDAY_FREEZE':
        raise GateError('INVALID_OPERATION')
    if target.get('season') != schedule.get('season'):
        raise GateError('TARGET_SCHEDULE_MISMATCH')
    week = next((w for w in schedule.get('weeks', []) if w.get('week') == target.get('week')), None)
    if week is None:
        raise GateError('TARGET_WEEK_MISSING')
    captured = timestamp(schedule.get('updatedAt'))
    cutoff = timestamp(target.get('cutoff_at'))
    if captured > cutoff:
        raise GateError('POST_CUTOFF_SCHEDULE')
    games = week.get('games', [])
    ids = [str(g.get('id')) for g in games]
    if not ids or any(x in ('None', '') for x in ids) or len(ids) != len(set(ids)):
        raise GateError('INVALID_SCHEDULE_IDS')
    for source in (draft, shadow):
        if (source.get('season'), source.get('week')) != (target.get('season'), target.get('week')):
            raise GateError('STALE_WEEK_INPUT')
        if timestamp(source.get('generatedAt')) > cutoff:
            raise GateError('POST_CUTOFF_INPUT')
        source_games = source.get('games', [])
        source_ids = [str(g.get('id')) for g in source_games]
        if len(source_ids) != len(ids) or len(set(source_ids)) != len(source_ids) or set(source_ids) != set(ids):
            raise GateError('GAME_ID_MISMATCH')
        by_id = {str(g['id']): g for g in source_games}
        for game in games:
            entry = by_id[str(game['id'])]
            if any(entry.get(k) != game.get(k) for k in ('home', 'away')) or timestamp(entry.get('date')) != timestamp(game.get('date')):
                raise GateError('GAME_METADATA_MISMATCH')
    if shadow.get('status') != 'EXPERIMENTAL_SHADOW_ONLY':
        raise GateError('INVALID_SHADOW_STATUS')
    return tuple(ids)
