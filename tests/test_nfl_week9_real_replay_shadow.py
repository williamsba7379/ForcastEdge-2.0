"""Offline negative tests for real research snapshot verifier; no GitHub writes."""
import io,json,zipfile,hashlib,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"research"))
from nfl_week9_real_archive_replay import replay,RUN,ARTIFACT,COMMIT,DIGEST,MEMBER,WORKFLOW

class ReplayNegativeTests(unittest.TestCase):
    def setUp(self):
        self.run={"id":RUN,"head_sha":COMMIT,"path":WORKFLOW,"status":"completed","conclusion":"success"}
        self.artifact={"id":ARTIFACT,"expired":False,"workflow_run":{"id":RUN,"head_sha":COMMIT}}
        self.schedule={"season":2026,"week":9,"games":[]}
        self.archive=b""
    def check(self):return replay(self.run,self.artifact,self.archive,self.schedule)
    def test_wrong_run(self):
        self.run["id"]=1;self.assertEqual(self.check()["reason"],"RUN_PROVENANCE_MISMATCH")
    def test_wrong_commit(self):
        self.run["head_sha"]="0"*40;self.assertEqual(self.check()["reason"],"RUN_PROVENANCE_MISMATCH")
    def test_failed_run(self):
        self.run["conclusion"]="failure";self.assertEqual(self.check()["reason"],"RUN_PROVENANCE_MISMATCH")
    def test_wrong_workflow(self):
        self.run["path"]="other.yml";self.assertEqual(self.check()["reason"],"RUN_PROVENANCE_MISMATCH")
    def test_wrong_artifact(self):
        self.artifact["id"]=1;self.assertEqual(self.check()["reason"],"ARTIFACT_PROVENANCE_MISMATCH")
    def test_wrong_artifact_run(self):
        self.artifact["workflow_run"]["id"]=1;self.assertEqual(self.check()["reason"],"ARTIFACT_PROVENANCE_MISMATCH")
    def test_expired(self):
        self.artifact["expired"]=True;self.assertEqual(self.check()["reason"],"ARTIFACT_PROVENANCE_MISMATCH")
    def test_corrupt_zip(self):
        self.assertEqual(self.check()["status"],"NOT_READY")
    def test_wrong_digest(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr(MEMBER,b'{"season":2026}')
            z.writestr("week9-readiness.json",json.dumps({"mode":"READ_ONLY_NO_FREEZE"}))
        self.archive=out.getvalue()
        self.assertEqual(self.check()["reason"],"PAYLOAD_DIGEST_MISMATCH")

if __name__=="__main__":unittest.main()
