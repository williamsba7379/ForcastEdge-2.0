#!/usr/bin/env python3
"""Offline fixtures for isolated historical availability validation."""
import hashlib
import unittest
from nfl_historical_availability_audit import validate, audit

CUTOFF = "2026-10-24T11:48:40Z"
RAW = '{"status":"final","home":21,"away":17}'
def fixture():
    return {"gameId": "401000001", "source": "https://site.api.espn.com/example",
            "kickoffAt": "2026-10-23T00:15:00Z",
            "observedFinalAt": "2026-10-23T04:00:00Z",
            "retrievedAt": "2026-10-23T04:01:00Z",
            "contentSha256": hashlib.sha256(RAW.encode()).hexdigest(),
            "rawResponse": RAW}

class AvailabilityTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(fixture(), CUTOFF), (True, "VERIFIED_AS_OF_CUTOFF"))
    def test_missing_required(self):
        for field in ("gameId", "source", "observedFinalAt", "retrievedAt", "contentSha256"):
            with self.subTest(field=field):
                row=fixture();del row[field]
                self.assertFalse(validate(row,CUTOFF)[0])
    def test_late_observed(self):
        row=fixture();row["observedFinalAt"]=CUTOFF;row["retrievedAt"]=CUTOFF
        self.assertEqual(validate(row,CUTOFF)[1],"LATE_FINAL_EVIDENCE")
    def test_late_retrieved(self):
        row=fixture();row["retrievedAt"]=CUTOFF
        self.assertEqual(validate(row,CUTOFF)[1],"LATE_FINAL_EVIDENCE")
    def test_inconsistent_times(self):
        row=fixture();row["retrievedAt"]="2026-10-23T03:59:00Z"
        self.assertEqual(validate(row,CUTOFF)[1],"INCONSISTENT_EVIDENCE_TIMES")
    def test_before_kickoff(self):
        row=fixture();row["observedFinalAt"]="2026-10-22T23:59:00Z"
        self.assertEqual(validate(row,CUTOFF)[1],"FINAL_BEFORE_KICKOFF")
    def test_hash_mismatch(self):
        row=fixture();row["rawResponse"]="changed"
        self.assertEqual(validate(row,CUTOFF)[1],"CONTENT_HASH_MISMATCH")
    def test_invalid_hash(self):
        row=fixture();row["contentSha256"]="xyz"
        self.assertEqual(validate(row,CUTOFF)[1],"INVALID_CONTENT_HASH")
    def test_timezone_required(self):
        row=fixture();row["observedFinalAt"]="2026-10-23T04:00:00"
        self.assertEqual(validate(row,CUTOFF)[1],"INVALID_EVIDENCE")
    def test_non_https(self):
        row=fixture();row["source"]="http://example.com"
        self.assertEqual(validate(row,CUTOFF)[1],"INVALID_SOURCE")
    def test_missing_kickoff(self):
        row=fixture();del row["kickoffAt"]
        self.assertFalse(validate(row,CUTOFF)[0])
    def test_summary(self):
        good=fixture();bad=fixture();bad["retrievedAt"]=CUTOFF
        result=audit([good,bad],CUTOFF)
        self.assertEqual((result["eligible"],result["rejected"]),(1,1))

if __name__ == "__main__":
    unittest.main()
