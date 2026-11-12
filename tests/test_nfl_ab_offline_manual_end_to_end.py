"""Execute actual manual review step Python bodies with synthetic GitHub responses."""
import contextlib,datetime as dt,hashlib,io,json,os,pathlib,tempfile,unittest,zipfile
from unittest.mock import patch
from test_nfl_ab_shadow_manual_workflow import extract_step
from test_nfl_ab_two_stage_rehearsal import TwoStageTests
from scripts.nfl_ab_two_stage_rehearsal import review
CAPTURE="a"*40
REVIEW="b"*40
RUNID="123456789"
PATH="research/reviewed-manifests/synthetic.json"
REPO="synthetic/offline"

class OfflineManualExecutionTests(unittest.TestCase):
    def exercise(self,tamper=False,expired=False,early=False):
        bundle,games=TwoStageTests().bundle()
        now=dt.datetime.now(dt.timezone.utc)
        capture_at=now-dt.timedelta(minutes=10)
        commit_at=capture_at+dt.timedelta(minutes=(-1 if early else 2))
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            manifest=root/PATH
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(games))
            zipbuf=io.BytesIO()
            with zipfile.ZipFile(zipbuf,"w") as z:
                z.writestr("nfl-ab-raw-capture.json",json.dumps(bundle))
            archive=zipbuf.getvalue()
            artifact={"id":987,"name":"nfl-ab-raw-capture","expired":expired,
                "workflow_run":{"id":int(RUNID)},
                "created_at":capture_at.isoformat(),
                "expires_at":(capture_at+dt.timedelta(days=30)).isoformat(),
                "digest":"sha256:"+hashlib.sha256(archive).hexdigest()}
            run={"id":int(RUNID),"event":"workflow_dispatch",
                "name":"NFL A-B manual Wednesday evidence rehearsal (research only)",
                "path":".github/workflows/nfl-ab-wednesday-evidence-rehearsal.yml",
                "head_branch":"audit/nfl-four-model-publisher-diagnostic",
                "head_sha":CAPTURE,"status":"completed","conclusion":"success",
                "updated_at":capture_at.isoformat()}
            commit={"sha":REVIEW,"commit":{"committer":{"date":commit_at.isoformat()}}}
            env={"GH_TOKEN":"synthetic","CAPTURE_RUN":RUNID,"CAPTURE_SHA":CAPTURE,
                "REVIEW_COMMIT":REVIEW,"REVIEW_HEAD":REVIEW,
                "REVIEWED":PATH,"REVIEW_SHA":hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "REPO":REPO,"RUNNER_TEMP":temp}
            import subprocess
            real_run=subprocess.run
            real_check=subprocess.check_output
            def check(args,*a,**kw):
                if args[:2]==["git","diff-tree"]:return (PATH+"\n") if kw.get("text") else (PATH+"\n").encode()
                if args[:2]!=["gh","api"]:raise AssertionError("UNEXPECTED_EXTERNAL_CALL")
                target=args[2]
                if target.endswith("/actions/runs/"+RUNID):return json.dumps(run).encode()
                if target.endswith("/actions/runs/"+RUNID+"/artifacts"):return json.dumps({"artifacts":[artifact]}).encode()
                if target.endswith("/commits/"+REVIEW):return json.dumps(commit).encode()
                if target.endswith("/actions/artifacts/987/zip"):return archive+b"tamper" if tamper else archive
                raise AssertionError("UNEXPECTED_API_PATH "+target)
            def run_mock(args,*a,**kw):
                if args[:3]==["git","merge-base","--is-ancestor"]:
                    return subprocess.CompletedProcess(args,0)
                raise AssertionError("UNEXPECTED_COMMAND")
            old=pathlib.Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ,env),patch("subprocess.check_output",side_effect=check),patch("subprocess.run",side_effect=run_mock):
                    exec(compile(extract_step("Verify exact capture run, artifact identity and reviewed manifest"),"manual-review-verify","exec"),{"__name__":"__main__"})
                    exec(compile(extract_step("Download and verify exact capture archive and extracted bytes"),"manual-review-download","exec"),{"__name__":"__main__"})
                saved=json.loads((root/"captured/nfl-ab-raw-capture.json").read_text())
                result=review(saved,games)
                self.assertEqual(result["status"],"SCHEDULE_EVIDENCE_PASS")
            finally:os.chdir(old)
    def test_actual_manual_steps_synthetic_end_to_end(self):self.exercise()
    def test_actual_manual_steps_reject_tampered_zip(self):
        with self.assertRaisesRegex(ValueError,"ARTIFACT_ARCHIVE_DIGEST_MISMATCH"):self.exercise(tamper=True)
    def test_actual_manual_steps_reject_expired_artifact(self):
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_CAPTURE_ARTIFACT"):self.exercise(expired=True)
    def test_actual_manual_steps_reject_early_manifest(self):
        with self.assertRaisesRegex(ValueError,"REVIEW_NOT_AFTER_CAPTURE"):self.exercise(early=True)
if __name__=="__main__":unittest.main()
