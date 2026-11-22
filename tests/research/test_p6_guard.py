"""P6 synthetic revocation-anchor regression checks."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.p6_guard import RevocationAnchoredGate,tombstone_digest
from research.ab_snapshot.trust_state import TrustStateError,SQLiteReplayRegistry
from research.ab_snapshot.durable_policy import DurablePolicyGate
import test_trusted_contract as baseline

class P6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'policy.db')
        self.root=Ed25519PrivateKey.generate()
        self.base=baseline.TrustedContractTests();self.base.setUp()
        self.m,self.s=self.manifest(1)
        self.anchor,self.anchor_sig=self.anchor_for(self.m,self.s,1,[])
    def manifest(self,version,revoked=None):
        k=self.base.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        b=canonical({'version':version,'keys':[{'id':'test-key','publicKeyHex':k,'purpose':'capture','activeFrom':'2026-01-01T00:00:00.000Z','activeUntil':'2027-01-01T00:00:00.000Z','revokedAt':revoked}]})
        return b,self.root.sign(b)
    def anchor_for(self,m,s,v,ids):
        b=canonical({'version':v,'digest':hashlib.sha256(m+s).hexdigest(),'revocationsSha256':tombstone_digest(ids)})
        return b,self.root.sign(b)
    def gate(self,m=None,s=None,anchor=None,sig=None):
        return RevocationAnchoredGate(self.root.public_key(),self.path,m or self.m,s or self.s,anchor or self.anchor,sig or self.anchor_sig)
    def verify(self,g):
        b=self.base
        return g.verify(1,b.wrap(),b.payload,b.schedule,SQLiteReplayRegistry(os.path.join(self.tmp.name,'replay.db')),b.context)
    def test_initial_anchor_accepts(self):self.assertTrue(self.verify(self.gate())['passed'])
    def test_bad_anchor_signature_rejected(self):
        with self.assertRaisesRegex(TrustStateError,'E601_ANCHOR_INVALID'):self.gate(sig=b'0'*64)
    def test_deleted_tombstone_rejected(self):
        m,s=self.manifest(1,'2026-10-01T00:00:00.000Z')
        a,sign=self.anchor_for(m,s,1,['test-key'])
        g=self.gate(m,s,a,sign)
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('DELETE FROM revoked_ids')
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
    def test_restored_tombstone_accepted(self):
        m,s=self.manifest(1,'2026-10-01T00:00:00.000Z')
        a,sign=self.anchor_for(m,s,1,['test-key']);g=self.gate(m,s,a,sign)
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('DELETE FROM revoked_ids')
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('INSERT INTO revoked_ids VALUES (?)',('test-key',))
        self.assertEqual(self.verify(g)['errors'],['E203_KEY_REVOKED'])
    def test_added_tombstone_rejected(self):
        g=self.gate()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('INSERT INTO revoked_ids VALUES (?)',('extra',))
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
    def test_stale_instance_rejected_after_other_update(self):
        g=self.gate();m2,s2=self.manifest(2)
        DurablePolicyGate(self.root.public_key(),self.path,m2,s2)
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
    def test_missing_policy_row_rejected(self):
        g=self.gate()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('DELETE FROM policy')
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
    def test_tampered_anchor_digest_rejected(self):
        bad=canonical({'version':1,'digest':'0'*64,'revocationsSha256':tombstone_digest([])})
        with self.assertRaisesRegex(TrustStateError,'E502_ANCHOR_MISMATCH'):self.gate(anchor=bad,sig=self.root.sign(bad))
    def test_independent_process_updates_one_wins(self):
        import multiprocessing
        # Independent process connection writers must serialize through SQLite.
        g=self.gate();m2,s2=self.manifest(2)
        from concurrent.futures import ThreadPoolExecutor
        def writer(_):
            try:
                DurablePolicyGate(self.root.public_key(),self.path,m2,s2)
                return 'ok'
            except TrustStateError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(writer,range(2)))
        self.assertEqual(outcomes.count('ok'),1)
        self.assertEqual(outcomes.count('E304_POLICY_ROLLBACK'),1)
        self.assertEqual(self.verify(g)['errors'],['E602_REVOCATION_MISMATCH'])
