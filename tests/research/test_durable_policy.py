"""Synthetic P4 durable policy checks."""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.durable_policy import DurablePolicyGate
from research.ab_snapshot.trust_state import TrustStateError

class DurableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=os.path.join(self.temp.name,'policy.sqlite')
        self.root=Ed25519PrivateKey.generate();self.signer=Ed25519PrivateKey.generate()
    def manifest(self,v,revoked=None,include=True):
        keys=[]
        if include:
            keys=[{'id':'key1','publicKeyHex':self.signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),'purpose':'capture','activeFrom':'2026-01-01T00:00:00.000Z','activeUntil':'2027-01-01T00:00:00.000Z','revokedAt':revoked}]
        b=canonical({'version':v,'keys':keys});return b,self.root.sign(b)
    def gate(self,v=1,revoked=None):return DurablePolicyGate(self.root.public_key(),self.path,*self.manifest(v,revoked))
    def test_initial_persist(self):self.assertEqual(self.gate().version,1)
    def test_restart_same_policy(self):self.gate();self.assertEqual(self.gate().version,1)
    def test_restart_rollback_rejected(self):
        g=self.gate();g.update(*self.manifest(2))
        with self.assertRaisesRegex(TrustStateError,'E304_POLICY_ROLLBACK'):self.gate()
    def test_restart_newer_policy(self):
        self.gate();self.assertEqual(self.gate(2).version,2)
    def test_revocation_persists(self):
        g=self.gate();g.update(*self.manifest(2,'2026-10-01T00:00:00.000Z'))
        with self.assertRaisesRegex(TrustStateError,'E306_REVOKED_KEY_REUSE'):
            DurablePolicyGate(self.root.public_key(),self.path,*self.manifest(3))
    def test_tampered_digest_rejected(self):
        self.gate()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute("UPDATE policy SET digest='bad'")
        with self.assertRaisesRegex(TrustStateError,'E402_STATE_TAMPERED'):self.gate()
    def test_tampered_version_rejected(self):
        self.gate()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('UPDATE policy SET version=99')
        with self.assertRaisesRegex(TrustStateError,'E402_STATE_TAMPERED'):self.gate()
    def test_failed_update_does_not_change_memory(self):
        g=self.gate()
        with self.assertRaisesRegex(TrustStateError,'E304_POLICY_ROLLBACK'):g.update(*self.manifest(1))
        self.assertEqual(g.version,1)
    def test_concurrent_update_only_one_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        g=self.gate()
        def run(_):
            try:g.update(*self.manifest(2));return 'ok'
            except TrustStateError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(run,range(2)))
        self.assertCountEqual(r,['ok','E304_POLICY_ROLLBACK'])
    def test_storage_failure_closed(self):
        with self.assertRaisesRegex(TrustStateError,'E401_STATE_INVALID'):
            DurablePolicyGate(self.root.public_key(),os.path.join(self.temp.name,'missing','x.db'),*self.manifest(1))

    def test_revocation_tombstone_survives_key_removal(self):
        g=self.gate();g.update(*self.manifest(2,'2026-10-01T00:00:00.000Z'))
        newkey=Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        obj={'version':3,'keys':[{'id':'replacement','publicKeyHex':newkey,'purpose':'capture','activeFrom':'2026-01-01T00:00:00.000Z','activeUntil':'2027-01-01T00:00:00.000Z','revokedAt':None}]}
        m=canonical(obj);g.update(m,self.root.sign(m))
        with self.assertRaisesRegex(TrustStateError,'E306_REVOKED_KEY_REUSE'):
            g.update(*self.manifest(4))
