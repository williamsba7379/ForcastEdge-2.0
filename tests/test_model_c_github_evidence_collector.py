import hashlib
import json
import unittest
from research.model_c_github_evidence_collector import verify, EvidenceError, PATHS

SHA0="a"*40; SHA1="b"*40
def fixture():
    run={"id":180,"event":"schedule","name":"Generate Model C review-only draft",
         "head_sha":SHA0,"conclusion":"success","run_started_at":"2026-11-11T16:05:00Z",
         "updated_at":"2026-11-11T16:20:00Z"}
    steps=[{"name":name,"conclusion":"success"} for name in (
        "Generate independent Model C review draft","Generate separate Model C-QB experimental shadow",
        "Validate generated Model C review draft","Commit draft only")]
    jobs=[{"run_id":180,"conclusion":"success","steps":steps}]
    commits=[{"sha":SHA1,"parents":[SHA0],"message":"Update Model C review-only draft",
              "committed_at":"2026-11-11T16:15:00Z","on_main":True,
              "changed_paths":list(PATHS.values())}]
    files={}
    for model,path in PATHS.items():
        raw=json.dumps({"season":2026,"week":10,"generatedAt":"2026-11-11T16:10:00Z"})
        files[model]={"path":path,"ref":SHA1,"raw":raw,"sha256":hashlib.sha256(raw.encode()).hexdigest()}
    return run,jobs,commits,files

class Collector(unittest.TestCase):
    def reject(self,reason,change):
        evidence=list(fixture());change(evidence)
        with self.assertRaisesRegex(EvidenceError,reason):verify(*evidence)
    def test_valid_fixture(self):
        self.assertEqual(verify(*fixture())["status"],"PASS")
    def test_179_skipped(self):
        self.reject("SKIPPED_REQUIRED_STEP",lambda e:e[1][0]["steps"].__setitem__(-1,{"name":"Commit draft only","conclusion":"skipped"}))
    def test_180_failed(self):
        self.reject("FAILED_RUN",lambda e:e[0].update(conclusion="failure"))
    def test_missing_commit(self):
        self.reject("MISSING_OUTPUT_COMMIT",lambda e:e[2].clear())
    def test_uncommitted(self):
        self.reject("UNCOMMITTED_OUTPUT",lambda e:e[2][0].update(sha=SHA0))
    def test_unlinked_parent(self):
        self.reject("COMMIT_NOT_DESCENDED",lambda e:e[2][0].update(parents=["c"*40]))
    def test_not_pushed(self):
        self.reject("OUTPUT_COMMIT_NOT_ON_MAIN",lambda e:e[2][0].update(on_main=False))
    def test_stale(self):
        def change(e):
            raw=json.dumps({"season":2026,"week":8,"generatedAt":"2026-11-11T16:10:00Z"})
            e[3]["C"]["raw"]=raw;e[3]["C"]["sha256"]=hashlib.sha256(raw.encode()).hexdigest()
        self.reject("STALE_ARTIFACT",change)
    def test_tampered(self):
        self.reject("TAMPERED_ARTIFACT",lambda e:e[3]["C"].update(sha256="0"*64))
    def test_wrong_commit_ref(self):
        self.reject("MISSING_SAVED_ARTIFACT",lambda e:e[3]["C-QB"].update(ref=SHA0))
    def test_missing_changed_file(self):
        self.reject("ARTIFACT_NOT_IN_OUTPUT_COMMIT",lambda e:e[2][0].update(changed_paths=[PATHS["C"]]))
    def test_late_commit(self):
        self.reject("COMMIT_OUTSIDE_RUN",lambda e:e[2][0].update(committed_at="2026-11-11T17:00:00Z"))
    def test_job_run_mismatch(self):
        self.reject("JOB_RUN_MISMATCH",lambda e:e[1][0].update(run_id=179))
if __name__=="__main__":unittest.main()
