"""Eight offline-only synthetic trust-policy regression tests; no real keys."""
import datetime as dt
import hashlib
import unittest

from nfl_offline_capture_envelope import SOURCE, capture_envelope
from nfl_signed_evidence_manifest import canonical_bytes, make_manifest
from nfl_offline_trust_policy_validator import assess_trust_policy


NOW = dt.datetime(2026, 11, 8, 22, 0, tzinfo=dt.timezone.utc)


def digest(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


class OfflineTrustPolicyTests(unittest.TestCase):
    def setUp(self):
        envelope = capture_envelope(
            game_id="401123456", source=SOURCE, response_bytes=b'{"events":[]}',
            request_started_at=NOW - dt.timedelta(seconds=1), clock=lambda: NOW)
        manifest = make_manifest(envelope, storage_reference="fixture://401123456")
        ts = dict(authorityId="ts-fixture", proofId="ts-001",
                  gameId="401123456", contentSha256=envelope["contentSha256"],
                  issuedAt="2026-11-08T22:00:01Z")
        archive = dict(authorityId="archive-fixture", proofId="ar-001",
                       gameId="401123456", manifestSha256=digest(manifest),
                       timestampProofSha256=digest(ts),
                       archivedAt="2026-11-08T22:00:02Z",
                       protectionStatus="independently_protected",
                       retentionStatus="locked")
        authority = dict(status="trusted", certificateStatus="valid",
                         revocationStatus="good", validFrom="2026-01-01T00:00:00Z",
                         validUntil="2027-01-01T00:00:00Z")
        self.kw = dict(envelope=envelope, manifest=manifest,
                       timestamp_proof=ts, archive_proof=archive,
                       timestamp_authorities={"ts-fixture": dict(authority)},
                       archive_authorities={"archive-fixture": dict(authority)},
                       expected_timestamp_id="ts-001", expected_archive_id="ar-001")

    def evaluate(self, **changes):
        return assess_trust_policy(**dict(self.kw, **changes))

    def reject(self, reason, **changes):
        accepted, actual, meta = self.evaluate(**changes)
        self.assertFalse(accepted)
        self.assertEqual(actual, reason)
        self.assertIs(meta["productionReady"], False)

    def test_valid_research_only_evidence(self):
        accepted, reason, meta = self.evaluate()
        self.assertTrue(accepted)
        self.assertEqual(reason, "SYNTHETIC_TRUST_POLICY_ACCEPTED_NOT_CRYPTOGRAPHICALLY_VERIFIED")
        self.assertIs(meta["productionReady"], False)

    def test_missing_timestamp_authority(self):
        proof = dict(self.kw["timestamp_proof"])
        proof.pop("authorityId")
        self.reject("MISSING_TIMESTAMP_AUTHORITY", timestamp_proof=proof)

    def test_unknown_or_revoked_authority(self):
        self.reject("UNTRUSTED_TIMESTAMP_AUTHORITY", timestamp_authorities={})
        authority = dict(self.kw["timestamp_authorities"]["ts-fixture"], status="revoked")
        self.reject("UNTRUSTED_TIMESTAMP_AUTHORITY",
                    timestamp_authorities={"ts-fixture": authority})

    def test_expired_or_invalid_certificate_metadata(self):
        authority = dict(self.kw["timestamp_authorities"]["ts-fixture"],
                         validUntil="2026-01-02T00:00:00Z")
        self.reject("INVALID_CERTIFICATE_METADATA",
                    timestamp_authorities={"ts-fixture": authority})
        authority = dict(self.kw["timestamp_authorities"]["ts-fixture"],
                         revocationStatus="revoked")
        self.reject("INVALID_CERTIFICATE_METADATA",
                    timestamp_authorities={"ts-fixture": authority})

    def test_wrong_evidence_hash(self):
        proof = dict(self.kw["timestamp_proof"], contentSha256="0"*64)
        self.reject("TIMESTAMP_EVIDENCE_MISMATCH", timestamp_proof=proof)

    def test_missing_archival_protection(self):
        archive = dict(self.kw["archive_proof"], protectionStatus="unverified")
        self.reject("MISSING_ARCHIVAL_PROTECTION", archive_proof=archive)

    def test_replayed_or_mismatched_archive_identity(self):
        self.reject("REPLAYED_OR_MISMATCHED_PROOF_ID", used_proof_ids={"ar-001"})
        self.reject("REPLAYED_OR_MISMATCHED_PROOF_ID", expected_archive_id="ar-old")
        archive = dict(self.kw["archive_proof"], manifestSha256="0"*64)
        self.reject("ARCHIVE_BINDING_MISMATCH", archive_proof=archive)

    def test_production_ready_claim_rejected(self):
        self.reject("PRODUCTION_AUTHORIZATION_FORBIDDEN", production_requested=True)
        accepted, _, meta = self.evaluate()
        self.assertTrue(accepted)
        self.assertEqual(meta["evidenceClass"], "SYNTHETIC_METADATA_UNVERIFIED")
        self.assertIs(meta["productionReady"], False)


if __name__ == "__main__":
    unittest.main()
