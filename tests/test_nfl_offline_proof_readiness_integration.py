"""Eight synthetic integration regression tests; no live services."""
import datetime as dt
import hashlib
import hmac
import unittest
from pathlib import Path

from nfl_signed_evidence_manifest import canonical_bytes
from nfl_offline_proof_readiness_integration import assess_offline_proof_readiness
from test_nfl_offline_readiness_gate import OfflineReadinessGateTests


TS_KEY = b"test-only-ts-proof-key-12345678901234567890"
AR_KEY = b"test-only-archive-proof-key-12345678901234567890"


def digest(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sign(obj, key):
    return dict(obj, signature=hmac.new(key, canonical_bytes(obj), hashlib.sha256).hexdigest())


class ProofReadinessIntegrationTests(unittest.TestCase):
    """Reuse the existing fixture setup without inheriting its test methods."""

    def setUp(self):
        OfflineReadinessGateTests.setUp(self)
        base = self.kw
        timestamp = sign(dict(
            kind="timestamp", authorityId="ts-fixture", proofId="ts-proof-001",
            gameId=base["game_id"], contentSha256=self.envelope["contentSha256"],
            issuedAt=base["receipt"]["issuedAt"]), TS_KEY)
        archive = sign(dict(
            kind="archive", authorityId="archive-fixture", proofId="archive-proof-001",
            gameId=base["game_id"], manifestSha256=digest(self.manifest),
            timestampProofSha256=digest(timestamp),
            archivedAt="2026-11-08T22:01:02Z"), AR_KEY)
        self.params = dict(base,
            timestamp_receipt=timestamp, archive_receipt=archive,
            timestamp_authorities={"ts-fixture": {"status": "trusted", "testKey": TS_KEY}},
            archive_authorities={"archive-fixture": {"status": "trusted", "testKey": AR_KEY}},
            expected_timestamp_id="ts-proof-001",
            expected_archive_id="archive-proof-001")

    def evaluate(self, **changes):
        return assess_offline_proof_readiness(**dict(self.params, **changes))

    def deny(self, reason, **changes):
        ok, actual, metadata = self.evaluate(**changes)
        self.assertFalse(ok)
        self.assertEqual(actual, reason)
        self.assertIs(metadata["productionReady"], False)

    def test_successful_synthetic_integration(self):
        ok, reason, metadata = self.evaluate()
        self.assertTrue(ok)
        self.assertEqual(reason, "SYNTHETIC_OFFLINE_CHAIN_VERIFIED_NOT_PRODUCTION_READY")
        self.assertEqual(metadata["evidenceClass"], "SYNTHETIC_OFFLINE_ONLY")

    def test_missing_proofs(self):
        self.deny("UNTRUSTED_TIMESTAMP_PROOF", timestamp_receipt=None)
        self.deny("UNTRUSTED_ARCHIVE_PROOF", archive_receipt=None)

    def test_forged_signature(self):
        self.deny("UNTRUSTED_TIMESTAMP_PROOF",
                  timestamp_receipt=dict(self.params["timestamp_receipt"], signature="0"*64))

    def test_mismatched_manifest(self):
        changed = dict(self.manifest, storageReference="fixture://wrong")
        self.deny("ARCHIVE_BINDING_MISMATCH", manifest=changed)

    def test_replayed_proof_id(self):
        self.deny("REPLAYED_OR_INCONSISTENT_PROOF_ID", used_proof_ids={"ts-proof-001"})

    def test_failed_storage_verification(self):
        self.deny("STORAGE_UNAVAILABLE", db_path=Path(self.db).with_name("missing.sqlite3"))

    def test_incomplete_submission(self):
        self.deny("INCOMPLETE_SUBMISSION", submission_state="PENDING")

    def test_no_production_ready_status(self):
        ok, reason, metadata = self.evaluate()
        self.assertTrue(ok)
        self.assertIs(metadata["productionReady"], False)
        self.assertNotEqual(reason, "PRODUCTION_READY")


if __name__ == "__main__":
    unittest.main()
