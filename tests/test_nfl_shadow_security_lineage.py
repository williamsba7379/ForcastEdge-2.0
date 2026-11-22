"""Security and provenance negative tests; isolated from production."""
import io,sys,pathlib,unittest,zipfile
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"research"))
from nfl_shadow_security import trusted_redirect,SafeArtifactRedirect,bounded_read,read_zip_members
from nfl_shadow_lineage import assess_lineage

class SecurityTests(unittest.TestCase):
    def test_valid_blob(self):
        self.assertTrue(trusted_redirect("https://a.blob.core.windows.net/file"))
    def test_valid_actions(self):
        self.assertTrue(trusted_redirect("https://a.actions.githubusercontent.com/x"))
    def test_evil_suffix(self):
        self.assertFalse(trusted_redirect("https://evilactions.githubusercontent.com/x"))
    def test_http_rejected(self):
        self.assertFalse(trusted_redirect("http://a.blob.core.windows.net/x"))
    def test_userinfo_rejected(self):
        self.assertFalse(trusted_redirect("https://user:pass@a.blob.core.windows.net/x"))
    def test_untrusted_redirect(self):
        with self.assertRaises(ValueError):
            SafeArtifactRedirect().redirect_request(None,None,302,"",{},"https://evil.example/x")
    def test_bearer_not_forwarded(self):
        req=SafeArtifactRedirect().redirect_request(None,None,302,"",{},"https://a.blob.core.windows.net/x")
        self.assertNotIn("Authorization",req.headers)
    def test_large_content_length(self):
        response=Mock(headers={"Content-Length":"26000000"})
        with self.assertRaises(ValueError):bounded_read(response)
    def test_large_stream(self):
        class Stream:
            headers={}
            def read(self,n):return b"x"*n
        with self.assertRaises(ValueError):bounded_read(Stream(),100)
    def test_duplicate_zip(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                z.writestr("a",b"1");z.writestr("a",b"2")
        with self.assertRaises(ValueError):read_zip_members(data.getvalue(),["a"])
    def test_missing_zip_member(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:z.writestr("a",b"1")
        with self.assertRaises(ValueError):read_zip_members(data.getvalue(),["b"])
    def test_zip_path_traversal(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:z.writestr("../a",b"1")
        with self.assertRaises(ValueError):read_zip_members(data.getvalue(),["../a"])
    def test_valid_zip(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:z.writestr("a",b"1")
        self.assertEqual(read_zip_members(data.getvalue(),["a"])["a"],b"1")

class LineageTests(unittest.TestCase):
    def setUp(self):
        self.good={"cutoff":"2026-11-11T16:00:00Z",
            "independent_nfl_schedule_authenticated":True,
            "independent_espn_schedule_authenticated":True,
            "models":{n:{"run_id":1,"artifact_id":2,"commit":"a"*40,"sha256":"b"*64,
                          "source_verified":True,"input_times":["2026-11-11T15:59:00Z"]}
                      for n in ("A","B","C","C-QB")}}
    def test_contract_not_production(self):
        result=assess_lineage(self.good)
        self.assertEqual(result["status"],"RESEARCH_LINEAGE_CONTRACT_ONLY")
        self.assertFalse(result["productionReady"])
    def test_missing_a(self):
        del self.good["models"]["A"]
        self.assertIn("LINEAGE_MISSING_A",assess_lineage(self.good)["reasons"])
    def test_missing_qb(self):
        del self.good["models"]["C-QB"]
        self.assertIn("LINEAGE_MISSING_C-QB",assess_lineage(self.good)["reasons"])
    def test_post_cutoff(self):
        self.good["models"]["C"]["input_times"]=["2026-11-11T16:01:00Z"]
        self.assertIn("INPUT_AFTER_CUTOFF_C",assess_lineage(self.good)["reasons"])
    def test_empty_timestamps(self):
        self.good["models"]["B"]["input_times"]=[]
        self.assertIn("LINEAGE_MISSING_B",assess_lineage(self.good)["reasons"])
    def test_unverified_source(self):
        self.good["models"]["C"]["source_verified"]=False
        self.assertIn("LINEAGE_MISSING_C",assess_lineage(self.good)["reasons"])
    def test_missing_nfl(self):
        self.good["independent_nfl_schedule_authenticated"]=False
        self.assertIn("NFL_SCHEDULE_UNVERIFIED",assess_lineage(self.good)["reasons"])
    def test_wrong_cutoff(self):
        self.good["cutoff"]="2026-11-11T15:00:00Z"
        self.assertIn("INVALID_WEDNESDAY_CUTOFF",assess_lineage(self.good)["reasons"])

if __name__=="__main__":unittest.main()
