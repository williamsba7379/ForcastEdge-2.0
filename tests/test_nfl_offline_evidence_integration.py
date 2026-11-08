"""Eight synthetic-only end-to-end tests; temporary databases, no network."""
import datetime as dt
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from nfl_offline_capture_envelope import SOURCE
from nfl_offline_evidence_integration import prepare, persist, verify_persisted

UTC = dt.timezone.utc
KICKOFF = dt.datetime(2026, 11, 8, 18, 0, tzinfo=UTC)
CAPTURE = dt.datetime(2026, 11, 8, 22, 1, tzinfo=UTC)
KEY = b"synthetic-only-integration-hmac-secret-1234567890"
REF = "fixture://local/401123456"


def fixture(*, completed=True, event_id="401123456"):
    schedule = dict(gameId="401123456", season=2026, week=10,
                    homeTeamId="1", awayTeamId="2", kickoffAt="2026-11-08T18:00:00Z")
    event = dict(id=event_id, season=dict(year=2026), week=dict(number=10),
                 date=schedule["kickoffAt"], status=dict(type=dict(completed=completed)),
                 competitions=[dict(competitors=[
                     dict(homeAway="home", team=dict(id="1"), score="21"),
                     dict(homeAway="away", team=dict(id="2"), score="17")])])
    raw = json.dumps(dict(events=[event]), sort_keys=True).encode("utf-8")
    return schedule, raw


class OfflineEvidenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "evidence.sqlite3")
        self.schedule, self.raw = fixture()

    def prepare(self, **changes):
        args = dict(game_id="401123456", source=SOURCE, response_bytes=self.raw,
                    request_started_at=CAPTURE - dt.timedelta(seconds=1),
                    clock=lambda: CAPTURE, schedule=self.schedule)
        args.update(changes)
        return prepare(**args)

    def stored(self):
        envelope, record, reason = self.prepare()
        self.assertEqual(reason, "VALIDATED_OFFLINE_FINAL")
        manifest, signature, anchor, result = persist(
            db_path=self.path, envelope=envelope, record=record,
            schedule=self.schedule, secret=KEY, storage_reference=REF)
        self.assertEqual(result, "STORED_OFFLINE_FINAL")
        return envelope, record, manifest, signature, anchor

    def verify(self, envelope, manifest, signature, anchor, **changes):
        args = dict(db_path=self.path, game_id="401123456", envelope=envelope,
                    manifest=manifest, signature=signature, secret=KEY,
                    external_anchor=anchor, expected_storage_reference=REF)
        args.update(changes)
        return verify_persisted(**args)

    def test_valid_final_roundtrip(self):
        envelope, record, manifest, signature, anchor = self.stored()
        self.assertEqual(self.verify(envelope, manifest, signature, anchor),
                         (True, "VERIFIED_OFFLINE_STORED_EVIDENCE"))

    def test_non_final_rejected_without_insert(self):
        schedule, raw = fixture(completed=False)
        self.assertEqual(self.prepare(response_bytes=raw)[2], "NOT_FINAL")
        self.assertFalse(Path(self.path).exists())

    def test_wrong_game_identity_rejected(self):
        schedule, raw = fixture(event_id="999")
        self.assertEqual(self.prepare(response_bytes=raw)[2], "GAME_ID_NOT_UNIQUE")
        self.assertFalse(Path(self.path).exists())

    def test_timestamp_mismatch_rejected(self):
        envelope, record, reason = self.prepare(
            request_started_at=CAPTURE + dt.timedelta(seconds=1))
        self.assertIsNone(record)
        self.assertEqual(reason, "UNVERIFIABLE_OFFLINE_FIXTURE")
        self.assertFalse(Path(self.path).exists())

    def test_altered_raw_response_rejected(self):
        envelope, record, reason = self.prepare()
        altered = dict(record, rawResponse=record["rawResponse"] + " ")
        self.assertEqual(persist(db_path=self.path, envelope=envelope, record=altered,
                                 schedule=self.schedule, secret=KEY,
                                 storage_reference=REF)[3], "ENVELOPE_RECORD_MISMATCH")
        self.assertFalse(Path(self.path).exists())

    def test_duplicate_immutable_first_observation(self):
        envelope, record, manifest, signature, anchor = self.stored()
        self.assertEqual(persist(db_path=self.path, envelope=envelope, record=record,
                                 schedule=self.schedule, secret=KEY,
                                 storage_reference=REF)[3],
                         "EXISTING_FIRST_OBSERVATION_IMMUTABLE")
        self.assertTrue(self.verify(envelope, manifest, signature, anchor)[0])

    def test_restart_persistence_and_manifest_linkage(self):
        envelope, record, manifest, signature, anchor = self.stored()
        self.assertTrue(self.verify(envelope, manifest, signature, anchor)[0])
        self.assertEqual(self.verify(envelope, manifest, signature, anchor,
                                    expected_storage_reference="fixture://wrong")[1],
                         "STORAGE_REFERENCE_MISMATCH")

    def test_coordinated_database_tamper_detected_by_external_anchor(self):
        envelope, record, manifest, signature, anchor = self.stored()
        changed = dict(record, rawResponse=record["rawResponse"] + " ")
        changed["contentSha256"] = hashlib.sha256(changed["rawResponse"].encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER reject_evidence_update")
            db.execute("UPDATE first_final_evidence SET evidence_json=?, raw_response=?, content_sha256=? WHERE game_id=?",
                       (json.dumps(changed, sort_keys=True, separators=(",", ":")),
                        changed["rawResponse"], changed["contentSha256"], changed["gameId"]))
        self.assertEqual(self.verify(envelope, manifest, signature, anchor)[1],
                         "STORED_EVIDENCE_MISMATCH")
        self.assertEqual(self.verify(envelope, manifest, signature, None)[1],
                         "MISSING_EXTERNAL_TRUST_ANCHOR")


if __name__ == "__main__":
    unittest.main()
