import unittest
import test_trusted_contract as baseline
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.trusted_contract import verify

class P0Audit(unittest.TestCase):
    setUp=baseline.TrustedContractTests.setUp
    wrap=baseline.TrustedContractTests.wrap
    check=baseline.TrustedContractTests.check
    def test_p0_malformed_keys(self):
        for keys in ([], None, 4, {'test-key':None}, {'test-key':b'abc'}, {'test-key':object()}):
            with self.subTest(keys=repr(keys)):
                self.assertFalse(verify(self.wrap(),self.payload,self.schedule,keys,set(),self.context)['passed'])
    def test_p0_malformed_replay(self):
        for seen in (None,[],{},'capture_0001',123,{'capture_0001':1}):
            with self.subTest(seen=repr(seen)):
                self.assertEqual(verify(self.wrap(),self.payload,self.schedule,self.keys,seen,self.context)['errors'],['E101_INPUT_INVALID'])
    def test_p0_context_substitution(self):
        for field,new in [('season','2025'),('week','9'),('freezeDate','2026-11-04'),('sourceIdentity','synthetic://other')]:
            with self.subTest(field=field):
                self.assertEqual(self.check(context={**self.context,field:new})['errors'],['E105_CONTEXT_MISMATCH'])
    def test_p0_malformed_context(self):
        for ctx in (None, [], {}, {'week':'8'}):
            self.assertFalse(verify(self.wrap(),self.payload,self.schedule,self.keys,set(),ctx)['passed'])
    def test_p0_signature_identity(self):
        e={**self.e,'signerKeyId':'other-key'}
        self.assertEqual(self.check(env=self.wrap(e))['errors'],['E102_SIGNATURE_INVALID'])
    def test_p0_oversize_exact(self):
        self.assertEqual(self.check(env=b'x'*1048577)['errors'],['E101_INPUT_INVALID'])
    def test_p0_noncanonical(self):
        self.assertEqual(self.check(env=b' '+self.wrap())['errors'],['E101_INPUT_INVALID'])
    def test_p0_timestamp_before_cutoff(self):
        e={**self.e,'captureCompletedUtc':'2026-10-28T14:59:59.998Z'}
        self.assertTrue(self.check(env=self.wrap(e))['passed'])
    def test_p0_timestamp_after_cutoff(self):
        e={**self.e,'trustedTimestampUtc':'2026-10-28T15:00:00.001Z'}
        self.assertEqual(self.check(env=self.wrap(e))['errors'],['E104_CUTOFF_INVALID'])
    def test_p0_invalid_timestamp(self):
        for timestamp in ('2026-10-28T15:00:60.000Z','2026-02-30T15:00:00.000Z','2026-10-28T15:00:00Z'):
            e={**self.e,'trustedTimestampUtc':timestamp}
            self.assertEqual(self.check(env=self.wrap(e))['errors'],['E101_INPUT_INVALID'])
    def test_p0_error_determinism(self):
        e={**self.e,'trustedTimestampUtc':'bad'};env=self.wrap(e)
        self.assertEqual([self.check(env=env) for _ in range(10)],[self.check(env=env)]*10)
    def test_p0_replay_is_caller_owned(self):
        seen=set();self.assertTrue(self.check(seen=seen)['passed']);self.assertEqual(seen,set())
    def test_p0_malformed_signer_id_rejected(self):
        e={**self.e,'signerKeyId':''}
        self.assertEqual(self.check(env=self.wrap(e),keys={'':self.private.public_key()})['errors'],['E101_INPUT_INVALID'])
