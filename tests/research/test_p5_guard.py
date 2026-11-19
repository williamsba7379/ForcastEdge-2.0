"""P5 synthetic-only full-file rollback and stale-policy rejection tests."""
import hashlib
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.p5_guard import AnchoredPolicyGate
from research.ab_snapshot.trust_state import TrustStateError, SQLiteReplayRegistry
import test_trusted_contract as baseline

class P5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'policy.db')
        self.root=Ed25519PrivateKey.generate()
        self.base=baseline.TrustedContractTests();self.base.setUp()
        self.m1,self.s1=self.manifest(1)
        self.anchor=self.make_anchor(self.m1,self.s1,1)
    def manifest(self,v,revoked=None):
        k=self.base.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        m=canonical({'version':v,'keys':[{'id':'test-key','publicKeyHex':k,'purpose':'capture','activeFrom':'2026-01-01T00:00:00.000Z','activeUntil':'2027-01-01T00:00:00.000Z','revokedAt':revoked}]})
        return m,self.root.sign(m)
    def make_anchor(self,m,s,v):return {'version':v,'digest':hashlib.sha256(m+s).hexdigest()}
    def gate(self,m=None,s=None,anchor=None):
        return AnchoredPolicyGate(self.root.public_key(),self.path,self.m1 if m is None else m,self.s1 if s is None else s,self.anchor if anchor is None else anchor)
    def test_initial_anchor(self):self.assertEqual(self.gate().version,1)
    def test_reopen_same_anchor(self):self.gate();self.assertEqual(self.gate().version,1)
    def test_wrong_digest_rejected(self):
        with self.assertRaisesRegex(TrustStateError,'E502_ANCHOR_MISMATCH'):self.gate(anchor={'version':1,'digest':'0'*64})
    def test_wrong_version_rejected(self):
        with self.assertRaisesRegex(TrustStateError,'E502_ANCHOR_MISMATCH'):self.gate(anchor={'version':2,'digest':self.anchor['digest']})
    def test_invalid_anchor(self):
        with self.assertRaisesRegex(TrustStateError,'E501_ANCHOR_INVALID'):self.gate(anchor={'version':0,'digest':'0'*64})
    def test_full_file_rollback_detected(self):
        g=self.gate();backup=os.path.join(self.tmp.name,'backup.db');shutil.copyfile(self.path,backup)
        m2,s2=self.manifest(2);g.update(m2,s2)
        anchor2=self.make_anchor(m2,s2,2)
        shutil.copyfile(backup,self.path)
        with self.assertRaisesRegex(TrustStateError,'E502_ANCHOR_MISMATCH'):self.gate(m2,s2,anchor2)
    def test_deleted_tombstone_detected_only_when_manifest_changes(self):
        # Tombstones are not part of the anchor. A deletion alone is NOT detected.
        g=self.gate();m2,s2=self.manifest(2,'2026-10-01T00:00:00.000Z');g.update(m2,s2)
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('DELETE FROM revoked_ids')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revoked_ids').fetchone()[0],0)
    def test_cross_process_stale_gate_fails_closed(self):
        g=self.gate();m2,s2=self.manifest(2);g.update(m2,s2)
        b=self.base;registry=SQLiteReplayRegistry(os.path.join(self.tmp.name,'replay.db'))
        self.assertEqual(g.verify(1,b.wrap(),b.payload,b.schedule,registry,b.context)['errors'],['E502_ANCHOR_MISMATCH'])
    def test_missing_policy_row_fails_closed(self):
        g=self.gate()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('DELETE FROM policy')
        b=self.base;registry=SQLiteReplayRegistry(os.path.join(self.tmp.name,'replay.db'))
        self.assertEqual(g.verify(1,b.wrap(),b.payload,b.schedule,registry,b.context)['errors'],['E502_ANCHOR_MISMATCH'])
