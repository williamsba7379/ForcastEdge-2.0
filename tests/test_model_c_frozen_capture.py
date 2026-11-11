"""Prospective capture integration tests in disposable Git repositories only."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import model_c_frozen_capture as capture
import model_c_isolated_update as runner
from test_model_c_isolated_update import fixture, GENERATED, NOW, KICKOFF


class CaptureIntegration(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'repository'
        (self.repo / 'scripts').mkdir(parents=True)
        (self.repo / 'data').mkdir()
        (self.repo / capture.ENGINE_PATH).write_bytes((SCRIPTS / 'model_c_engine.py').read_bytes())
        self.git('init', '-q')
        self.bundle, self.event = fixture()
        inputs = self.bundle['inputs']
        self.write_json('data/nfl-schedule.json', {'season': inputs['year'], 'weeks': [inputs['selected']]})
        self.write_json('data/nfl-historical-results.json', inputs['history_raw'])
        self.write_json('data/model-c-qb-candidates.json', {'teams': inputs['qb_candidates']})
        self.model_version = self.commit()
        self.capture_root = self.root / 'model-c-frozen-captures'
        self.capture_root.mkdir()
        self.output = self.root / 'model-c-baseline-bundles'
        self.output.mkdir()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Capture Tests', '-c', 'user.email=capture-tests@example.invalid',
                 'commit', '-qm', 'Synthetic capture fixture')
        return self.git('rev-parse', 'HEAD')

    def write_json(self, path, value):
        destination = self.repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, indent=2) + '\n')

    def artifacts(self, clock=lambda: GENERATED):
        return capture.prospective_capture(self.repo, self.model_version, self.repo / 'data', clock)

    def archived(self):
        artifacts = self.artifacts()
        directory = capture.publish_capture(self.capture_root, artifacts, lambda: GENERATED)
        manifest, inputs, generation, _ = capture.validate_capture(directory)
        self.archive_path = 'captures/' + manifest['captureId']
        shutil.copytree(directory, self.repo / self.archive_path)
        self.frozen = dict(status='FROZEN_PREKICKOFF', season=generation['season'], week=generation['week'],
                           modelCGeneratedAt=generation['generatedAt'], frozenAt=self.bundle['frozenAt'],
                           games=[dict(id=g['id'], date=g['date'], home=g['home'], away=g['away'],
                                       picks={'C': g['pick']}) for g in generation['games']])
        self.write_json('data/frozen.json', self.frozen)
        self.archive_version = self.commit()
        self.freeze_link = capture.REPO + self.archive_version + '/data/frozen.json'
        return directory, artifacts

    def reviewed(self, directory, reviewed=True):
        return capture.reviewed_bundle(self.repo, directory, self.archive_version, self.archive_path,
                                       self.freeze_link, '0', reviewed, lambda: NOW)

    def test_end_to_end_capture_freeze_bundle_then_isolated_update(self):
        directory, artifacts = self.archived()
        manifest = json.loads(artifacts['manifest.json'])
        self.assertFalse(manifest['reviewed'])
        self.assertEqual(manifest['status'], 'UNREVIEWED_PROSPECTIVE_CAPTURE')
        bundle = self.reviewed(directory)
        path = capture.publish_bundle(self.output, bundle, lambda: NOW)
        self.assertEqual(json.loads(path.read_text()), bundle)
        updates = self.root / 'model-c-isolated-updates'
        updates.mkdir()
        with patch.object(runner, 'ENGINE', self.repo / capture.ENGINE_PATH):
            update = runner.process_update(updates, bundle, self.event, lambda: NOW)
        record = json.loads(update.read_text())
        self.assertEqual(record['label'], 'UPDATED MODEL C')
        self.assertEqual(record['updated']['quarterbacks']['away']['starter'], 'New QB')
        self.assertEqual(record['original']['pick'], record['updated']['pick'])
        self.assertEqual(record['rating'], 'NO BET')
        self.assertEqual(bundle['modelVersion'], self.model_version)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_exact_raw_bytes_and_missing_optional_inputs_preserved(self):
        before = {p.name: p.read_bytes() for p in (self.repo / 'data').iterdir()}
        artifacts = self.artifacts()
        directory = capture.publish_capture(self.capture_root, artifacts, lambda: GENERATED)
        manifest, inputs, generation, _ = capture.validate_capture(directory)
        for name, raw in before.items():
            self.assertEqual((directory / 'raw' / name).read_bytes(), raw)
            self.assertEqual((self.repo / 'data' / name).read_bytes(), raw)
        self.assertFalse(manifest['sourceInventory']['model-c-qb-starters.json']['present'])
        self.assertFalse((directory / 'raw/model-c-qb-starters.json').exists())
        self.assertEqual(inputs['qb_declarations'], {})
        self.assertFalse((self.repo / 'data/model-c-automated-draft.json').exists())
        self.assertEqual(len(generation['games']), 10)

    def test_dirty_or_wrong_engine_cannot_claim_a_pinned_version(self):
        (self.repo / capture.ENGINE_PATH).write_text('# dirty engine\n')
        with self.assertRaisesRegex(runner.Blocked, 'differs from the pinned'):
            self.artifacts()

    def test_source_changed_during_generation_blocks_capture(self):
        original_loader = capture.engine_from_source
        def loading(source, path):
            engine = original_loader(source, path)
            predict = engine.predict_game
            def changed(*args, **kwargs):
                (self.repo / 'data/model-c-qb-candidates.json').write_text('{}')
                return predict(*args, **kwargs)
            engine.predict_game = changed
            return engine
        with patch.object(capture, 'engine_from_source', side_effect=loading):
            with self.assertRaisesRegex(runner.Blocked, 'Source changed'):
                self.artifacts()
        self.assertEqual(list(self.capture_root.iterdir()), [])

    def test_no_overwrite_even_when_existing_capture_directory_is_empty(self):
        artifacts = self.artifacts()
        capture_id = json.loads(artifacts['manifest.json'])['captureId']
        empty = self.capture_root / capture_id
        empty.mkdir()
        with self.assertRaises(FileExistsError):
            capture.publish_capture(self.capture_root, artifacts, lambda: GENERATED)
        self.assertEqual(list(empty.iterdir()), [])
        empty.rmdir()
        first = capture.publish_capture(self.capture_root, artifacts, lambda: GENERATED)
        preserved = (first / 'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):
            capture.publish_capture(self.capture_root, artifacts, lambda: GENERATED)
        self.assertEqual((first / 'manifest.json').read_bytes(), preserved)
        self.assertEqual(len(list(self.capture_root.iterdir())), 1)

    def test_no_missing_or_tampered_raw_source_is_accepted(self):
        directory, _ = self.archived()
        raw = directory / 'raw/nfl-schedule.json'
        raw.write_bytes(b'{}')
        with self.assertRaisesRegex(runner.Blocked, 'hash mismatch'):
            self.reviewed(directory)

    def test_archive_claim_must_match_every_committed_byte(self):
        directory, _ = self.archived()
        self.archive_version = self.model_version
        with self.assertRaises(subprocess.CalledProcessError):
            self.reviewed(directory)

    def test_unreviewed_capture_cannot_become_a_reviewed_bundle(self):
        directory, _ = self.archived()
        with self.assertRaisesRegex(runner.Blocked, 'Explicit provenance review'):
            self.reviewed(directory, reviewed=False)

    def test_different_generation_freeze_and_winner_are_rejected(self):
        directory, _ = self.archived()
        for change in ('time', 'winner', 'slate'):
            frozen = copy.deepcopy(self.frozen)
            if change == 'time':
                frozen['modelCGeneratedAt'] = NOW.isoformat()
            elif change == 'winner':
                frozen['games'][0]['picks']['C'] = 'Away'
            else:
                frozen['games'].pop()
            self.write_json('data/frozen.json', frozen)
            commit = self.commit()
            with self.subTest(change=change), self.assertRaises(runner.Blocked):
                capture.reviewed_bundle(self.repo, directory, self.archive_version, self.archive_path,
                                        capture.REPO + commit + '/data/frozen.json', '0', True, lambda: NOW)

    def test_capture_cannot_be_reconstructed_after_an_earlier_freeze(self):
        directory, _ = self.archived()
        frozen = copy.deepcopy(self.frozen)
        frozen['frozenAt'] = (GENERATED - capture.dt.timedelta(seconds=1)).isoformat()
        self.write_json('data/frozen.json', frozen)
        commit = self.commit()
        with self.assertRaisesRegex(runner.Blocked, 'historical reconstruction'):
            capture.reviewed_bundle(self.repo, directory, self.archive_version, self.archive_path,
                                    capture.REPO + commit + '/data/frozen.json', '0', True, lambda: NOW)

    def test_kickoff_during_capture_or_publication_blocks_all_output(self):
        ticks = iter((GENERATED, KICKOFF))
        with self.assertRaisesRegex(runner.Blocked, 'Kickoff'):
            self.artifacts(lambda: next(ticks))
        artifacts = self.artifacts()
        with self.assertRaisesRegex(runner.Blocked, 'Kickoff'):
            capture.publish_capture(self.capture_root, artifacts, lambda: KICKOFF)
        self.assertEqual(list(self.capture_root.iterdir()), [])

    def test_reviewed_bundle_cannot_overwrite_or_publish_after_kickoff(self):
        directory, _ = self.archived()
        bundle = self.reviewed(directory)
        path = capture.publish_bundle(self.output, bundle, lambda: NOW)
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            capture.publish_bundle(self.output, bundle, lambda: NOW)
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaisesRegex(runner.Blocked, 'Kickoff'):
            capture.publish_bundle(self.output, bundle, lambda: KICKOFF)

    def test_production_output_paths_and_source_symlinks_are_rejected(self):
        with self.assertRaises(runner.Blocked):
            capture.publish_capture(self.repo / 'data', self.artifacts(), lambda: GENERATED)
        source = self.repo / 'data/model-c-qb-candidates.json'
        alternate = self.root / 'candidates.json'
        alternate.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(alternate)
        with self.assertRaisesRegex(runner.Blocked, 'symlinks'):
            self.artifacts()

    def test_short_slate_and_future_dated_qb_sources_are_blocked(self):
        schedule_path = self.repo / 'data/nfl-schedule.json'
        original = schedule_path.read_bytes()
        schedule = json.loads(original)
        schedule['weeks'][0]['games'] = schedule['weeks'][0]['games'][:1]
        schedule_path.write_text(json.dumps(schedule))
        with self.assertRaisesRegex(RuntimeError, 'Too few'):
            self.artifacts()
        schedule_path.write_bytes(original)
        self.write_json('data/model-c-qb-starters.json', {'teams': {'Away': {'asOf': NOW.isoformat()}}})
        with self.assertRaisesRegex(runner.Blocked, 'Future-dated'):
            self.artifacts()


if __name__ == '__main__':
    unittest.main()
