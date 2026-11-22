"""Offline provenance guards: no GitHub API calls or live captures."""
import hashlib
import json
import unittest
from scripts.nfl_ab_review_provenance_guard import validate_capture_run,validate_capture_artifact,validate_review_manifest,BRANCH,WORKFLOW

SHA="a"*40
RID="43268416357"
RUN={"id":int(RID),"event":"workflow_dispatch","name":"NFL A-B manual Wednesday evidence rehearsal (research only)","path":WORKFLOW,"head_branch":BRANCH,"head_sha":SHA,"status":"completed","conclusion":"success"}
ART={"name":"nfl-ab-raw-capture","expired":False,"workflow_run":{"id":int(RID)}}
DATA=b'[{"date":"2026-11-19T01:15:00Z","home":"Home","away":"Away","sourceSnippet":"proof"}]'
PATH="research/reviewed-manifests/2026-week-11.json"
HASH=hashlib.sha256(DATA).hexdigest()

class GuardTests(unittest.TestCase):
    def test_exact_capture_identity(self):
        self.assertTrue(validate_capture_run(RUN,RID,SHA))
    def test_reject_wrong_branch(self):
        with self.assertRaises(ValueError): validate_capture_run({**RUN,"head_branch":"main"},RID,SHA)
    def test_reject_wrong_commit(self):
        with self.assertRaises(ValueError): validate_capture_run({**RUN,"head_sha":"b"*40},RID,SHA)
    def test_reject_wrong_workflow(self):
        with self.assertRaises(ValueError): validate_capture_run({**RUN,"path":"other.yml"},RID,SHA)
    def test_reject_failed_capture(self):
        with self.assertRaises(ValueError): validate_capture_run({**RUN,"conclusion":"failure"},RID,SHA)
    def test_reject_wrong_run_id(self):
        with self.assertRaises(ValueError): validate_capture_run(RUN,"123",SHA)
    def test_artifact_identity(self):
        self.assertTrue(validate_capture_artifact(ART,RID))
    def test_reject_expired_artifact(self):
        with self.assertRaises(ValueError): validate_capture_artifact({**ART,"expired":True},RID)
    def test_reject_foreign_artifact(self):
        with self.assertRaises(ValueError): validate_capture_artifact({**ART,"workflow_run":{"id":1}},RID)
    def test_reviewed_manifest(self):
        self.assertEqual(len(validate_review_manifest(PATH,HASH,DATA)),1)
    def test_reject_manifest_tamper(self):
        with self.assertRaises(ValueError): validate_review_manifest(PATH,HASH,DATA+b" ")
    def test_reject_untrusted_path(self):
        with self.assertRaises(ValueError): validate_review_manifest("../../etc/passwd",HASH,DATA)
    def test_reject_empty_manifest(self):
        empty=b"[]"
        with self.assertRaises(ValueError): validate_review_manifest(PATH,hashlib.sha256(empty).hexdigest(),empty)

if __name__=="__main__":
    unittest.main()
