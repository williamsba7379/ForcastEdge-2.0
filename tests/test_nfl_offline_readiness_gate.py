"""Ten synthetic offline readiness failure tests; no external services."""
import datetime as dt
import hashlib
import hmac
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from nfl_offline_capture_envelope import SOURCE
from nfl_offline_evidence_integration import prepare, persist
from nfl_offline_readiness_gate import assess
from nfl_signed_evidence_manifest import canonical_bytes
from test_nfl_offline_evidence_integration import fixture, CAPTURE, KEY, REF


class OfflineReadinessGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "first.sqlite3"
        schedule, raw = fixture()
        envelope, record, result = prepare(
            game_id="401123456", source=SOURCE, response_bytes=raw,
            request_started_at=CAPTURE - dt.timedelta(seconds=1),
            clock=lambda: CAPTURE, schedule=schedule)
        self.assertEqual(result, "VALIDATED_OFFLINE_FINAL")
        manifest, signature, digest, result = persist(
            db_path=str(self.db), envelope=envelope, record=record,
            schedule=schedule, secret=KEY, storage_reference=REF)
        self.assertEqual(result, "STORED_OFFLINE_FINAL")
        self.envelope = envelope
        self.manifest = manifest
        self.signature = signature
        self.kw = dict(
            envelope=envelope, manifest=manifest, signature=signature,
            receipt=dict(trusted=True, gameId="401123456",
                         contentSha256=envelope["contentSha256"],
                         issuedAt="2026-11-08T22:01:01Z"),
            external_anchor=dict(protected=True, gameId="401123456", digest=digest),
            key_id="v1", key_registry={"v1": dict(status="active", secret=KEY)},
            db_path=self.db, game_id="401123456")
        self.assertEqual(assess(**self.kw), (True, "SYNTHETIC_READINESS_GATE_PASSED"))

    def check(self, expected, **overrides):
        args = dict(self.kw)
        args.update(overrides)
        self.assertEqual(assess(**args), (False, expected))

    def test_missing_trusted_timestamp_receipt(self):
        self.check("MISSING_TRUSTED_TIMESTAMP_RECEIPT", receipt=None)

    def test_inconsistent_timestamp_receipt(self):
        receipt = dict(self.kw["receipt"], issuedAt="2026-11-08T21:59:00Z")
        self.check("TIMESTAMP_RECEIPT_MISMATCH", receipt=receipt)

    def test_missing_protected_external_anchor(self):
        self.check("MISSING_PROTECTED_EXTERNAL_ANCHOR", external_anchor=None)

    def test_crash_before_anchoring_fails_closed(self):
        self.check("INCOMPLETE_SUBMISSION", submission_state="COMMITTED_NOT_ANCHORED")

    def test_unknown_and_revoked_hmac_key(self):
        self.check("UNKNOWN_OR_REVOKED_KEY", key_id="missing")
        self.check("UNKNOWN_OR_REVOKED_KEY",
                   key_registry={"v1": dict(status="revoked", secret=KEY)})

    def test_rotated_key_cannot_verify_old_signature(self):
        rotated = b"another-synthetic-test-key-rotated-123456789"
        self.check("KEY_OR_SIGNATURE_MISMATCH",
                   key_registry={"v1": dict(status="active", secret=rotated)})

    def test_missing_database_is_not_recreated(self):
        self.db.unlink()
        self.check("STORAGE_UNAVAILABLE")
        self.assertFalse(self.db.exists())

    def test_restored_database_anchor_mismatch(self):
        # Model a restore paired with a stale external anchor.
        other = dict(self.kw["external_anchor"], digest="0" * 64)
        self.check("EXTERNAL_ANCHOR_MISMATCH", external_anchor=other)

    def test_corrupt_or_unavailable_storage(self):
        self.db.write_bytes(b"not a sqlite database")
        self.check("STORAGE_CORRUPT_OR_UNAVAILABLE")
        self.check("STORAGE_UNAVAILABLE", db_path=self.root / "unavailable.sqlite3")

    def test_incomplete_submission_fails_closed(self):
        self.check("INCOMPLETE_SUBMISSION", submission_state="PENDING")
        self.check("INCOMPLETE_SUBMISSION", submission_state="FAILED")


if __name__ == "__main__":
    unittest.main()
