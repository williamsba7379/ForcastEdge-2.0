#!/usr/bin/env python3
"""Prospective, review-only Model C capture; never edits production files."""
import argparse
import copy
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types

_bytecode_setting = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    from model_c_isolated_update import REPO, canonical, digest, require, stamp, utcnow
finally:
    sys.dont_write_bytecode = _bytecode_setting

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = 'scripts/model_c_engine.py'
FILES = {
    'nfl-schedule.json': None,
    'nfl-historical-results.json': [],
    'model-c-verified-adjustments.json': {'games': {}},
    'model-c-injury-snapshot.json': {},
    'model-c-qb-starters.json': {},
    'model-c-qb-performance.json': {},
    'model-c-qb-candidates.json': {},
    'model-c-qb-depthcharts.json': {},
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def flush_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def rename_new_directory(source, destination):
    """Linux atomic no-replace publication, including existing empty directories."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    require(rename is not None, 'Atomic no-replace directory publication is unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def git_bytes(repository, version, path):
    require(isinstance(version, str) and re.fullmatch(r'[0-9a-f]{40}', version),
            'Exact Git commit SHA required')
    require(path and not path.startswith('/') and all(p not in ('', '.', '..') for p in path.split('/')),
            'Safe relative Git path required')
    return subprocess.run(['git', '-C', str(repository), 'show', version + ':' + path],
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def source_link(link):
    require(isinstance(link, str) and link.startswith(REPO), 'Pinned ForecastEdge blob link required')
    value = link[len(REPO):]
    version, separator, path = value.partition('/')
    require(separator and re.fullmatch(r'[0-9a-f]{40}', version), 'Pinned commit link required')
    require(not any(c in path for c in ('?', '#', '%', '\\')), 'Canonical blob path required')
    return version, path


def engine_from_source(source, filename):
    engine = types.ModuleType('captured_model_c')
    engine.__file__ = str(filename)
    exec(compile(source, str(filename), 'exec'), engine.__dict__)
    require(getattr(engine, 'ISOLATED_API_VERSION', None) == 1,
            'Engine cannot capture a compatible isolated baseline')
    return engine


def no_future_asof(value, generated):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'asOf' and item is not None:
                require(stamp(item) <= generated, 'Future-dated input cannot be captured')
            else:
                no_future_asof(item, generated)
    elif isinstance(value, list):
        for item in value:
            no_future_asof(item, generated)


def normalize(raw, engine, generated):
    values = {name: json.loads(raw[name]) if raw[name] is not None else copy.deepcopy(default)
              for name, default in FILES.items()}
    schedule = values['nfl-schedule.json']
    require(schedule is not None, 'Schedule is required')
    selected = engine.choose_week(schedule, generated)
    engine.validate_original_slate(selected)
    require(all(stamp(game['date']) > generated for game in selected['games']),
            'Prospective capture cannot include a started game')
    inputs = dict(
        selected=selected, year=schedule['season'],
        history_raw=values['nfl-historical-results.json'],
        adjustments=values['model-c-verified-adjustments.json'],
        injury_snapshot=values['model-c-injury-snapshot.json'],
        qb_declarations=values['model-c-qb-starters.json'].get('teams', {}),
        qb_stats=values['model-c-qb-performance.json'],
        qb_candidates=values['model-c-qb-candidates.json'].get('teams', {}),
        depthchart_candidates=values['model-c-qb-depthcharts.json'].get('teams', {}))
    no_future_asof(inputs, generated)
    last_kickoff = max(stamp(game['date']) for game in selected['games'])
    require(engine.extract_history(inputs['history_raw'], generated, inputs['year']) ==
            engine.extract_history(inputs['history_raw'], last_kickoff, inputs['year']),
            'History contains future results that could activate later')
    return inputs


def prospective_capture(repository, version, data_dir, clock=utcnow):
    """Read once for calculation; verify sources did not change during generation."""
    repository, data_dir = Path(repository).resolve(), Path(data_dir).resolve()
    source = git_bytes(repository, version, ENGINE_PATH)
    require((repository / ENGINE_PATH).read_bytes() == source,
            'Installed engine differs from the pinned Git version')
    engine = engine_from_source(source, repository / ENGINE_PATH)
    generated = clock()
    raw = {}
    for name in FILES:
        path = data_dir / name
        require(not path.is_symlink(), 'Input symlinks are not supported')
        try:
            raw[name] = path.read_bytes()
        except FileNotFoundError:
            require(FILES[name] is not None, 'Missing required input: ' + name)
            raw[name] = None
    inputs = normalize(raw, engine, generated)
    args = {key: value for key, value in inputs.items() if key != 'selected'}
    games = [engine.predict_game(game, now=generated, **args) for game in inputs['selected']['games']]
    require(all(game['rating'] == 'NO BET' for game in games), 'NO BET must be retained')
    finished = clock()
    require(generated <= finished and all(finished < stamp(game['date']) for game in games),
            'Kickoff reached during prospective capture')
    for name, original in raw.items():
        path = data_dir / name
        require(not path.is_symlink(), 'Input changed to a symlink during capture')
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            current = None
        require(current == original, 'Source changed during capture: ' + name)
    require((repository / ENGINE_PATH).read_bytes() == source, 'Engine changed during capture')
    generation = dict(status='AUTOMATED_REVIEW_ONLY', reviewRequired=True, rating='NO BET',
                      season=inputs['year'], week=inputs['selected']['week'],
                      generatedAt=generated.isoformat(), games=games)
    artifacts = {'engine.py': source, 'inputs.json': (canonical(inputs) + '\n').encode(),
                 'generation.json': (canonical(generation) + '\n').encode()}
    inventory = {}
    for name, original in raw.items():
        inventory[name] = {'present': original is not None,
                           'sha256': sha256(original) if original is not None else None}
        if original is not None:
            artifacts['raw/' + name] = original
    manifest = dict(schemaVersion=1, status='UNREVIEWED_PROSPECTIVE_CAPTURE', reviewed=False,
                    modelVersion=version, engineLink=REPO + version + '/' + ENGINE_PATH,
                    engineSha256=sha256(source), inputsSha256=digest(inputs),
                    generatedAt=generated.isoformat(), capturedAt=finished.isoformat(),
                    sourceInventory=inventory,
                    artifactHashes={name: sha256(value) for name, value in artifacts.items()})
    manifest['captureId'] = digest(manifest)
    artifacts['manifest.json'] = (canonical(manifest) + '\n').encode()
    return artifacts


def publish_capture(output_root, artifacts, clock=utcnow):
    """One complete new directory, atomically published; no replace operation."""
    root = Path(output_root).resolve()
    require(root.name == 'model-c-frozen-captures' and root.is_dir() and not root.is_relative_to(ROOT),
            'Use an existing external model-c-frozen-captures directory')
    manifest = json.loads(artifacts['manifest.json'])
    require(re.fullmatch(r'[0-9a-f]{64}', manifest['captureId']) is not None, 'Invalid capture ID')
    allowed = {'engine.py', 'inputs.json', 'generation.json', 'manifest.json'} | {'raw/' + name for name in FILES}
    require(set(artifacts) <= allowed, 'Unexpected capture artifact path')
    generation = json.loads(artifacts['generation.json'])
    require(clock() < min(stamp(game['date']) for game in generation['games']),
            'Kickoff reached before capture publication')
    destination = root / manifest['captureId']
    temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=root))
    try:
        for name, raw in artifacts.items():
            path = temporary / name
            path.parent.mkdir(exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        validate_capture(temporary)
        if (temporary / 'raw').exists():
            flush_directory(temporary / 'raw')
        flush_directory(temporary)
        require(clock() < min(stamp(game['date']) for game in generation['games']),
                'Kickoff reached before capture publication')
        rename_new_directory(temporary, destination)
        flush_directory(root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def validate_capture(capture_dir):
    directory = Path(capture_dir)
    require(not directory.is_symlink(), 'Capture directory must not be a symlink')
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    unsigned = {k: v for k, v in manifest.items() if k != 'captureId'}
    require(manifest['captureId'] == digest(unsigned), 'Capture manifest hash mismatch')
    require(manifest['schemaVersion'] == 1 and manifest['reviewed'] is False and
            manifest['status'] == 'UNREVIEWED_PROSPECTIVE_CAPTURE', 'Unrecognized capture')
    expected_files = {'engine.py', 'inputs.json', 'generation.json'}
    require(set(manifest['sourceInventory']) == set(FILES), 'Missing raw source inventory')
    for name, item in manifest['sourceInventory'].items():
        if item['present'] is True:
            expected_files.add('raw/' + name)
        else:
            require(item['present'] is False and item['sha256'] is None and FILES[name] is not None,
                    'Invalid missing-source declaration')
    require(set(manifest['artifactHashes']) == expected_files, 'Incomplete capture artifacts')
    found = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    require(found == expected_files | {'manifest.json'}, 'Unexpected or missing capture files')
    artifacts = {}
    for name in expected_files | {'manifest.json'}:
        path = directory / name
        require(not path.is_symlink() and not path.parent.is_symlink(), 'Capture symlink refused')
        artifacts[name] = path.read_bytes()
        if name != 'manifest.json':
            require(sha256(artifacts[name]) == manifest['artifactHashes'][name], 'Artifact hash mismatch: ' + name)
    require(sha256(artifacts['engine.py']) == manifest['engineSha256'], 'Engine hash mismatch')
    inputs, generation = json.loads(artifacts['inputs.json']), json.loads(artifacts['generation.json'])
    require(digest(inputs) == manifest['inputsSha256'], 'Normalized input hash mismatch')
    for name, item in manifest['sourceInventory'].items():
        if item['present']:
            require(sha256(artifacts['raw/' + name]) == item['sha256'], 'Raw source hash mismatch')
    return manifest, inputs, generation, artifacts


def reviewed_bundle(repository, capture_dir, archive_commit, archive_path, freeze_link, game_id,
                    reviewed, clock=utcnow):
    """Bind captured generation to an existing authentic, prekickoff freeze."""
    require(reviewed is True, 'Explicit provenance review is required')
    manifest, inputs, generation, artifacts = validate_capture(capture_dir)
    version = manifest['modelVersion']
    require(git_bytes(repository, version, ENGINE_PATH) == artifacts['engine.py'],
            'Captured engine does not match the pinned Git commit')
    require(manifest['engineLink'] == REPO + version + '/' + ENGINE_PATH, 'Wrong model source link')
    # Verify every archived byte actually exists at its claimed immutable Git URL.
    for name, raw in artifacts.items():
        require(git_bytes(repository, archive_commit, archive_path + '/' + name) == raw,
                'Immutable archive differs from local capture: ' + name)
    freeze_commit, freeze_path = source_link(freeze_link)
    frozen = json.loads(git_bytes(repository, freeze_commit, freeze_path))
    require(frozen['status'] in ('FROZEN_PREKICKOFF', 'FRESH_PREKICKOFF_SNAPSHOT'),
            'Prediction is not an original prekickoff freeze')
    generated, frozen_at, now = stamp(generation['generatedAt']), stamp(frozen['frozenAt']), clock()
    require(stamp(manifest['generatedAt']) == generated and
            generated <= stamp(manifest['capturedAt']) <= frozen_at <= now,
            'Capture must precede the original freeze; historical reconstruction is forbidden')
    require(stamp(frozen['modelCGeneratedAt']) == generated, 'Freeze refers to a different generation')
    require((frozen['season'], frozen['week']) == (generation['season'], generation['week']) ==
            (inputs['year'], inputs['selected']['week']), 'Freeze season/week mismatch')
    engine = engine_from_source(artifacts['engine.py'], Path(repository) / ENGINE_PATH)
    raw = {name: artifacts.get('raw/' + name) for name in FILES}
    require(canonical(normalize(raw, engine, generated)) == canonical(inputs),
            'Normalized inputs do not match the captured source bytes')
    require(generation['status'] == 'AUTOMATED_REVIEW_ONLY' and generation['rating'] == 'NO BET',
            'Wrong generation type')
    selected = {str(game['id']): game for game in inputs['selected']['games']}
    originals = {str(game['id']): game for game in generation['games']}
    require(len(originals) == len(generation['games']), 'Duplicate captured game ID')
    require(originals.keys() == selected.keys(), 'Generation differs from captured schedule')
    rows = {str(game['id']): game for game in frozen['games']}
    require(len(rows) == len(frozen['games']) and rows.keys() == originals.keys(), 'Freeze slate mismatch')
    for key, game in originals.items():
        row = rows[key]
        require(all(game[k] == selected[key][k] for k in ('date', 'away', 'home')),
                'Generation matchup differs from captured inputs')
        require(all(row[k] == game[k] for k in ('date', 'away', 'home')) and row['picks']['C'] == game['pick'],
                'Frozen Model C differs from captured original: ' + key)
        require(frozen_at < stamp(game['date']) and game['rating'] == 'NO BET', 'Freeze was not prekickoff/NO BET')
    require(str(game_id) in originals, 'Requested game is not in the freeze')
    original = originals[str(game_id)]
    require(now < stamp(original['date']), 'Requested game has already started')
    args = {key: value for key, value in inputs.items() if key != 'selected'}
    replay = engine.predict_game(selected[str(game_id)], now=generated, **args)
    require(canonical(replay) == canonical(original), 'Captured original game cannot be reproduced exactly')
    base = REPO + archive_commit + '/' + archive_path
    return dict(schemaVersion=1, reviewed=True, season=frozen['season'], week=frozen['week'],
                modelVersion=version, engineLink=manifest['engineLink'], engineSha256=manifest['engineSha256'],
                originalLink=freeze_link, inputsLink=base + '/inputs.json',
                generationLink=base + '/generation.json', captureLink=base + '/manifest.json',
                capturedAt=manifest['capturedAt'], captureId=manifest['captureId'],
                frozenAt=frozen['frozenAt'], modelCGeneratedAt=generation['generatedAt'],
                inputsSha256=manifest['inputsSha256'], inputs=inputs, original=original)


def publish_bundle(output_dir, bundle, clock=utcnow):
    directory = Path(output_dir).resolve()
    require(directory.name == 'model-c-baseline-bundles' and directory.is_dir() and
            not directory.is_relative_to(ROOT), 'Use an existing external model-c-baseline-bundles directory')
    require(clock() < stamp(bundle['original']['date']), 'Kickoff reached before bundle publication')
    destination = directory / (digest(bundle) + '.json')
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(canonical(bundle) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        require(clock() < stamp(bundle['original']['date']), 'Kickoff reached before bundle publication')
        os.link(temporary, destination)
        flush_directory(directory)
    finally:
        os.unlink(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--repository', type=Path, required=True)
    capture.add_argument('--model-version', required=True)
    capture.add_argument('--data-dir', type=Path, required=True)
    capture.add_argument('--output-root', type=Path, required=True)
    bundle = commands.add_parser('bundle')
    bundle.add_argument('--repository', type=Path, required=True)
    bundle.add_argument('--capture-dir', type=Path, required=True)
    bundle.add_argument('--archive-commit', required=True)
    bundle.add_argument('--archive-path', required=True)
    bundle.add_argument('--freeze-link', required=True)
    bundle.add_argument('--game-id', required=True)
    bundle.add_argument('--reviewed', action='store_true')
    bundle.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'capture':
            artifacts = prospective_capture(args.repository, args.model_version, args.data_dir)
            path = publish_capture(args.output_root, artifacts)
            status = 'UNREVIEWED_PROSPECTIVE_CAPTURE'
        else:
            record = reviewed_bundle(args.repository, args.capture_dir, args.archive_commit,
                                     args.archive_path, args.freeze_link, args.game_id, args.reviewed)
            path = publish_bundle(args.output_dir, record)
            status = 'REVIEWED_BASELINE_BUNDLE'
        print(json.dumps({'status': status, 'record': str(path), 'rating': 'NO BET'}))
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError,
            SyntaxError, ImportError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'status': 'CAPTURE BLOCKED', 'reason': str(exc)}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
