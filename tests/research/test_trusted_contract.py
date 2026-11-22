"""Synthetic-only contract security tests. Never uses a live timestamp authority."""
import copy
import hashlib
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from research.ab_snapshot.validator import canonical
from research.ab_snapshot.trusted_contract import verify

class TrustedContractTests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.keys={'test-key':self.private.public_key()}
        self.context={'season':'2026','week':'8','freezeDate':'2026-10-28','sourceIdentity':'synthetic://scores'}
        self.payload=b'synthetic-payload';self.schedule=b'synthetic-schedule'
        self.e={'contractVersion':'1.0-SYNTHETIC','captureId':'capture_0001',**self.context,
                'payloadSha256':hashlib.sha256(self.payload).hexdigest(),
                'scheduleSha256':hashlib.sha256(self.schedule).hexdigest(),
                'captureCompletedUtc':'2026-10-28T14:59:59.999Z',
                'trustedTimestampUtc':'2026-10-28T15:00:00.000Z',
                'signerKeyId':'test-key','signatureAlgorithm':'Ed25519'}
    def wrap(self,e=None,private=None):
        e=self.e if e is None else e
        signature=(private or self.private).sign(canonical(e)).hex()
        return canonical({'evidence':e,'signature':signature})
    def check(self,env=None,payload=None,schedule=None,keys=None,seen=None,context=None):
        return verify(self.wrap() if env is None else env,self.payload if payload is None else payload,
                      self.schedule if schedule is None else schedule,self.keys if keys is None else keys,
                      set() if seen is None else seen,self.context if context is None else context)
    def assertCode(self,code,**kwargs):
        self.assertEqual(self.check(**kwargs)['errors'],[code])
    def test_valid(self): self.assertTrue(self.check()['passed'])
    def test_never_historical(self): self.assertFalse(self.check()['historicalCertification'])
    def test_payload_tamper(self): self.assertCode('E103_CONTENT_MISMATCH',payload=b'tampered')
    def test_schedule_tamper(self): self.assertCode('E103_CONTENT_MISMATCH',schedule=b'tampered')
    def test_wrong_signing_key(self): self.assertCode('E102_SIGNATURE_INVALID',keys={'test-key':Ed25519PrivateKey.generate().public_key()})
    def test_missing_key(self): self.assertCode('E102_SIGNATURE_INVALID',keys={})
    def test_signature_tamper(self):
        env=self.wrap();d=__import__('json').loads(env);d['signature']='0'*128
        self.assertCode('E102_SIGNATURE_INVALID',env=canonical(d))
    def test_replay(self): self.assertCode('E106_REPLAY',seen={'capture_0001'})
    def test_cross_week(self): self.assertCode('E105_CONTEXT_MISMATCH',context={**self.context,'week':'9'})
    def test_cross_source(self): self.assertCode('E105_CONTEXT_MISMATCH',context={**self.context,'sourceIdentity':'synthetic://other'})
    def test_late_timestamp(self):
        e={**self.e,'trustedTimestampUtc':'2026-10-28T15:00:00.001Z'}
        self.assertCode('E104_CUTOFF_INVALID',env=self.wrap(e))
    def test_late_completion(self):
        e={**self.e,'captureCompletedUtc':'2026-10-28T15:00:00.001Z'}
        self.assertCode('E104_CUTOFF_INVALID',env=self.wrap(e))
    def test_completion_after_timestamp(self):
        e={**self.e,'captureCompletedUtc':'2026-10-28T15:00:00.001Z'}
        self.assertCode('E104_CUTOFF_INVALID',env=self.wrap(e))
    def test_exact_cutoff(self): self.assertTrue(self.check()['passed'])
    def test_malformed_envelope(self):
        for env in (b'{}',b'[]',b'not-json',b'{"x":1,"x":2}',b'\xff'):
            with self.subTest(env=env): self.assertCode('E101_INPUT_INVALID',env=env)
    def test_missing_field(self):
        e=dict(self.e);del e['sourceIdentity']
        self.assertCode('E101_INPUT_INVALID',env=self.wrap(e))
    def test_extra_field(self):
        e={**self.e,'unknown':'x'}
        self.assertCode('E101_INPUT_INVALID',env=self.wrap(e))
    def test_wrong_algorithm(self):
        e={**self.e,'signatureAlgorithm':'HMAC'}
        self.assertCode('E101_INPUT_INVALID',env=self.wrap(e))
    def test_untrusted_self_reseal(self):
        attacker=Ed25519PrivateKey.generate();e={**self.e,'payloadSha256':hashlib.sha256(b'forged').hexdigest()}
        self.assertCode('E102_SIGNATURE_INVALID',env=self.wrap(e,attacker),payload=b'forged')
    def test_deterministic_errors(self):
        e={**self.e,'captureCompletedUtc':'bad'};env=self.wrap(e)
        self.assertEqual([self.check(env=env) for _ in range(5)],[self.check(env=env)]*5)
        self.assertCode('E101_INPUT_INVALID',env=env)
    def test_oversized_envelope(self): self.assertCode('E101_INPUT_INVALID',env=b'x'*1_048_577)
    def test_noncanonical_envelope(self): self.assertCode('E101_INPUT_INVALID',env=self.wrap()+b' ')
    def test_wrong_capture_id(self):
        e={**self.e,'captureId':'!'}
        self.assertCode('E101_INPUT_INVALID',env=self.wrap(e))
    def test_repeated_signature_determinism(self): self.assertEqual(self.wrap(),self.wrap())
