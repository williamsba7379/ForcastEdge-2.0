"""Research-only integration and transaction ordering tests."""
import concurrent.futures
import os
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.trusted_integration import verify_and_register
from research.ab_snapshot.trust_state import KeyRecord, SyntheticTrustStore, SQLiteReplayRegistry
from research.ab_snapshot.validator import canonical
import test_trusted_contract as baseline

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        base=baseline.TrustedContractTests();base.setUp();self.base=base
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=os.path.join(self.tmp.name,'captures.sqlite')
        self.registry=SQLiteReplayRegistry(self.path)
        self.store=SyntheticTrustStore([KeyRecord('test-key',base.private.public_key(),'capture','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z')])
    def verify(self,env=None,payload=None,schedule=None,store=None,registry=None,context=None):
        b=self.base
        return verify_and_register(b.wrap() if env is None else env,b.payload if payload is None else payload,b.schedule if schedule is None else schedule,self.store if store is None else store,self.registry if registry is None else registry,b.context if context is None else context)
    def assert_reject_without_consuming(self,code,**kwargs):
        self.assertEqual(self.verify(**kwargs)['errors'],[code]);self.assertTrue(self.verify()['passed'])
    def test_accept_then_replay(self):
        self.assertTrue(self.verify()['passed']);self.assertEqual(self.verify()['errors'],['E206_REPLAY'])
    def test_signature_before_insert(self):
        e=dict(self.base.e);e['payloadSha256']='0'*64
        # Re-signing makes signature valid, but content mismatch must not register.
        self.assert_reject_without_consuming('E103_CONTENT_MISMATCH',env=self.base.wrap(e))
    def test_bad_signature_no_insert(self):
        attacker=Ed25519PrivateKey.generate()
        self.assert_reject_without_consuming('E102_SIGNATURE_INVALID',env=self.base.wrap(private=attacker))
    def test_revoked_key_no_insert(self):
        revoked=SyntheticTrustStore([KeyRecord('test-key',self.base.private.public_key(),'capture','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z','2026-10-01T00:00:00.000Z')])
        self.assert_reject_without_consuming('E203_KEY_REVOKED',store=revoked)
    def test_wrong_purpose_no_insert(self):
        wrong=SyntheticTrustStore([KeyRecord('test-key',self.base.private.public_key(),'schedule','2026-01-01T00:00:00.000Z','2027-01-01T00:00:00.000Z')])
        self.assert_reject_without_consuming('E202_KEY_UNAUTHORIZED',store=wrong)
    def test_late_timestamp_no_insert(self):
        e={**self.base.e,'trustedTimestampUtc':'2026-10-28T15:00:00.001Z'}
        self.assert_reject_without_consuming('E104_CUTOFF_INVALID',env=self.base.wrap(e))
    def test_payload_tamper_no_insert(self):
        self.assert_reject_without_consuming('E103_CONTENT_MISMATCH',payload=b'tampered')
    def test_schedule_tamper_no_insert(self):
        self.assert_reject_without_consuming('E103_CONTENT_MISMATCH',schedule=b'tampered')
    def test_context_tamper_no_insert(self):
        self.assert_reject_without_consuming('E105_CONTEXT_MISMATCH',context={**self.base.context,'week':'9'})
    def test_malformed_envelope_no_insert(self):
        self.assert_reject_without_consuming('E101_INPUT_INVALID',env=b'{}')
    def test_storage_failure(self):
        os.unlink(self.path);os.mkdir(self.path)
        self.assertEqual(self.verify()['errors'],['E204_STORAGE_INVALID'])
    def test_restart_replay(self):
        self.assertTrue(self.verify()['passed']);other=SQLiteReplayRegistry(self.path)
        self.assertEqual(self.verify(registry=other)['errors'],['E206_REPLAY'])
    def test_concurrent_one_winner(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(lambda _:self.verify(),range(16)))
        self.assertEqual(sum(x['passed'] for x in outcomes),1)
        self.assertEqual(sum(x['errors']==['E206_REPLAY'] for x in outcomes),15)
    def test_invalid_store_type(self):
        self.assert_reject_without_consuming('E101_INPUT_INVALID',store={})
    def test_invalid_registry_type(self):
        self.assert_reject_without_consuming('E101_INPUT_INVALID',registry={})
    def test_deterministic_replay(self):
        self.assertTrue(self.verify()['passed']);self.assertEqual([self.verify() for _ in range(5)],[self.verify()]*5)
