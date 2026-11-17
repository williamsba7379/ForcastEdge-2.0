"""Offline synthetic capture -> reviewed manifest -> provenance -> comparison rehearsal.

No HTTP, GitHub dispatch, live capture, production writes or real artifacts.
"""
import copy
import datetime as dt
import hashlib
import json
import unittest
from unittest.mock import Mock
from test_nfl_ab_two_stage_rehearsal import TwoStageTests
from test_nfl_ab_wednesday_evidence_rehearsal import CUTOFF
from scripts.nfl_ab_two_stage_rehearsal import capture,review
from scripts.nfl_ab_review_provenance_guard import (
    BRANCH, WORKFLOW,validate_capture_run,validate_capture_artifact,validate_review_manifest,
)

RUN_ID="123456789"
COMMIT="a"*40
MANIFEST="research/reviewed-manifests/2026-week-11.json"

def synthetic():
    bundle,games=TwoStageTests().bundle()
    captured_at=dt.datetime(2026,11,18,15,55,tzinfo=dt.timezone.utc)
    reviewed_at=captured_at+dt.timedelta(minutes=2)
    run={"id":int(RUN_ID),"event":"workflow_dispatch",
         "name":"NFL A-B manual Wednesday evidence rehearsal (research only)",
         "path":WORKFLOW,"head_branch":BRANCH,"head_sha":COMMIT,
         "status":"completed","conclusion":"success",
         "created_at":captured_at.isoformat(),"updated_at":captured_at.isoformat()}
    artifact={"name":"nfl-ab-raw-capture","expired":False,
              "workflow_run":{"id":int(RUN_ID)},"created_at":captured_at.isoformat(),
              "expires_at":(captured_at+dt.timedelta(days=30)).isoformat()}
    manifest_bytes=json.dumps(games,sort_keys=True).encode()
    return bundle,games,run,artifact,manifest_bytes,captured_at,reviewed_at

def offline_handoff(bundle,run,artifact,manifest_bytes,capture_sha=COMMIT,
                    run_id=RUN_ID,reviewed_at=None,created_at=None,retention_days=30):
    # These metadata checks simulate the GitHub API responses; they do not
    # claim that the existing workflow enforces creation order or retention.
    validate_capture_run(run,run_id,capture_sha)
    validate_capture_artifact(artifact,run_id)
    if created_at is not None and reviewed_at is not None and reviewed_at<=created_at:
        raise ValueError("REVIEW_NOT_AFTER_CAPTURE")
    if retention_days!=30:
        raise ValueError("RETENTION_POLICY_MISMATCH")
    games=validate_review_manifest(MANIFEST,hashlib.sha256(manifest_bytes).hexdigest(),manifest_bytes)
    return review(bundle,games)

class SyntheticHandoffTests(unittest.TestCase):
    def test_full_handoff_without_network(self):
        b,g,r,a,data,at,review_at=synthetic()
        original=json.dumps(b,sort_keys=True)
        fetch_nfl=Mock(return_value=b["nfl"])
        fetch_espn=Mock(return_value=b["espn"])
        captured=capture(2026,11,CUTOFF,fetch_nfl,fetch_espn)
        self.assertEqual(fetch_nfl.call_count,1)
        self.assertEqual(fetch_espn.call_count,1)
        result=offline_handoff(captured,r,a,data,reviewed_at=review_at,created_at=at)
        self.assertEqual(result["status"],"SCHEDULE_EVIDENCE_PASS")
        self.assertEqual(len(result["captureBundleSha256"]),64)
        self.assertFalse(result["productionReady"])
        self.assertFalse(result["officialFrozen"])
        self.assertEqual(json.dumps(b,sort_keys=True),original)
    def test_reject_wrong_commit(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaises(ValueError):
            offline_handoff(b,r,a,data,capture_sha="b"*40)
    def test_reject_wrong_branch(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaises(ValueError):
            offline_handoff(b,{**r,"head_branch":"main"},a,data)
    def test_reject_wrong_capture_artifact(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaises(ValueError):
            offline_handoff(b,r,{**a,"workflow_run":{"id":9}},data)
    def test_reject_tampered_manifest(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaises(ValueError):
            validate_review_manifest(MANIFEST,hashlib.sha256(data).hexdigest(),data+b" ")
    def test_reject_review_before_capture_in_simulation(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaisesRegex(ValueError,"REVIEW_NOT_AFTER_CAPTURE"):
            offline_handoff(b,r,a,data,reviewed_at=at-dt.timedelta(seconds=1),created_at=at)
    def test_reject_retention_mismatch_in_simulation(self):
        b,g,r,a,data,at,t=synthetic()
        with self.assertRaisesRegex(ValueError,"RETENTION_POLICY_MISMATCH"):
            offline_handoff(b,r,a,data,retention_days=7)
    def test_reject_mismatched_schedule(self):
        b,g,r,a,data,at,t=synthetic()
        altered=copy.deepcopy(g)
        altered[0]["date"]="2026-11-19T02:15:00Z"
        altered_bytes=json.dumps(altered).encode()
        with self.assertRaises(ValueError):
            offline_handoff(b,r,a,altered_bytes)
if __name__=="__main__":
    unittest.main()
