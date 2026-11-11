import hashlib
import json
import unittest
from research.model_c_wednesday_delivery_monitor import evaluate, REQUIRED

DAY = "2026-11-11"
def run(start="2026-11-11T16:05:00Z", conclusion="success", gate=True, steps=None):
    return {"event":"schedule", "startedAt":start, "conclusion":conclusion,
            "timeGateRun":gate, "week":10,
            "steps":steps if steps is not None else {k:"success" for k in REQUIRED}}

def artifacts():
    result={}
    for model,status in (("C","AUTOMATED_REVIEW_ONLY"),("C-QB","EXPERIMENTAL_SHADOW_ONLY")):
        raw=json.dumps({"season":2026,"week":10,"status":status,"generatedAt":"2026-11-11T16:06:00Z"})
        result[model]={"content":raw,"sha256":hashlib.sha256(raw.encode()).hexdigest(),
                       "committedAt":"2026-11-11T16:10:00Z"}
    return result

class WednesdayMonitor(unittest.TestCase):
    def test_179_early_green_is_not_delivery(self):
        r=evaluate(target_wednesday=DAY,runs=[run(start="2026-11-11T15:47:00Z",gate=False,
                       steps={k:"skipped" for k in REQUIRED})],artifacts={})
        self.assertEqual(r["reason"],"MISSING_REQUIRED_DELIVERY")
        self.assertEqual(r["earlyChecks"],1)
    def test_180_failed_qb_audit_skipped_commit(self):
        steps={k:"success" for k in REQUIRED}
        steps["Commit draft only"]="skipped"
        r=evaluate(target_wednesday=DAY,runs=[run(conclusion="failure",steps=steps)],artifacts={})
        self.assertEqual(r["reason"],"FAILED_REQUIRED_JOB")
    def test_missing_required_run(self):
        self.assertEqual(evaluate(target_wednesday=DAY,runs=[],artifacts={})["status"],"FAIL")
    def test_skipped_required_run(self):
        self.assertIn("SKIPPED_REQUIRED_DELIVERY",evaluate(target_wednesday=DAY,runs=[run(gate=False)],artifacts={})["reason"])
    def test_skipped_commit_even_green(self):
        s={k:"success" for k in REQUIRED};s["Commit draft only"]="skipped"
        self.assertIn("SKIPPED_OR_FAILED_REQUIRED_STEP",evaluate(target_wednesday=DAY,runs=[run(steps=s)],artifacts=artifacts())["reason"])
    def test_missing_saved_artifact(self):
        self.assertIn("MISSING_SAVED_ARTIFACT",evaluate(target_wednesday=DAY,runs=[run()],artifacts={})["reason"])
    def test_stale_week8_saved_artifact(self):
        a=artifacts();a["C"]["content"]=json.dumps({"season":2026,"week":8})
        self.assertIn("INVALID_PROVENANCE",evaluate(target_wednesday=DAY,runs=[run()],artifacts=a)["reason"])
    def test_tampered_artifact_hash(self):
        a=artifacts();a["C-QB"]["sha256"]="0"*64
        self.assertIn("INVALID_PROVENANCE",evaluate(target_wednesday=DAY,runs=[run()],artifacts=a)["reason"])
    def test_late_commit(self):
        a=artifacts();a["C"]["committedAt"]="2026-11-11T17:00:00Z"
        self.assertIn("INVALID_PROVENANCE",evaluate(target_wednesday=DAY,runs=[run()],artifacts=a)["reason"])
    def test_valid_saved_drafts(self):
        self.assertEqual(evaluate(target_wednesday=DAY,runs=[run()],artifacts=artifacts())["status"],"PASS")

if __name__=="__main__":
    unittest.main()
