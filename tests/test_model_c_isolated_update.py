"""Synthetic fixtures only: no real prediction/update records or network calls."""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import model_c_engine as engine
import model_c_isolated_update as runner

GENERATED = dt.datetime(2030, 11, 4, 12, tzinfo=dt.timezone.utc)
NOW = GENERATED + dt.timedelta(days=1)
KICKOFF = GENERATED + dt.timedelta(days=4)
PIN = 'a' * 40


def fixture():
    games = [{'id': str(i), 'date': KICKOFF.isoformat(), 'away': 'Away', 'home': 'Home'}
             for i in range(10)]
    history = [{'season': 2030, 'date': '2030-11-01T00:00:00Z', 'away': 'Away', 'home': 'Home',
                'scoreAway': 20, 'scoreHome': 24}]
    inputs = dict(selected={'week': 10, 'games': games}, year=2030, history_raw=history,
                  adjustments={'games': {}}, injury_snapshot={}, qb_declarations={}, qb_stats={},
                  qb_candidates={'Away': {'candidate': 'Old QB'}}, depthchart_candidates={})
    args = {k: v for k, v in inputs.items() if k != 'selected'}
    original = engine.predict_game(games[0], now=GENERATED, **args)
    bundle = dict(schemaVersion=1, reviewed=True, season=2030, week=10,
                  modelVersion=PIN, engineLink=runner.REPO + PIN + '/scripts/model_c_engine.py',
                  engineSha256=hashlib.sha256(runner.ENGINE.read_bytes()).hexdigest(),
                  originalLink=runner.REPO + PIN + '/data/frozen.json',
                  inputsLink=runner.REPO + PIN + '/data/archived-inputs.json',
                  frozenAt=(GENERATED + dt.timedelta(minutes=1)).isoformat(),
                  modelCGeneratedAt=GENERATED.isoformat(), inputs=inputs,
                  inputsSha256=runner.digest(inputs), original=original)
    event = dict(gameId='0', team='Away', quarterback='Old QB', replacement='New QB',
                 previousStatus='STARTER', newStatus='REPLACED', change='REPLACED',
                 reviewed=True, officiallyConfirmed=True, evidenceKind='STARTER_ANNOUNCEMENT',
                 source='https://www.nfl.com/news/synthetic-fixture',
                 evidenceText='Synthetic team announcement: New QB starts this game.',
                 reportedAt=(NOW - dt.timedelta(hours=1)).isoformat())
    event['declaration'] = dict(team='Away', gameId='0', starter='New QB',
                                status='CONFIRMED_STARTER', sourceType='TEAM_ANNOUNCEMENT',
                                reviewed=True, source=event['source'], asOf=event['reportedAt'],
                                evidenceText=event['evidenceText'])
    return bundle, event


