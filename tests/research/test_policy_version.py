"""Synthetic-only authenticated policy version and revocation-boundary tests."""
import concurrent.futures
import hashlib
import os
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.policy_version import VersionedPolicyGate
from research.ab_snapshot.trust_state import SQLiteReplayRegistry, TrustStateError
import test_trusted_contract as baseline

class PolicyVersionTests(unittest.TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.base = baseline.TrustedContractTests(); self.base.setUp()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.registry = SQLiteReplayRegistry(os.path.join(self.tmp.name,'replay.sqlite'))
        self.gate = VersionedPolicyGate(self.root.public_key(), *self.manifest(1))
    def manifest(self, version, revoked=None):
        key = self.base.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        obj = {'version':version,'keys':[{'id':'test-key','publicKeyHex':key,'purpose':'capture',
             'activeFrom':'2026-01-01T00:00:00.000Z','activeUntil':'2027-01-01T00:00:00.000Z',
             'revokedAt':revoked}]}
        b=canonical(obj); return b,self.root.sign(b)
    def verify(self,version=1):
        b=self.base
        return self.gate.verify(version,b.wrap(),b.payload,b.schedule,self.registry,b.context)
    def test_valid_signed_policy(self): self.assertEqual(self.gate.version,1)
    def test_valid_capture(self): self.assertTrue(self.verify()['passed'])
    def test_unsigned_policy_rejected(self):
        with self.assertRaises(TrustStateError) as cm: self.gate.update(*self.manifest(2)[:1],b'0'*64)
        self.assertEqual(cm.exception.code,'E303_POLICY_SIGNATURE_INVALID')
    def test_stale_version_rejected_without_replay_consumption(self):
        self.gate.update(*self.manifest(2))
        self.assertEqual(self.verify(1)['errors'],['E305_STALE_POLICY'])
        self.assertTrue(self.verify(2)['passed'])
    def test_rollback_rejected(self):
        with self.assertRaises(TrustStateError) as cm: self.gate.update(*self.manifest(1))
        self.assertEqual(cm.exception.code,'E304_POLICY_ROLLBACK')
    def test_revocation_rejects(self):
        self.gate.update(*self.manifest(2,'2026-10-01T00:00:00.000Z'))
        self.assertEqual(self.verify(2)['errors'],['E203_KEY_REVOKED'])
    def test_revocation_does_not_consume_capture(self):
        self.gate.update(*self.manifest(2,'2026-10-01T00:00:00.000Z'))
        self.assertEqual(self.verify(2)['errors'],['E203_KEY_REVOKED'])
        with self.assertRaises(TrustStateError) as cm: self.gate.update(*self.manifest(3))
        self.assertEqual(cm.exception.code,'E306_REVOKED_KEY_REUSE')
        self.assertTrue(self.registry.register('capture_0001','0'*64))
    def test_wrong_root_signature_rejected(self):
        manifest,_=self.manifest(2)
        with self.assertRaises(TrustStateError): self.gate.update(manifest,Ed25519PrivateKey.generate().sign(manifest))
    def test_malformed_manifest_rejected(self):
        with self.assertRaises(TrustStateError): self.gate.update(b'{}',self.root.sign(b'{}'))
    def test_concurrent_update_and_capture_serialized(self):
        # Either capture commits before revocation, or revocation rejects capture;
        # no stale-version acceptance after an update completes.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.verify,1)
            b=pool.submit(self.gate.update,*self.manifest(2,'2026-10-01T00:00:00.000Z'))
            result=a.result();b.result()
        self.assertIn(result['errors'],([],['E305_STALE_POLICY']))
        self.assertEqual(self.verify(2)['errors'],['E203_KEY_REVOKED'])
    def test_policy_version_required(self):
        self.assertEqual(self.verify(None)['errors'],['E305_STALE_POLICY'])
    def test_policy_update_invalid_does_not_replace(self):
        manifest,_=self.manifest(2)
        with self.assertRaises(TrustStateError): self.gate.update(manifest,b'0'*64)
        self.assertEqual(self.gate.version,1)
