"""Fail-closed two-stage rehearsal tests; no HTTP or production changes."""
import copy
import json
import unittest
from unittest.mock import Mock
from test_nfl_ab_wednesday_evidence_rehearsal import fixture, CUTOFF
from scripts.nfl_ab_two_stage_rehearsal import capture,review,validate_bundle

class TwoStageTests(unittest.TestCase):
    def bundle(self):
        nfl,reviewed,espn=fixture()
        b={"kind":"RESEARCH_ONLY_INDEPENDENT_CAPTURE","schemaVersion":1,
           "season":2026,"week":11,"cutoff":CUTOFF,
           "nfl":nfl,"espn":espn,"officialFrozen":False,
           "publishable":False,"productionReady":False}
        return b,reviewed
    def test_review_preserves_original_capture(self):
        b,r=self.bundle()
        before=json.dumps(b,sort_keys=True)
        result=review(b,r)
        self.assertEqual(result["status"],"SCHEDULE_EVIDENCE_PASS")
        self.assertFalse(result["productionReady"])
        self.assertEqual(json.dumps(b,sort_keys=True),before)
    def test_review_requires_reviewed_manifest(self):
        b,_=self.bundle()
        with self.assertRaises(ValueError):
            review(b,[])
    def test_capture_rejects_wrong_cutoff_before_fetch(self):
        a=Mock()
        with self.assertRaisesRegex(ValueError,"INVALID_WEDNESDAY_CUTOFF"):
            capture(2026,11,"2026-11-18T15:00:00Z",a,a)
        a.assert_not_called()
    def test_capture_sources_are_independent(self):
        b,_=self.bundle()
        a=Mock(return_value=b["nfl"])
        e=Mock(return_value=b["espn"])
        result=capture(2026,11,CUTOFF,a,e)
        self.assertTrue(validate_bundle(result))
        a.assert_called_once()
        e.assert_called_once()
    def test_capture_rejects_late_nfl(self):
        b,_=self.bundle()
        b["nfl"]["retrievedAt"]="2026-11-18T16:00:01Z"
        with self.assertRaises(ValueError):
            validate_bundle(b)
    def test_capture_rejects_tampered_espn(self):
        b,_=self.bundle()
        b["espn"]["scheduleEvidence"]["responseSha256"]="0"*64
        with self.assertRaises(ValueError):
            validate_bundle(b)
    def test_capture_rejects_tampered_nfl(self):
        b,_=self.bundle()
        b["nfl"]["responseSha256"]="0"*64
        with self.assertRaises(ValueError):
            validate_bundle(b)
    def test_capture_rejects_stale_nfl(self):
        b,_=self.bundle()
        b["nfl"]["retrievedAt"]="2026-11-17T14:00:00Z"
        with self.assertRaises(ValueError):
            validate_bundle(b)
    def test_capture_rejects_week_mismatch(self):
        b,_=self.bundle()
        b["week"]=12
        with self.assertRaisesRegex(ValueError,"CAPTURE_WEEK_MISMATCH"):
            validate_bundle(b)
    def test_review_rejects_mismatched_kickoff(self):
        b,r=self.bundle()
        r[0]["date"]="2026-11-19T02:15:00Z"
        with self.assertRaises(ValueError):
            review(b,r)

if __name__=="__main__":
    unittest.main()
