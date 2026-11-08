"""Offline HMAC/anchor tests with synthetic response and local test-only key."""
import hashlib
import unittest
from nfl_offline_capture_envelope import capture_envelope, SOURCE
from nfl_signed_evidence_manifest import canonical_bytes, make_manifest, authenticate, verify
import datetime as dt

KEY = b"test-only-key-never-use-in-production-0123456789"
OTHER_KEY = b"different-test-only-key-not-production-987654"
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 8, 22, 0, tzinfo=UTC)

def sample():
    envelope = capture_envelope(game_id="123", source=SOURCE,
        response_bytes=b'{"events":[{"id":"123"}]}',
        request_started_at=NOW, clock=lambda: NOW + dt.timedelta(seconds=1))
    manifest = make_manifest(envelope, storage_reference="fixture://synthetic/123")
    anchor = hashlib.sha256(canonical_bytes(manifest)).hexdigest()
    signature = authenticate(manifest, secret=KEY)
    return envelope, manifest, anchor, signature

class SignedManifestTests(unittest.TestCase):
    def test_deterministic_manifest(self):
        envelope, manifest, anchor, signature = sample()
        self.assertEqual(manifest, make_manifest(dict(reversed(list(envelope.items()))),
                                                storage_reference="fixture://synthetic/123"))
        self.assertEqual(signature, authenticate(manifest, secret=KEY))

    def test_valid_hmac_and_external_anchor(self):
        envelope, manifest, anchor, signature = sample()
        self.assertEqual(verify(manifest, signature, secret=KEY, external_anchor=anchor, envelope=envelope),
                         (True, "VERIFIED_OFFLINE_MANIFEST"))

    def test_modified_evidence_or_manifest_rejected(self):
        envelope, manifest, anchor, signature = sample()
        changed = dict(manifest, gameId="999")
        self.assertFalse(verify(changed, signature, secret=KEY, external_anchor=anchor)[0])
        changed_envelope = dict(envelope, rawResponse=envelope["rawResponse"]+" ")
        self.assertFalse(verify(manifest, signature, secret=KEY, external_anchor=anchor, envelope=changed_envelope)[0])

    def test_wrong_key_rejected(self):
        envelope, manifest, anchor, signature = sample()
        self.assertEqual(verify(manifest, signature, secret=OTHER_KEY, external_anchor=anchor),
                         (False, "SIGNATURE_MISMATCH"))

    def test_missing_external_trust_anchor_rejected(self):
        envelope, manifest, anchor, signature = sample()
        self.assertEqual(verify(manifest, signature, secret=KEY, envelope=envelope),
                         (False, "MISSING_EXTERNAL_TRUST_ANCHOR"))

if __name__ == "__main__":
    unittest.main()
