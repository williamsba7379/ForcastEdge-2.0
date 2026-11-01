#!/usr/bin/env python3
"""Read-only BAL/BUF evidence experiment. Writes only to stdout, never confirms starters."""
import datetime as dt
import hashlib
import json
import urllib.request
from model_c_official_qb_announcements import SOURCES, classify
from model_c_qb_game_evidence import validate

GAME_DATE = '2026-11-01'
SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261101'
BASE = dict(starterConfirmed=False, productionEligible=False, depthChartFreshnessAffected=False)

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'ForecastEdge-QB-Validation/1.0'})
    with urllib.request.urlopen(request, timeout=18) as response:
        if response.geturl() != url:
            raise ValueError('Unexpected redirect')
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        return raw.decode('utf-8', errors='strict')

def diagnose(get=fetch, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    result = {**BASE, 'status': 'UNVERIFIED', 'retrievedAt': now.isoformat(),
              'scheduleSource': SCOREBOARD, 'scope': 'BAL vs BUF only; availability is not starter confirmation'}
    try:
        schedule = get(SCOREBOARD)
        matches = []
        for event in json.loads(schedule).get('events', []):
            for competition in event.get('competitions', []):
                teams = [c['team']['abbreviation'] for c in competition.get('competitors', [])]
                if len(teams) == 2 and set(teams) == {'BAL', 'BUF'}:
                    matches.append((event, competition))
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous BAL/BUF game')
        event, competition = matches[0]
        kickoff = dt.datetime.fromisoformat(competition['date'].replace('Z', '+00:00'))
        if kickoff.tzinfo is None or kickoff.date().isoformat() != GAME_DATE:
            raise ValueError('Game date mismatch')
        game = dict(gameId=str(event['id']), team='BAL', opponent='BUF',
                    quarterback='Lamar Jackson', gameDate=GAME_DATE)
        result.update(game=game, kickoff=kickoff.isoformat())
        if now >= kickoff or competition.get('status', event.get('status', {})).get('type', {}).get('state') != 'pre':
            return {**result, 'status': 'NOT_PREGAME_NO_LIVE_VALIDATION'}
        url, _, _ = SOURCES['BAL']
        html = get(url)
        classification = classify('BAL', html, game_date=GAME_DATE)
        result.update(sourceUrl=url, sourceSha256=hashlib.sha256(html.encode()).hexdigest(),
                      announcement=classification)
        if classification.get('status') != 'DATED_OFFICIAL_REPORT':
            return {**result, 'status': 'UNVERIFIED_ANNOUNCEMENT'}
        published = dt.datetime.strptime(classification['articleDate'], '%b %d, %Y').date()
        # A day-only publication date cannot prove same-day pre-retrieval publication time.
        if published >= now.date():
            return {**result, 'status': 'PUBLICATION_TIME_NOT_VERIFIED'}
        report = dict(game, publicationDate=published.isoformat(), sourceType='OFFICIAL_TEAM',
                      sourceUrl=url, evidence='AVAILABLE' if classification['evidence'] ==
                      'COACH_ANNOUNCED_AVAILABLE_FOR_MATCHUP' else 'NO_DIRECT_ANNOUNCEMENT')
        return {**result, 'status': 'READ_ONLY_LIVE_GAME_EVIDENCE', 'report': report,
                'validation': validate(game, [report])}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {**result, 'status': 'UNVERIFIED', 'reason': type(exc).__name__}

if __name__ == '__main__':
    print(json.dumps(diagnose(), indent=2))
