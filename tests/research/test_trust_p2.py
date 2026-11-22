"""P2 synthetic-only crash consistency and immutable policy regression tests."""
import os
import sqlite3
from contextlib import closing
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.trust_state import SyntheticTrustStore,KeyRecord,SQLiteReplayRegistry,TrustStateError
from research.ab_snapshot.trusted_integration import verify_and_register
import test_trusted_contract as baseline

class P2TrustTests(unittest.TestCase):
    def setUp(self):
        self.base=baseline.TrustedContractTests();self.base.setUp()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'state.sqlite')
        self.registry=SQLiteReplayRegistry(self.path)
        self.record=KeyRecord('test-key',self.base.private.public_key(),'capture','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z')
        self.store=SyntheticTrustStore([self.record])
    def verify(self,registry=None):
        b=self.base
        return verify_and_register(b.wrap(),b.payload,b.schedule,self.store,registry or self.registry,b.context)
    def test_policy_dictionary_cannot_mutate(self):
        with self.assertRaises(TypeError):
            self.store._keys['test-key']=KeyRecord('test-key',self.base.private.public_key(),'capture','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z','2026-10-01T00:00:00.000Z')
    def test_policy_source_list_mutation_does_not_change_snapshot(self):
        records=[self.record];store=SyntheticTrustStore(records);records.clear()
        self.assertIs(store.authorize('test-key','capture','2026-10-28T15:00:00.000Z'),self.record.public_key)
    def test_replay_after_reopen(self):
        self.assertTrue(self.verify()['passed'])
        self.assertEqual(self.verify(SQLiteReplayRegistry(self.path))['errors'],['E206_REPLAY'])
    def test_explicit_rollback_does_not_consume_id(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO captures VALUES (?,?)',('rollback_01','0'*64))
            db.rollback()
        self.assertTrue(self.registry.register('rollback_01','0'*64))
    def test_failed_insert_does_not_remove_existing_record(self):
        self.registry.register('capture_001','0'*64)
        with self.assertRaises(TrustStateError): self.registry.register('capture_001','1'*64)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT digest FROM captures WHERE capture_id=?',('capture_001',)).fetchone()[0],'0'*64)
    def test_revoked_snapshot_rejects_before_insert(self):
        revoked=SyntheticTrustStore([KeyRecord('test-key',self.base.private.public_key(),'capture','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z','2026-10-01T00:00:00.000Z')])
        b=self.base
        self.assertEqual(verify_and_register(b.wrap(),b.payload,b.schedule,revoked,self.registry,b.context)['errors'],['E203_KEY_REVOKED'])
        self.assertTrue(self.verify()['passed'])