class IsolatedUpdates(unittest.TestCase):
    def test_only_target_replays_and_non_qb_inputs_remain_unchanged(self):
        bundle, event = fixture()
        before = copy.deepcopy(bundle)
        with patch.object(runner, 'load_engine', return_value=engine), \
             patch.object(engine, 'predict_game', wraps=engine.predict_game) as predict:
            record = runner.prepare(bundle, event, NOW)
        self.assertEqual([c.args[0]['id'] for c in predict.call_args_list], ['0', '0'])
        self.assertEqual(bundle, before)
        self.assertEqual(record['original']['pick'], record['updated']['pick'])
        self.assertEqual(record['original']['homeEdgePoints'], record['updated']['homeEdgePoints'])
        self.assertEqual(record['updated']['quarterbacks']['away']['starter'], 'New QB')
        self.assertEqual(record['otherInputChanges'], [])
        self.assertFalse(record['gradingImplemented'])
        self.assertEqual(record['rating'], 'NO BET')

    def test_real_engine_hash_and_api_checked(self):
        bundle, event = fixture()
        self.assertEqual(runner.prepare(bundle, event, NOW)['label'], 'UPDATED MODEL C')
        bundle['engineSha256'] = '0' * 64
        with self.assertRaisesRegex(runner.Blocked, 'engine bytes'):
            runner.prepare(bundle, event, NOW)

    def test_fail_closed_matrix(self):
        mutations = {
            'missing input': lambda b, e: b['inputs'].pop('history_raw'),
            'wrong baseline': lambda b, e: b['original'].update(pick='Away'),
            'wrong team': lambda b, e: e.update(team='Other'),
            'wrong quarterback': lambda b, e: e.update(quarterback='Other QB'),
            'practice': lambda b, e: e.update(evidenceKind='PRACTICE'),
            'expectation': lambda b, e: e.update(officiallyConfirmed=False),
            'bad domain': lambda b, e: e.update(source='https://nfl.com.example.org/article'),
            'stale': lambda b, e: e.update(reportedAt=GENERATED.isoformat()),
            'future': lambda b, e: e.update(reportedAt=KICKOFF.isoformat()),
            'unchanged': lambda b, e: e.update(previousStatus=e['newStatus']),
            'short slate': lambda b, e: b['inputs']['selected'].update(games=b['inputs']['selected']['games'][:1]),
            'duplicate games': lambda b, e: b['inputs']['selected']['games'][1].update(id='0'),
            'injected inputs': lambda b, e: b['inputs'].update(extra='unapproved'),
            'no original no-bet': lambda b, e: b['original'].update(rating='BET'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                bundle, event = fixture()
                mutate(bundle, event)
                # Let semantic guards, not only the hash, catch fixture edits.
                bundle['inputsSha256'] = runner.digest(bundle['inputs'])
                with self.assertRaises((runner.Blocked, KeyError, RuntimeError)):
                    runner.prepare(bundle, event, NOW)
        bundle, event = fixture()
        with self.assertRaisesRegex(runner.Blocked, 'precede kickoff'):
            runner.prepare(bundle, event, KICKOFF)

    def test_original_input_hash_is_enforced(self):
        bundle, event = fixture()
        bundle['inputs']['history_raw'][0]['scoreHome'] = 45
        with self.assertRaisesRegex(runner.Blocked, 'hash mismatch'):
            runner.prepare(bundle, event, NOW)

    def test_future_history_cannot_activate(self):
        bundle, event = fixture()
        bundle['inputs']['history_raw'].append(dict(bundle['inputs']['history_raw'][0], date=NOW.isoformat()))
        bundle['inputsSha256'] = runner.digest(bundle['inputs'])
        with self.assertRaisesRegex(runner.Blocked, 'cutoff'):
            runner.prepare(bundle, event, NOW + dt.timedelta(seconds=1))

    def test_no_numeric_adjustment_from_status(self):
        bundle, event = fixture()
        event.update(change='RULED_OUT', newStatus='OUT', replacement=None)
        event['declaration'].update(status='CONFIRMED_RULED_OUT', starter='Old QB')
        record = runner.prepare(bundle, event, NOW)
        self.assertIsNone(record['updated']['quarterbacks']['away']['starter'])
        self.assertEqual(record['original']['homeEdgePoints'], record['updated']['homeEdgePoints'])

    def test_append_only_dedup_and_concurrency(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            with ThreadPoolExecutor(max_workers=2) as pool:
                paths = list(pool.map(lambda _: runner.process_update(directory, bundle, event, lambda: NOW), range(2)))
            self.assertEqual(sum(p is not None for p in paths), 1)
            path = next(p for p in paths if p)
            frozen_bytes = path.read_bytes()
            event['reportedAt'] = NOW.isoformat()
            event['declaration']['asOf'] = NOW.isoformat()
            with patch.object(runner, 'load_engine', return_value=engine), \
                 patch.object(engine, 'predict_game', wraps=engine.predict_game) as predict:
                self.assertIsNone(runner.process_update(directory, bundle, event, lambda: NOW))
                predict.assert_not_called()
            self.assertEqual(path.read_bytes(), frozen_bytes)
            with self.assertRaisesRegex(runner.Blocked, '[Kk]ickoff'):
                runner.process_update(directory, bundle, event, lambda: KICKOFF)
            self.assertEqual(len(list(directory.glob('*.json'))), 1)

    def test_later_substantive_return_to_same_status_is_recorded(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            for index, status in enumerate(('OUT', 'CLEARED', 'OUT')):
                current = copy.deepcopy(event)
                current.update(change='CLEARED' if status == 'CLEARED' else 'RULED_OUT',
                               newStatus=status, previousStatus='OUT' if status == 'CLEARED' else 'CLEARED',
                               replacement=None, reportedAt=(NOW + dt.timedelta(hours=index)).isoformat())
                current['declaration'].update(asOf=current['reportedAt'], starter='Old QB',
                                              status='CONFIRMED_STARTER' if status == 'CLEARED' else 'CONFIRMED_RULED_OUT')
                now = NOW + dt.timedelta(hours=index, minutes=1)
                self.assertIsNotNone(runner.process_update(directory, bundle, current, lambda: now))
            self.assertEqual(len(list(directory.glob('*.json'))), 3)

    def test_weekly_output_matches_pre_refactor_engine(self):
        class Fixed(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return GENERATED.astimezone(tz)
        bundle, _ = fixture()
        files = {'nfl-schedule.json': {'season': 2030, 'weeks': [bundle['inputs']['selected']]},
                 'nfl-historical-results.json': bundle['inputs']['history_raw']}
        def load(name):
            if name not in files:
                raise FileNotFoundError(name)
            return files[name]
        with tempfile.TemporaryDirectory() as temp, patch.object(engine, 'DATA', Path(temp)), \
             patch.object(engine, 'load', side_effect=load), patch.object(engine.dt, 'datetime', Fixed):
            engine.main()
            result = json.loads((Path(temp) / 'model-c-automated-draft.json').read_text())
        # Captured by executing the unmodified engine blob f727e761bd7ab52b5fa6224b29e80d7bf5e68fd9
        # with this same synthetic fixture and fixed clock. All output fields are covered.
        self.assertEqual(runner.digest(result), '1d995e130f7188c253d4009ec8ba01ae032f66c12a914f5cb0c7d92295bbb741')

    def test_production_output_directory_is_rejected(self):
        bundle, event = fixture()
        with self.assertRaises(runner.Blocked):
            runner.process_update(SCRIPTS, bundle, event, lambda: NOW)

    def test_both_teams_updates_are_cumulative(self):
        bundle, away = fixture()
        bundle['inputs']['qb_candidates']['Home'] = {'candidate': 'Home Old'}
        bundle['inputsSha256'] = runner.digest(bundle['inputs'])
        args = {k: v for k, v in bundle['inputs'].items() if k != 'selected'}
        bundle['original'] = engine.predict_game(bundle['inputs']['selected']['games'][0], now=GENERATED, **args)
        home = copy.deepcopy(away)
        home.update(team='Home', quarterback='Home Old', replacement='Home New', reportedAt=NOW.isoformat())
        home['declaration'].update(team='Home', starter='Home New', asOf=NOW.isoformat())
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            first = runner.process_update(directory, bundle, away, lambda: NOW)
            original_bytes = first.read_bytes()
            second = runner.process_update(directory, bundle, home, lambda: NOW + dt.timedelta(minutes=1))
            result = json.loads(second.read_text())
            self.assertEqual(result['updated']['quarterbacks']['away']['starter'], 'New QB')
            self.assertEqual(result['updated']['quarterbacks']['home']['starter'], 'Home New')
            self.assertEqual(len(result['inputChanges']), 2)
            self.assertEqual(len(result['priorUpdateIds']), 1)
            self.assertEqual(first.read_bytes(), original_bytes)

    def test_replacement_can_later_be_ruled_out_without_reverting(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            runner.process_update(directory, bundle, event, lambda: NOW)
            event.update(quarterback='New QB', replacement=None, change='RULED_OUT',
                         previousStatus='STARTER', newStatus='OUT', reportedAt=NOW.isoformat())
            event['declaration'].update(starter='New QB', status='CONFIRMED_RULED_OUT', asOf=NOW.isoformat())
            path = runner.process_update(directory, bundle, event, lambda: NOW + dt.timedelta(minutes=1))
            result = json.loads(path.read_text())
            self.assertIsNone(result['updated']['quarterbacks']['away']['starter'])
            self.assertEqual(result['inputChanges'][0]['new']['starter'], 'New QB')

    def test_numeric_dependency_is_blocked_instead_of_carried_forward(self):
        for reason in ('QB injury points', 'Unknown adjustment', 'Non-QB adjustment'):
            with self.subTest(reason=reason):
                bundle, event = fixture()
                bundle['inputs']['adjustments']['games']['0'] = {'away': {
                    'points': -2, 'reason': reason, 'source': 'https://nfl.com/test',
                    'asOf': (GENERATED - dt.timedelta(hours=1)).isoformat()}}
                bundle['inputsSha256'] = runner.digest(bundle['inputs'])
                args = {k: v for k, v in bundle['inputs'].items() if k != 'selected'}
                bundle['original'] = engine.predict_game(bundle['inputs']['selected']['games'][0], now=GENERATED, **args)
                with self.assertRaisesRegex(runner.Blocked, 'dependent-input reassessment'):
                    runner.prepare(bundle, event, NOW)

    def test_upgrading_from_out_is_not_a_downgrade(self):
        bundle, event = fixture()
        event.update(change='DOWNGRADED', newStatus='QUESTIONABLE', previousStatus='OUT', replacement=None)
        event['declaration'].update(starter='Old QB', status='CONFIRMED_DOWNGRADED')
        with self.assertRaisesRegex(runner.Blocked, 'does not worsen'):
            runner.prepare(bundle, event, NOW)

    def test_hash_loader_never_uses_import_cache_or_creates_bytecode(self):
        bundle, _ = fixture()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'model_c_engine.py'
            path.write_bytes(runner.ENGINE.read_bytes())
            with patch.object(runner, 'ENGINE', path):
                self.assertEqual(runner.load_engine(bundle).ISOLATED_API_VERSION, 1)
            self.assertFalse((Path(temp) / '__pycache__').exists())

    def test_kickoff_during_evaluation_blocks_publication(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            ticks = iter((NOW, KICKOFF))
            with self.assertRaisesRegex(runner.Blocked, '[Kk]ickoff'):
                runner.process_update(directory, bundle, event, lambda: next(ticks))
            self.assertEqual(list(directory.glob('*.json')), [])

    def test_simultaneous_dedup_does_not_rerun_the_model(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            with patch.object(runner, 'load_engine', return_value=engine), \
                 patch.object(engine, 'predict_game', wraps=engine.predict_game) as predict, \
                 ThreadPoolExecutor(max_workers=2) as pool:
                paths = list(pool.map(lambda _: runner.process_update(directory, bundle, event, lambda: NOW), range(2)))
                self.assertEqual(predict.call_count, 2)  # One baseline replay + one update total.
            self.assertEqual(sum(path is not None for path in paths), 1)

    def test_stale_conflicting_status_does_not_execute_model(self):
        bundle, event = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            runner.process_update(directory, bundle, event, lambda: NOW)
            event.update(quarterback='New QB', change='RULED_OUT', newStatus='OUT', replacement=None)
            with patch.object(runner, 'load_engine', return_value=engine), \
                 patch.object(engine, 'predict_game', wraps=engine.predict_game) as predict:
                with self.assertRaisesRegex(runner.Blocked, 'Stale or conflicting'):
                    runner.process_update(directory, bundle, event, lambda: NOW)
                predict.assert_not_called()

    def test_repeat_out_after_replacement_is_suppressed_without_model(self):
        bundle, replacement = fixture()
        ruled_out = copy.deepcopy(replacement)
        ruled_out.update(change='RULED_OUT', newStatus='OUT', replacement=None)
        ruled_out['declaration'].update(starter='Old QB', status='CONFIRMED_RULED_OUT')
        replacement['reportedAt'] = NOW.isoformat()
        replacement['declaration']['asOf'] = NOW.isoformat()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'model-c-isolated-updates'
            directory.mkdir()
            runner.process_update(directory, bundle, ruled_out, lambda: NOW)
            runner.process_update(directory, bundle, replacement, lambda: NOW + dt.timedelta(minutes=1))
            ruled_out['reportedAt'] = (NOW + dt.timedelta(minutes=2)).isoformat()
            ruled_out['declaration']['asOf'] = ruled_out['reportedAt']
            with patch.object(runner, 'load_engine', return_value=engine), \
                 patch.object(engine, 'predict_game', wraps=engine.predict_game) as predict:
                self.assertIsNone(runner.process_update(directory, bundle, ruled_out,
                                                       lambda: NOW + dt.timedelta(minutes=3)))
                predict.assert_not_called()
            self.assertEqual(len(list(directory.glob('*.json'))), 2)


if __name__ == '__main__':
    unittest.main()
