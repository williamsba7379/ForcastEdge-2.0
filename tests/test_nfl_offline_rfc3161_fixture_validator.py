"""Eight synthetic-only RFC3161-like fixture checks; no real token parsing."""
import hashlib
import unittest

from nfl_offline_rfc3161_fixture_validator import validate_rfc3161_fixture


class RFC3161FixtureTests(unittest.TestCase):
    def setUp(self):
        raw = b'{"gameId":"401123456","fixture":true}'
        fixture = {
            "messageImprint": {"algorithm": "sha256", "digest": hashlib.sha256(raw).hexdigest()},
            "nonce": "nonce-001",
            "policyOid": "1.2.3.4.5",
            "signerId": "fixture-tsa",
            "extendedKeyUsage": "timeStamping",
            "tokenId": "token-001",
            "genTime": "2026-11-08T22:00:02Z",
        }
        self.kw = {
            "raw_evidence": raw, "fixture": fixture,
            "expected_nonce": "nonce-001",
            "approved_policies": {"1.2.3.4.5"},
            "approved_signers": {"fixture-tsa"},
            "expected_token_id": "token-001",
            "used_token_ids": (),
            "earliest_time": "2026-11-08T22:00:00Z",
            "latest_time": "2026-11-08T22:05:00Z",
        }

    def check(self, **changes):
        return validate_rfc3161_fixture(**dict(self.kw, **changes))

    def deny(self, expected, **changes):
        accepted, reason, metadata = self.check(**changes)
        self.assertFalse(accepted)
        self.assertEqual(reason, expected)
        self.assertIs(metadata["productionReady"], False)

    def test_valid_research_only_fixture(self):
        accepted, reason, metadata = self.check()
        self.assertTrue(accepted)
        self.assertEqual(reason, "SYNTHETIC_RFC3161_FIXTURE_ACCEPTED_RESEARCH_ONLY")
        self.assertIs(metadata["productionReady"], False)

    def test_missing_or_malformed_message_imprint(self):
        fixture = dict(self.kw["fixture"])
        fixture.pop("messageImprint")
        self.deny("MALFORMED_MESSAGE_IMPRINT", fixture=fixture)
        fixture = dict(self.kw["fixture"], messageImprint={"algorithm": "sha256", "digest": "bad"})
        self.deny("MALFORMED_MESSAGE_IMPRINT", fixture=fixture)

    def test_wrong_hash_algorithm_or_evidence_digest(self):
        fixture = dict(self.kw["fixture"], messageImprint={"algorithm": "sha1", "digest": "0"*64})
        self.deny("IMPRINT_MISMATCH", fixture=fixture)
        fixture = dict(self.kw["fixture"], messageImprint={"algorithm": "sha256", "digest": "0"*64})
        self.deny("IMPRINT_MISMATCH", fixture=fixture)

    def test_missing_or_mismatched_nonce(self):
        fixture = dict(self.kw["fixture"])
        fixture.pop("nonce")
        self.deny("NONCE_MISMATCH", fixture=fixture)
        fixture = dict(self.kw["fixture"], nonce="wrong")
        self.deny("NONCE_MISMATCH", fixture=fixture)

    def test_unapproved_timestamp_policy(self):
        fixture = dict(self.kw["fixture"], policyOid="1.2.3.4.999")
        self.deny("UNAPPROVED_TIMESTAMP_POLICY", fixture=fixture)

    def test_wrong_signer_identity_or_signing_purpose(self):
        fixture = dict(self.kw["fixture"], signerId="unknown-tsa")
        self.deny("UNAPPROVED_TIMESTAMP_SIGNER", fixture=fixture)
        fixture = dict(self.kw["fixture"], extendedKeyUsage="serverAuth")
        self.deny("UNAPPROVED_TIMESTAMP_SIGNER", fixture=fixture)

    def test_invalid_timestamp_or_replayed_token_identity(self):
        fixture = dict(self.kw["fixture"], genTime="2026-11-08T23:00:00Z")
        self.deny("INVALID_TIMESTAMP_WINDOW", fixture=fixture)
        self.deny("REPLAYED_OR_MISMATCHED_TOKEN_ID", used_token_ids={"token-001"})

    def test_production_ready_claim_rejected(self):
        self.deny("PRODUCTION_AUTHORIZATION_FORBIDDEN", production_requested=True)
        accepted, _, metadata = self.check()
        self.assertTrue(accepted)
        self.assertEqual(metadata["evidenceClass"], "SYNTHETIC_RFC3161_METADATA_NOT_CRYPTOGRAPHICALLY_VERIFIED")
        self.assertIs(metadata["productionReady"], False)


if __name__ == "__main__":
    unittest.main()
