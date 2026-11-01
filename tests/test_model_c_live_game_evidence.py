"""Offline integration cases for the live read-only evidence adapter."""
import datetime as dt
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from model_c_live_game_evidence import diagnose, SCOREBOARD

NOW = dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)
competition = dict(date='2026-11-01T18:00:00Z', status={'type': {'state': 'pre'}},
                   competitors=[{'team': {'abbreviation': t}} for t in ('BAL', 'BUF')])
event = dict(id='fixture-game-id', competitions=[competition])
html = '<p>Oct 30, 2026 at 01:56 PM</p><p>Lamar Jackson. Head Coach Jesse Minter announced Friday that Jackson will play against the Buffalo Bills</p>'
def run(events=None, article=html, now=NOW):
    def get(url):
        return json.dumps({'events': [event] if events is None else events}) if url == SCOREBOARD else article
    r = diagnose(get, now)
    assert all(r[k] is False for k in ('starterConfirmed', 'productionEligible', 'depthChartFreshnessAffected'))
    if 'validation' in r:
        assert all(r['validation'][k] is False for k in ('starterConfirmed', 'productionEligible', 'depthChartFreshnessAffected'))
    return r
assert run()['validation']['status'] == 'READ_ONLY_MATCHED_EVIDENCE'
assert run([])['status'] == 'UNVERIFIED'
assert run([event, event])['status'] == 'UNVERIFIED'
assert run([dict(event, competitions=[dict(competition, date='2026-11-02T18:00:00Z')])])['status'] == 'UNVERIFIED'
assert run(article=html.replace('Oct 30', 'Oct 20'))['status'] == 'UNVERIFIED_ANNOUNCEMENT'
assert run(article=html.replace('Oct 30', 'Oct 31'), now=dt.datetime(2026, 10, 31, 12, tzinfo=dt.timezone.utc))['status'] == 'PUBLICATION_TIME_NOT_VERIFIED'
assert run(article=html.replace('Lamar Jackson.', 'Other Player.'))['status'] == 'UNVERIFIED_ANNOUNCEMENT'
assert run(now=dt.datetime(2026, 11, 1, 18, tzinfo=dt.timezone.utc))['status'] == 'NOT_PREGAME_NO_LIVE_VALIDATION'
assert run(article='<p>Oct 30, 2026 at 01:56 PM Lamar Jackson Buffalo Bills</p>')['validation']['status'] == 'NO_DIRECT_QB_ANNOUNCEMENT'
def broken(url):
    raise OSError('offline')
assert diagnose(broken, NOW)['status'] == 'UNVERIFIED'
print('PASS: live adapter schedule, publication, identity, pregame and fail-closed integration')
