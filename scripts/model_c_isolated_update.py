#!/usr/bin/env python3
"""Offline, append-only Model C QB updates. No production workflow entry point."""
import argparse
import copy
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import types
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
    source = ENGINE.read_bytes()
    require(hashlib.sha256(source).hexdigest() == bundle['engineSha256'],
            'Exact frozen engine bytes unavailable; cannot substitute a newer version')
    # Compile exactly the bytes hashed above, without importing/writing a .pyc file.
    engine = types.ModuleType('isolated_model_c')
    engine.__file__ = str(ENGINE)
    exec(compile(source, str(ENGINE), 'exec'), engine.__dict__)
    require(getattr(engine, 'ISOLATED_API_VERSION', None) == 1,
            'Frozen engine has no supported isolated API')
    return engine


def validate_bundle(bundle, now, replay=True):
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
    if replay:
        original = engine.predict_game(target, now=generated, **args)
        require(canonical(original) == canonical(game),
                'Original game cannot be reproduced exactly; no update may be published')
    return engine, target, args, frozen, kickoff


def validate_event(bundle, event, now, engine, target, args, frozen, kickoff):
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
    severity = {'STARTER': 0, 'AVAILABLE': 0, 'CLEARED': 0, 'QUESTIONABLE': 1, 'DOUBTFUL': 2, 'OUT': 3}
    if event['change'] == 'DOWNGRADED' and event['previousStatus'] in severity:
        require(severity[event['newStatus']] > severity[event['previousStatus']],
                'Reported downgrade does not worsen availability')
    require(bool(event['quarterback'].strip()), 'Quarterback identity required')
    side = 'home' if team == target['home'] else 'away'
    assumption = bundle['original']['quarterbacks'][side]
    identities = {assumption.get(k) for k in ('starter', 'recentPrimaryPasser', 'depthChartQB1Candidate')}
    effective = args['qb_declarations'].get(team, {})
    if effective.get('starter'):
        identities = {effective['starter']}
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
    # The engine has no calibrated QB-dependent numeric adjustment updater. An old
    # target-side adjustment cannot be assumed valid for a changed QB assumption.
    adjustment = args['adjustments'].get('games', {}).get(str(target['id']), {}).get(side)
    require(not adjustment, 'Existing target-side points require dependent-input reassessment')
    return team, declaration


def identity_keys(bundle, event):
    identity = {k: event.get(k) for k in ('gameId', 'team', 'quarterback', 'newStatus', 'replacement')}
    identity['gameId'] = str(identity['gameId'])
    baseline_key = digest({k: bundle[k] for k in ('modelVersion', 'engineSha256', 'inputsSha256',
                                                'frozenAt', 'modelCGeneratedAt', 'original')})
    return baseline_key, digest({'baseline': baseline_key, 'status': identity})


