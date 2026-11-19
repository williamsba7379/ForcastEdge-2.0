"""Synthetic-only P1 trust policy and transactional replay tests."""
import concurrent.futures
import hashlib
import os
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.trust_state import KeyRecord, SyntheticTrustStore, SQLiteReplayRegistry, TrustStateError

START='2026-01-01T00:00:00.000Z'
SWITCH='2026-11-01T00:00:00.000Z'
END='2027-01-01T00:00:00.000Z'
DIGEST=hashlib.sha256(b'synthetic').hexdigest()

class TrustPolicyTests(unittest.TestCase):
    def setUp(self):
        self.k1=Ed25519PrivateKey.generate().public_key()
        self.k2=Ed25519PrivateKey.generate().public_key()
    def record(self, key_id='key-one', purpose='capture', start=START, end=END, revoked=None, key=None):
        return KeyRecord(key_id, self.k1 if key is None else key, purpose, start, end, revoked)
    def test_authorized_key(self):
        self.assertIs(SyntheticTrustStore([self.record()]).authorize('key-one','capture',SWITCH),self.k1)
    def test_rotation_old_before_boundary(self):
        store=SyntheticTrustStore([self.record(end=SWITCH),self.record('key-two',start=SWITCH,key=self.k2)])
        self.assertIs(store.authorize('key-one','capture',START),self.k1)
    def test_rotation_new_at_boundary(self):
        store=SyntheticTrustStore([self.record(end=SWITCH),self.record('key-two',start=SWITCH,key=self.k2)])
        self.assertIs(store.authorize('key-two','capture',SWITCH),self.k2)
    def test_rotation_old_at_boundary_rejected(self):
        store=SyntheticTrustStore([self.record(end=SWITCH),self.record('key-two',start=SWITCH,key=self.k2)])
        with self.assertRaises(TrustStateError) as cm: store.authorize('key-one','capture',SWITCH)
        self.assertEqual(cm.exception.code,'E202_KEY_UNAUTHORIZED')
    def test_revoked_key_rejected(self):
        store=SyntheticTrustStore([self.record(revoked=SWITCH)])
        with self.assertRaises(TrustStateError) as cm: store.authorize('key-one','capture',START)
        self.assertEqual(cm.exception.code,'E203_KEY_REVOKED')
    def test_wrong_purpose(self):
        with self.assertRaises(TrustStateError) as cm: SyntheticTrustStore([self.record(purpose='schedule')]).authorize('key-one','capture',SWITCH)
        self.assertEqual(cm.exception.code,'E202_KEY_UNAUTHORIZED')
    def test_unknown_key(self):
        with self.assertRaises(TrustStateError) as cm: SyntheticTrustStore([self.record()]).authorize('missing','capture',SWITCH)
        self.assertEqual(cm.exception.code,'E202_KEY_UNAUTHORIZED')
    def test_duplicate_key_id_rejected(self):
        with self.assertRaises(TrustStateError): SyntheticTrustStore([self.record(),self.record()])
    def test_invalid_key_type_rejected(self):
        with self.assertRaises(TrustStateError): SyntheticTrustStore([self.record(key=b'bad')])
    def test_invalid_window_rejected(self):
        with self.assertRaises(TrustStateError): SyntheticTrustStore([self.record(start=END,end=START)])
    def test_invalid_timestamp_rejected(self):
        with self.assertRaises(TrustStateError): SyntheticTrustStore([self.record()]).authorize('key-one','capture','bad')
    def test_invalid_purpose_rejected(self):
        with self.assertRaises(TrustStateError): SyntheticTrustStore([self.record(purpose='admin')])

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'replay.sqlite')
        self.registry=SQLiteReplayRegistry(self.path)
    def test_register(self): self.assertTrue(self.registry.register('capture_001',DIGEST))
    def test_replay_same_digest_rejected(self):
        self.registry.register('capture_001',DIGEST)
        with self.assertRaises(TrustStateError) as cm: self.registry.register('capture_001',DIGEST)
        self.assertEqual(cm.exception.code,'E206_REPLAY')
    def test_replay_changed_digest_rejected(self):
        self.registry.register('capture_001',DIGEST)
        with self.assertRaises(TrustStateError): self.registry.register('capture_001','0'*64)
    def test_restart_persists(self):
        self.registry.register('capture_001',DIGEST)
        restarted=SQLiteReplayRegistry(self.path)
        with self.assertRaises(TrustStateError) as cm: restarted.register('capture_001',DIGEST)
        self.assertEqual(cm.exception.code,'E206_REPLAY')
    def test_distinct_captures(self):
        self.assertTrue(self.registry.register('capture_001',DIGEST))
        self.assertTrue(self.registry.register('capture_002',DIGEST))
    def test_concurrent_same_id_one_winner(self):
        def attempt(_):
            try: self.registry.register('capture_001',DIGEST);return 'accepted'
            except TrustStateError as exc: return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: outcomes=list(pool.map(attempt,range(16)))
        self.assertEqual(outcomes.count('accepted'),1)
        self.assertEqual(outcomes.count('E206_REPLAY'),15)
    def test_invalid_id(self):
        with self.assertRaises(TrustStateError) as cm: self.registry.register('bad',DIGEST)
        self.assertEqual(cm.exception.code,'E205_CAPTURE_INVALID')
    def test_invalid_digest(self):
        with self.assertRaises(TrustStateError): self.registry.register('capture_001','bad')
    def test_memory_database_rejected(self):
        with self.assertRaises(TrustStateError): SQLiteReplayRegistry(':memory:')
    def test_storage_missing_directory(self):
        with self.assertRaises(TrustStateError) as cm: SQLiteReplayRegistry(os.path.join(self.tmp.name,'missing','db.sqlite'))
        self.assertEqual(cm.exception.code,'E204_STORAGE_INVALID')
    def test_storage_failure_after_initialization(self):
        os.unlink(self.path)
        os.mkdir(self.path)
        with self.assertRaises(TrustStateError) as cm: self.registry.register('capture_001',DIGEST)
        self.assertEqual(cm.exception.code,'E204_STORAGE_INVALID')
    def test_no_partial_acceptance_after_failure(self):
        self.registry.register('capture_001',DIGEST)
        with self.assertRaises(TrustStateError): self.registry.register('capture_001',DIGEST)
        self.assertTrue(self.registry.register('capture_002',DIGEST))
