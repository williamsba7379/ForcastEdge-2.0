"""Eight synthetic proof-verification tests. No network or production keys."""
import datetime as dt
import hashlib
import hmac
import unittest

from nfl_offline_capture_envelope import SOURCE, capture_envelope
from nfl_signed_evidence_manifest import canonical_bytes, make_manifest
from nfl_offline_external_proof_verifier import verify_external_proofs

TKEY = b"timestamp-fixture-only-key-0000000000000001"
AKEY = b"archive-fixture-only-key-000000000000000002"
NOW = dt.datetime(2026, 11, 8, 22, 0, tzinfo=dt.timezone.utc)

def digest(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()

def sign(payload, key):
    return dict(payload, signature=hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest())

class ExternalProofTests(unittest.TestCase):
    def setUp(self):
        self.envelope = capture_envelope(
            game_id="401123456", source=SOURCE, response_bytes=b'{"events":[]}',
            clock=lambda: NOW, request_started_at=NOW - dt.timedelta(seconds=1))
        self.manifest = make_manifest(self.envelope, storage_reference="fixture://401123456")
        self.timestamp = sign(dict(
            kind="timestamp", authorityId="test-ts", proofId="ts-001",
            gameId="401123456", contentSha256=self.envelope["contentSha256"],
            issuedAt="2026-11-08T22:00:01Z"), TKEY)
        self.archive = sign(dict(
            kind="archive", authorityId="test-archive", proofId="ar-001",
            gameId="401123456", manifestSha256=digest(self.manifest),
            timestampProofSha256=digest(self.timestamp),
            archivedAt="2026-11-08T22:00:02Z"), AKEY)
        self.args = dict(
            envelope=self.envelope, manifest=self.manifest,
            timestamp_receipt=self.timestamp, archive_receipt=self.archive,
            timestamp_authorities={"test-ts": {"status": "trusted", "testKey": TKEY}},
            archive_authorities={"test-archive": {"status": "trusted", "testKey": AKEY}},
            expected_timestamp_id="ts-001", expected_archive_id="ar-001")

    def check(self, expected, **overrides):
        args = dict(self.args)
        args.update(overrides)
        self.assertEqual(verify_external_proofs(**args), (False, expected))

    def test_valid_signed_timestamp_receipt(self):
        self.assertEqual(verify_external_proofs(**self.args),
                         (True, "SYNTHETIC_EXTERNAL_PROOFS_VERIFIED"))

    def test_forged_timestamp_signature_rejected(self):
        self.check("UNTRUSTED_TIMESTAMP_PROOF",
                   timestamp_receipt=dict(self.timestamp, signature="0" * 64))

    def test_untrusted_timestamp_authority_rejected(self):
        self.check("UNTRUSTED_TIMESTAMP_PROOF", timestamp_authorities={})

    def test_wrong_timestamp_evidence_hash_rejected(self):
        bad = dict(self.timestamp, contentSha256="0" * 64)
        bad.pop("signature")
        self.check("TIMESTAMP_EVIDENCE_MISMATCH", timestamp_receipt=sign(bad, TKEY))

    def test_valid_signed_archive_receipt(self):
        self.assertEqual(verify_external_proofs(**self.args)[0], True)
        self.check("UNTRUSTED_ARCHIVE_PROOF", archive_authorities={})

    def test_missing_or_forged_archive_receipt_rejected(self):
        self.check("UNTRUSTED_ARCHIVE_PROOF", archive_receipt=None)
        self.check("UNTRUSTED_ARCHIVE_PROOF",
                   archive_receipt=dict(self.archive, signature="0" * 64))

    def test_wrong_manifest_binding_rejected(self):
        bad = dict(self.archive, manifestSha256="0" * 64)
        bad.pop("signature")
        self.check("ARCHIVE_BINDING_MISMATCH", archive_receipt=sign(bad, AKEY))

    def test_replayed_or_inconsistent_proof_identity_rejected(self):
        self.check("REPLAYED_OR_INCONSISTENT_PROOF_ID", used_proof_ids={"ts-001"})
        self.check("REPLAYED_OR_INCONSISTENT_PROOF_ID", expected_archive_id="ar-previous")

if __name__ == "__main__":
    unittest.main()
