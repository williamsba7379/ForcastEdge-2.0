#!/usr/bin/env python3
"""Offline, append-only Model C QB updates. No production workflow entry point."""
import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(__file__).with_name('model_c_engine.py')
REPO = 'https://github.com/williamsba7379/ForcastEdge-2.0/blob/'
OFFICIAL = set('nfl.com azcardinals.com atlantafalcons.com baltimoreravens.com buffalobills.com panthers.com chicagobears.com bengals.com clevelandbrowns.com dallascowboys.com denverbroncos.com detroitlions.com packers.com houstontexans.com colts.com jaguars.com chiefs.com raiders.com chargers.com therams.com miamidolphins.com vikings.com patriots.com neworleanssaints.com giants.com newyorkjets.com philadelphiaeagles.com steelers.com 49ers.com seahawks.com buccaneers.com tennesseetitans.com commanders.com'.split())
INPUT_KEYS = {'selected', 'year', 'history_raw', 'adjustments', 'injury_snapshot',
              'qb_declarations', 'qb_stats', 'qb_candidates', 'depthchart_candidates'}


class Blocked(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Blocked(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timezone required')
    return parsed.astimezone(dt.timezone.utc)


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def pinned_link(value):
    return isinstance(value, str) and re.fullmatch(
        re.escape(REPO) + r'[0-9a-f]{40}/[^?#\s]+', value) is not None


def official_link(value):
    parsed = urlparse(value)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and any(host == domain or host.endswith('.' + domain) for domain in OFFICIAL))


def load_engine(bundle):
    version = bundle['modelVersion']
    require(re.fullmatch(r'[0-9a-f]{40}', version) is not None, 'Pinned model commit required')
    require(bundle['engineLink'] == REPO + version + '/scripts/model_c_engine.py',
            'Engine link must identify the exact model commit')
    require(hashlib.sha256(ENGINE.read_bytes()).hexdigest() == bundle['engineSha256'],
            'Exact frozen engine bytes unavailable; cannot substitute a newer version')
    spec = importlib.util.spec_from_file_location('isolated_model_c', ENGINE)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    require(getattr(engine, 'ISOLATED_API_VERSION', None) == 1,
            'Frozen engine has no supported isolated API')
    return engine


def validate_bundle(bundle, now):
    require(bundle['schemaVersion'] == 1, 'Unsupported baseline bundle')
    require(bundle['reviewed'] is True, 'Baseline provenance requires review')
    require(pinned_link(bundle['originalLink']), 'Immutable original link required')
    require(pinned_link(bundle['inputsLink']), 'Immutable archived-input link required')
    inputs = bundle['inputs']
    require(set(inputs) == INPUT_KEYS, 'Complete original input set required')
    require(digest(inputs) == bundle['inputsSha256'], 'Original input hash mismatch')
    frozen = stamp(bundle['frozenAt'])
    generated = stamp(bundle['modelCGeneratedAt'])
    game = bundle['original']
    kickoff = stamp(game['date'])
    require(generated <= frozen < now < kickoff, 'Original and update must precede kickoff')
    require(game.get('rating') == 'NO BET', 'Original NO BET required')
    rows = inputs['selected']['games']
    matches = [g for g in rows if str(g['id']) == str(game['id'])]
    require(len(matches) == 1, 'Exact game must occur once in original full slate')
    target = matches[0]
    require(all(target[k] == game[k] for k in ('date', 'home', 'away')), 'Matchup mismatch')
    require(inputs['year'] == bundle['season'] and inputs['selected']['week'] == bundle['week'],
            'Season/week mismatch')
    engine = load_engine(bundle)
    engine.validate_original_slate(inputs['selected'])
    args = {k: v for k, v in inputs.items() if k not in ('selected',)}
    require(engine.extract_history(args['history_raw'], generated, inputs['year']) ==
            engine.extract_history(args['history_raw'], now, inputs['year']),
            'Archived history would change its effective cutoff at update time')
    def check_asof(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'asOf' and item is not None:
                    require(stamp(item) <= generated, 'Future-dated original QB inputs')
                else:
                    check_asof(item)
        elif isinstance(value, list):
            for item in value:
                check_asof(item)
    check_asof(args)
    # Replay ONLY the affected game at its original generation time.
    replay = engine.predict_game(target, now=generated, **args)
    require(canonical(replay) == canonical(game),
            'Original game cannot be reproduced exactly; no update may be published')
    return engine, target, args, frozen, kickoff


def prepare(bundle, event, now):
    engine, target, args, frozen, kickoff = validate_bundle(bundle, now)
    team = event['team']
    require(str(event['gameId']) == str(target['id']) and team in (target['away'], target['home']),
            'QB evidence must identify this exact game and team')
    require(event['reviewed'] is True and event['officiallyConfirmed'] is True,
            'Verified official status decision required')
    require(event['change'] in ('RULED_OUT', 'DOWNGRADED', 'CLEARED', 'REPLACED'),
            'Not a qualifying QB status change')
    allowed_status = {'RULED_OUT': ('OUT',), 'DOWNGRADED': ('QUESTIONABLE', 'DOUBTFUL', 'OUT'),
                      'CLEARED': ('CLEARED',), 'REPLACED': ('REPLACED',)}
    require(event['newStatus'] in allowed_status[event['change']], 'Noncanonical status')
    require(event['evidenceKind'] in ('GAME_STATUS', 'INACTIVE_LIST', 'STARTER_ANNOUNCEMENT'),
            'Practice participation and expectations do not establish game status')
    require(official_link(event['source']) and len(event['evidenceText'].strip()) >= 15,
            'Official evidence URL and reviewed text required')
    reported = stamp(event['reportedAt'])
    require(frozen < reported <= now < kickoff, 'Evidence must be new and prekickoff')
    require(event['previousStatus'] != event['newStatus'], 'No meaningful status transition')
    require(bool(event['quarterback'].strip()), 'Quarterback identity required')
    side = 'home' if team == target['home'] else 'away'
    assumption = bundle['original']['quarterbacks'][side]
    identities = {assumption.get(k) for k in ('starter', 'recentPrimaryPasser', 'depthChartQB1Candidate')}
    require(event['quarterback'] in identities, 'QB does not match the archived baseline assumption')
    declaration = event['declaration']
    require(declaration['team'] == team and str(declaration['gameId']) == str(target['id']),
            'Declaration game/team mismatch')
    require(declaration['source'] == event['source'] and stamp(declaration['asOf']) == reported,
            'Declaration must use the verified report')
    require(declaration['evidenceText'] == event['evidenceText'] and declaration['reviewed'] is True,
            'Declaration provenance mismatch')
    if event['change'] in ('CLEARED', 'REPLACED'):
        require(engine.official_starter_valid(declaration, target, team, now),
                'Cleared/replacement starter needs official game-specific team confirmation')
        expected = event['quarterback'] if event['change'] == 'CLEARED' else event['replacement']
        require(declaration['starter'] == expected, 'Confirmed starter mismatch')
    else:
        require(declaration['status'] == 'CONFIRMED_' + event['change']
                and declaration['starter'] == event['quarterback'],
                'Unavailable/uncertain declaration must not promote a replacement')
        require(not event.get('replacement'), 'Replacement needs a separate confirmed starter event')
    changed = copy.deepcopy(args)
    changed['qb_declarations'][team] = copy.deepcopy(declaration)
    # No ad hoc/calibration-free QB point conversion is supported.
    # All other inputs, including documented adjustments, remain byte-equivalent.
    updated = engine.predict_game(target, now=now, **changed)
    require(updated['rating'] == 'NO BET', 'NO BET must be retained')
    identity = {k: event.get(k) for k in ('gameId', 'team', 'quarterback', 'newStatus', 'replacement')}
    identity['gameId'] = str(identity['gameId'])
    baseline_key = digest({k: bundle[k] for k in ('modelVersion', 'engineSha256', 'inputsSha256',
                                                'frozenAt', 'modelCGeneratedAt', 'original')})
    status_key = digest({'baseline': baseline_key, 'status': identity})
    key = digest({'status': status_key, 'reportedAt': reported.isoformat()})
    return {
        'schemaVersion': 1, 'label': 'UPDATED MODEL C', 'generatedAt': now.isoformat(),
        'dedupKey': key, 'statusKey': status_key, 'baselineKey': baseline_key,
        'baselineSha256': digest(bundle), 'originalLink': bundle['originalLink'],
        'inputsLink': bundle['inputsLink'], 'modelVersion': bundle['modelVersion'],
        'engineSha256': bundle['engineSha256'], 'season': bundle['season'], 'week': bundle['week'],
        'sourceProvenance': event, 'original': bundle['original'], 'updated': updated,
        'inputChanges': [{'path': 'qb_declarations/' + team,
                         'previous': args['qb_declarations'].get(team), 'new': declaration}],
        'otherInputChanges': [], 'evaluationTimeChangedFrom': bundle['modelCGeneratedAt'],
        'explanation': ('QB evidence is updated. This Model C version does not translate QB '
                        'status into points automatically. Original numeric adjustment inputs '
                        'were retained; an unchanged pick/margin is not evidence of no QB impact.'),
        'gradingImplemented': False, 'rating': 'NO BET',
    }


def append_record(directory, record, clock=utcnow):
    directory = Path(directory).resolve()
    require(directory.name == 'model-c-isolated-updates' and directory.is_dir(),
            'Use an existing dedicated model-c-isolated-updates directory')
    require(not directory.is_relative_to(ROOT), 'Updates must be stored outside the repository')
    # Serialize dedup + publication; records become visible atomically, never replaced.
    fd = os.open(directory / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prior = []
        for path in directory.glob('*.json'):
            require(not path.is_symlink(), 'Refusing symlink in update archive')
            previous = json.loads(path.read_text())
            if (previous['baselineKey'] == record['baselineKey'] and
                    previous['sourceProvenance']['team'] == record['sourceProvenance']['team']):
                prior.append(previous)
        if prior:
            latest = max(prior, key=lambda row: stamp(row['sourceProvenance']['reportedAt']))
            if latest['statusKey'] == record['statusKey']:
                return None
            require(stamp(record['sourceProvenance']['reportedAt']) >
                    stamp(latest['sourceProvenance']['reportedAt']), 'Stale or conflicting status transition')
        kickoff = stamp(record['updated']['date'])
        now = clock()
        require(stamp(record['generatedAt']) <= now < kickoff, 'Kickoff reached before publication')
        filename = now.strftime('%Y%m%dT%H%M%S%fZ') + '-' + record['dedupKey'] + '.json'
        dest = directory / filename
        temp_fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=directory)
        try:
            with os.fdopen(temp_fd, 'w') as output:
                output.write(json.dumps(record, indent=2, allow_nan=False) + '\n')
                output.flush()
                os.fsync(output.fileno())
            require(clock() < kickoff, 'Kickoff reached before publication')
            os.link(temporary, dest)  # Fails if the destination exists; no overwrite.
        finally:
            os.unlink(temporary)
        return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--event', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.baseline.read_text())
        event = json.loads(args.event.read_text())
        record = prepare(bundle, event, utcnow())
        path = append_record(args.output_dir, record)
        print(json.dumps({'status': 'UPDATED MODEL C' if path else 'DUPLICATE_SUPPRESSED',
                          'record': str(path) if path else None}))
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError) as exc:
        print(json.dumps({'label': 'NEEDS REASSESSMENT', 'status': 'UPDATE BLOCKED', 'reason': str(exc)}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
