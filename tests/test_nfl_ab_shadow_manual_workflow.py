"""Shadow the real manual workflow's embedded review steps without GitHub or NFL access."""
import hashlib,io,json,os,pathlib,subprocess,sys,tempfile,unittest,zipfile
from unittest.mock import patch
from test_nfl_ab_operational_provenance_enforcement import ART,ARCHIVE,CAPTURE,REVIEW,RUN,COMMIT,NOW
from scripts.nfl_ab_review_provenance_guard import validate_artifact_expiry,verify_archive_digest,validate_capture_review_chain
WORKFLOW=pathlib.Path(".github/workflows/nfl-ab-wednesday-evidence-rehearsal.yml")

def extract_step(label):
    lines=WORKFLOW.read_text().splitlines()
    marker="      - name: "+label
    i=lines.index(marker)
    start=next(j for j in range(i+1,len(lines)) if lines[j]=="        run: |")+1
    block=[]
    for line in lines[start:]:
        if line.startswith("      - name:") or line.startswith("      - uses:"):
            break
        if line.strip():
            if not line.startswith("          "):
                raise ValueError("INVALID_SHADOW_INDENT")
            block.append(line[10:])
        else: block.append("")
    script="\\n".join(block)
    if not script.startswith("python - <<'PY'\\n") or not script.rstrip().endswith("PY"):
        raise ValueError("INVALID_SHADOW_SCRIPT")
    return script[len("python - <<'PY'\\n"):script.rfind("\\nPY")]

class ShadowWorkflowTests(unittest.TestCase):
    def test_real_review_step_extraction(self):
        script=extract_step("Verify exact capture run, artifact identity and reviewed manifest")
        self.assertIn("validate_capture_review_chain",script)
        self.assertIn("validate_artifact_expiry",script)
        self.assertIn("MANIFEST_NOT_COMMITTED_IN_REVIEW_COMMIT",script)
    def test_real_download_step_extraction(self):
        script=extract_step("Download and verify exact capture archive and extracted bytes")
        self.assertIn("verify_archive_digest",script)
        self.assertIn("UNEXPECTED_CAPTURE_ARCHIVE_MEMBERS",script)
    def test_synthetic_zip_and_digest(self):
        content=json.dumps({"kind":"RESEARCH_ONLY_INDEPENDENT_CAPTURE"}).encode()
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:z.writestr("nfl-ab-raw-capture.json",content)
        archive=buf.getvalue()
        metadata={**ART,"digest":"sha256:"+hashlib.sha256(archive).hexdigest()}
        self.assertTrue(validate_artifact_expiry(metadata,"123",NOW))
        self.assertTrue(verify_archive_digest(archive,metadata))
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.namelist(),["nfl-ab-raw-capture.json"])
            self.assertEqual(json.loads(z.read("nfl-ab-raw-capture.json"))["kind"],"RESEARCH_ONLY_INDEPENDENT_CAPTURE")
    def test_zip_tamper_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"ARTIFACT_ARCHIVE_DIGEST_MISMATCH"):
            verify_archive_digest(b"altered",ART)
    def test_manifest_after_capture_required(self):
        self.assertTrue(validate_capture_review_chain(RUN,CAPTURE,REVIEW,COMMIT,True))
        with self.assertRaises(ValueError):
            validate_capture_review_chain(RUN,CAPTURE,REVIEW,COMMIT,False)
    def test_expired_artifact_rejected(self):
        with self.assertRaises(ValueError):
            validate_artifact_expiry(ART,"123","2027-01-01T00:00:00Z")
if __name__=="__main__":unittest.main()
