"""Offline tests with mocked authenticated GitHub API responses; no production access."""
import datetime as dt
import hashlib
import io
import json
import pathlib
import sys
import unittest
import zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"))
from nfl_real_artifact_shadow import shadow,validate_artifact,NotReady

REPO="williamsba7379/ForcastEdge-2.0"
CUTOFF="2026-11-11T16:00:00Z"
def pack(obj):
    raw=json.dumps(obj).encode()
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w") as z:z.writestr("model.json",raw)
    return raw,bio.getvalue()

class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.games=[{"id":"1","home":"A","away":"B","date":"2026-11-12T01:00:00Z"},
                    {"id":"2","home":"C","away":"D","date":"2026-11-15T18:00:00Z"}]
        self.payload={"season":2026,"week":10,"generatedAt":"2026-11-11T15:59:00Z","games":self.games}
        self.raw,self.archive=pack(self.payload)
        self.spec={"run_id":123,"artifact_id":456,"commit":"a"*40,
                   "workflow_path":".github/workflows/model-c-draft.yml",
                   "member":"model.json","sha256":hashlib.sha256(self.raw).hexdigest()}
        self.run={"id":123,"head_sha":"a"*40,"status":"completed","conclusion":"success",
                  "path":".github/workflows/model-c-draft.yml"}
        self.artifact={"id":456,"expired":False,"workflow_run":{"id":123}}
        self.req={"season":2026,"week":10,"cutoff":CUTOFF,"repo":REPO,
                  "nfl_source_id":"official-nfl","espn_source_id":"espn",
                  "nfl_schedule":{"season":2026,"week":10,"games":self.games},
                  "espn_schedule":{"season":2026,"week":10,"games":self.games},
                  "artifacts":{"model_c":self.spec,"model_c_qb":self.spec}}
    def fetch(self,path):
        if path.endswith("/zip"):return self.archive
        if path.endswith("/actions/runs/123"):return json.dumps(self.run).encode()
        if path.endswith("/actions/artifacts/456"):return json.dumps(self.artifact).encode()
        raise AssertionError(path)
    def status(self):
        return shadow(self.req,self.fetch)
    def test_valid_research_only(self):
        x=self.status();self.assertEqual(x["status"],"VERIFIED_RESEARCH_ONLY");self.assertFalse(x["productionReady"])
    def test_stale_week8(self):
        self.req["week"]=8;self.assertEqual(self.status()["status"],"NOT_READY")
    def test_missing_qb(self):
        del self.req["artifacts"]["model_c_qb"];self.assertEqual(self.status()["status"],"NOT_READY")
    def test_wrong_run_commit(self):
        self.run["head_sha"]="b"*40;self.assertEqual(self.status()["reason"],"RUN_IDENTITY_MISMATCH")
    def test_failed_producer(self):
        self.run["conclusion"]="failure";self.assertEqual(self.status()["reason"],"RUN_IDENTITY_MISMATCH")
    def test_wrong_workflow(self):
        self.run["path"]="different.yml";self.assertEqual(self.status()["reason"],"RUN_IDENTITY_MISMATCH")
    def test_artifact_wrong_run(self):
        self.artifact["workflow_run"]["id"]=888;self.assertEqual(self.status()["reason"],"ARTIFACT_IDENTITY_MISMATCH")
    def test_expired_artifact(self):
        self.artifact["expired"]=True;self.assertEqual(self.status()["reason"],"ARTIFACT_IDENTITY_MISMATCH")
    def test_tampered_bytes(self):
        self.archive=pack({**self.payload,"week":8})[1]
        self.assertEqual(self.status()["reason"],"ARTIFACT_DIGEST_MISMATCH")
    def test_missing_zip_member(self):
        self.spec["member"]="absent.json";self.assertEqual(self.status()["reason"],"ARTIFACT_MEMBER_MISSING")
    def test_post_cutoff(self):
        self.raw,self.archive=pack({**self.payload,"generatedAt":"2026-11-11T16:01:00Z"})
        self.spec["sha256"]=hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(self.status()["reason"],"POST_CUTOFF_ARTIFACT")
    def test_schedule_mismatch(self):
        self.req["espn_schedule"]={**self.req["espn_schedule"],"games":self.games[:1]}
        self.assertEqual(self.status()["reason"],"SCHEDULE_DISAGREEMENT")
    def test_missing_schedule(self):
        self.req["nfl_schedule"]=None;self.assertEqual(self.status()["status"],"NOT_READY")
    def test_same_source_not_independent(self):
        self.req["espn_source_id"]="official-nfl"
        self.assertEqual(self.status()["reason"],"INDEPENDENT_SCHEDULE_UNVERIFIED")
    def test_dynamic_two_games(self):
        self.assertEqual(self.status()["games"],2)
    def test_invalid_cutoff(self):
        self.req["cutoff"]="2026-11-11T15:00:00Z"
        self.assertEqual(self.status()["reason"],"INVALID_WEDNESDAY_CUTOFF")
    def test_missing_timestamp(self):
        self.raw,self.archive=pack({k:v for k,v in self.payload.items() if k!="generatedAt"})
        self.spec["sha256"]=hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(self.status()["status"],"NOT_READY")
    def test_invalid_repo(self):
        self.req["repo"]="other/repo";self.assertEqual(self.status()["reason"],"REPOSITORY_NOT_APPROVED")

if __name__=="__main__":unittest.main()
