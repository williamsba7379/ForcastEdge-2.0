"""Synthetic-only timestamp and binding adversarial regression tests."""
import sys
import unittest
from datetime import timedelta
sys.path.insert(0, __file__.rsplit('/',1)[0])
from test_ab_snapshot_validator import fixture, run
from research.ab_snapshot.validator import canonical, digest, validate, cutoff


def attest(p, s):
    raw=canonical(p)
    seal_time=p['cutoffUtc']
    return {'capturePayloadSha256':digest(raw),'scheduleSha256':digest(s),
            'kind':'SYNTHETIC_TEST_ONLY','proof':'SYNTHETIC_VALID',
            'timingClassification':'SYNTHETIC_VERIFIED',
            'syntheticSeal':{'sealedAtUtc':seal_time,'bindingSha256':digest(canonical({
                'capturePayloadSha256':digest(raw),'scheduleSha256':digest(s),
                'sealedAtUtc':seal_time,'kind':'SYNTHETIC_TEST_ONLY'}))}}

class TimestampBindingAudit(unittest.TestCase):
    def test_payload_digest_tamper(self):
        p,r,s=fixture();a=attest(p,s);a['capturePayloadSha256']='0'*64
        self.assertIn('E015_PAYLOAD_HASH_MISMATCH',validate(canonical(p),r,s,a)['errors'])
    def test_schedule_digest_tamper(self):
        p,r,s=fixture();a=attest(p,s);a['scheduleSha256']='0'*64
        self.assertIn('E014_SCHEDULE_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_payload_modified_after_sealing(self):
        p,r,s=fixture();a=attest(p,s);p['extra']='modified'
        self.assertIn('E015_PAYLOAD_HASH_MISMATCH',validate(canonical(p),r,s,a)['errors'])
    def test_schedule_modified_after_sealing(self):
        p,r,s=fixture();a=attest(p,s);s+=b' '
        self.assertIn('E014_SCHEDULE_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_forged_seal_hash(self):
        p,r,s=fixture();a=attest(p,s);a['syntheticSeal']['bindingSha256']='0'*64
        self.assertIn('E017_ATTESTATION_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_changed_sealed_time_without_rebinding(self):
        p,r,s=fixture();a=attest(p,s);a['syntheticSeal']['sealedAtUtc']='2026-10-28T14:59:59.999Z'
        self.assertIn('E017_ATTESTATION_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_sealed_time_exact_cutoff(self):
        p,r,s=fixture();self.assertTrue(run(p,r,s)['passed'])
    def test_sealed_time_one_millisecond_late(self):
        p,r,s=fixture();a=attest(p,s);t='2026-10-28T15:00:00.001Z'
        a['syntheticSeal']['sealedAtUtc']=t
        a['syntheticSeal']['bindingSha256']=digest(canonical({'capturePayloadSha256':digest(canonical(p)),
            'scheduleSha256':digest(s),'sealedAtUtc':t,'kind':'SYNTHETIC_TEST_ONLY'}))
        self.assertIn('E005_CAPTURE_LATE',validate(canonical(p),r,s,a)['errors'])
    def test_schedule_capture_exact_cutoff(self):
        p,r,s=fixture();p['scheduleCapture']['completedAtUtc']=p['cutoffUtc']
        self.assertTrue(run(p,r,s)['passed'])
    def test_schedule_capture_one_millisecond_late(self):
        p,r,s=fixture();p['scheduleCapture']['completedAtUtc']='2026-10-28T15:00:00.001Z'
        self.assertIn('E005_CAPTURE_LATE',run(p,r,s)['errors'])
    def test_malformed_attestations(self):
        p,r,s=fixture()
        for value in (None,[],0,'bad',{'syntheticSeal':[]},{'syntheticSeal':None}):
            with self.subTest(value=value):
                result=validate(canonical(p),r,s,value)
                self.assertFalse(result['passed'])
                self.assertTrue(result['errors'])
    def test_malformed_seal_timestamp(self):
        p,r,s=fixture();a=attest(p,s);a['syntheticSeal']['sealedAtUtc']='bad'
        a['syntheticSeal']['bindingSha256']=digest(canonical({'capturePayloadSha256':digest(canonical(p)),
            'scheduleSha256':digest(s),'sealedAtUtc':'bad','kind':'SYNTHETIC_TEST_ONLY'}))
        self.assertIn('E007_TIME_CONFLICT',validate(canonical(p),r,s,a)['errors'])
    def test_missing_seal(self):
        p,r,s=fixture();a=attest(p,s);del a['syntheticSeal']
        self.assertIn('E017_ATTESTATION_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_wrong_synthetic_proof(self):
        p,r,s=fixture();a=attest(p,s);a['proof']='UNTRUSTED'
        self.assertIn('E017_ATTESTATION_INVALID',validate(canonical(p),r,s,a)['errors'])
    def test_unverified_timing(self):
        p,r,s=fixture();a=attest(p,s);a['timingClassification']='CLAIMED'
        self.assertIn('E006_TIME_UNVERIFIED',validate(canonical(p),r,s,a)['errors'])
    def test_self_resealed_tamper_is_not_trust(self):
        # Illustrates that attacker-controlled synthetic metadata can be rehashed.
        p,r,s=fixture();p['extra']='attacker-rewritten';a=attest(p,s)
        self.assertTrue(validate(canonical(p),r,s,a)['passed'])

if __name__ == '__main__': unittest.main()