def prepare(bundle, event, now, previous_records=()):
    engine, target, args, frozen, kickoff = validate_bundle(bundle, now)
    changed = copy.deepcopy(args)
    baseline_key, status_key = identity_keys(bundle, event)
    previous_links = []
    for previous in sorted(previous_records, key=lambda row: stamp(row['sourceProvenance']['reportedAt'])):
        require(previous['baselineKey'] == baseline_key and previous['rating'] == 'NO BET',
                'Previous record baseline mismatch')
        require(stamp(previous['generatedAt']) <= now, 'Future-dated prior update')
        prior_event = previous['sourceProvenance']
        prior_team, prior_declaration = validate_event(
            bundle, prior_event, now, engine, target, changed, frozen, kickoff)
        changed['qb_declarations'][prior_team] = copy.deepcopy(prior_declaration)
        previous_links.append(previous['dedupKey'])
    team, declaration = validate_event(bundle, event, now, engine, target, changed, frozen, kickoff)
    changed['qb_declarations'][team] = copy.deepcopy(declaration)
    # No ad hoc/calibration-free QB point conversion is supported.
    # All other inputs, including documented adjustments, remain byte-equivalent.
    updated = engine.predict_game(target, now=now, **changed)
    require(updated['rating'] == 'NO BET', 'NO BET must be retained')
    reported = stamp(event['reportedAt'])
    key = digest({'status': status_key, 'reportedAt': reported.isoformat()})
    return {
        'schemaVersion': 1, 'label': 'UPDATED MODEL C', 'generatedAt': now.isoformat(),
        'dedupKey': key, 'statusKey': status_key, 'baselineKey': baseline_key,
        'baselineSha256': digest(bundle), 'originalLink': bundle['originalLink'],
        'inputsLink': bundle['inputsLink'], 'modelVersion': bundle['modelVersion'],
        'engineSha256': bundle['engineSha256'], 'season': bundle['season'], 'week': bundle['week'],
        'sourceProvenance': event, 'original': bundle['original'], 'updated': updated,
        'inputChanges': [{'path': 'qb_declarations/' + name,
                         'previous': args['qb_declarations'].get(name), 'new': value}
                        for name, value in sorted(changed['qb_declarations'].items())
                        if value != args['qb_declarations'].get(name)],
        'priorUpdateIds': previous_links,
        'otherInputChanges': [], 'evaluationTimeChangedFrom': bundle['modelCGeneratedAt'],
        'explanation': ('QB evidence is updated. This Model C version does not translate QB '
                        'status into points automatically. Original numeric adjustment inputs '
                        'were retained; an unchanged pick/margin is not evidence of no QB impact.'),
        'gradingImplemented': False, 'rating': 'NO BET',
    }


@contextmanager
def archive_lock(directory):
    directory = Path(directory).resolve()
    require(directory.name == 'model-c-isolated-updates' and directory.is_dir(),
            'Use an existing dedicated model-c-isolated-updates directory')
    require(not directory.is_relative_to(ROOT), 'Updates must be stored outside the repository')
    # Serialize dedup + publication; records become visible atomically, never replaced.
    fd = os.open(directory / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield directory


def _publish(directory, record, clock):
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
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        os.unlink(temporary)
    return dest


def process_update(directory, bundle, event, clock=utcnow):
    # Hold one lock through dedup, cumulative-input reconstruction and publication.
    # A duplicate never reaches either baseline replay or updated model evaluation.
    with archive_lock(directory) as archive:
        now = clock()
        validate_bundle(bundle, now, replay=False)
        baseline_key, status_key = identity_keys(bundle, event)
        previous_records = []
        for path in archive.glob('*.json'):
            require(not path.is_symlink(), 'Refusing symlink in update archive')
            previous = json.loads(path.read_text())
            if previous['baselineKey'] == baseline_key:
                previous_records.append(previous)
        team_records = [row for row in previous_records
                        if row['sourceProvenance']['team'] == event['team']]
        if team_records:
            def relevant(row):
                earlier = row['sourceProvenance']
                if event['change'] == 'REPLACED':
                    return earlier['change'] == 'REPLACED'
                return ((earlier['change'] != 'REPLACED' and
                         earlier['quarterback'] == event['quarterback']) or
                        (earlier['change'] == 'REPLACED' and
                         earlier.get('replacement') == event['quarterback']))
            status_records = [row for row in team_records if relevant(row)]
            if status_records:
                latest_status = max(status_records, key=lambda row: stamp(row['sourceProvenance']['reportedAt']))
                if latest_status['statusKey'] == status_key:
                    return None
            latest = max(team_records, key=lambda row: stamp(row['sourceProvenance']['reportedAt']))
            require(stamp(event['reportedAt']) > stamp(latest['sourceProvenance']['reportedAt']),
                    'Stale or conflicting status transition')
        record = prepare(bundle, event, now, previous_records)
        return _publish(archive, record, clock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--event', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.baseline.read_text())
        event = json.loads(args.event.read_text())
        path = process_update(args.output_dir, bundle, event)
        print(json.dumps({'status': 'UPDATED MODEL C' if path else 'DUPLICATE_SUPPRESSED',
                          'record': str(path) if path else None}))
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError, SyntaxError, ImportError) as exc:
        print(json.dumps({'label': 'NEEDS REASSESSMENT', 'status': 'UPDATE BLOCKED', 'reason': str(exc)}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
