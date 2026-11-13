import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"research"))
from nfl_operational_readiness import audit
class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.schedule={"season":2026,"week":9,"games":[{"id":"1"}]}
        self.c={"season":2026,"week":9,"generatedAt":"2026-11-04T15:59:00Z","games":[{"id":"1"}]}
        self.q=dict(self.c)
        self.card={"season":2026,"week":9,"frozenAt":"2026-11-04T16:00:00Z",
                   "games":[{"id":"1","picks":{"A":"x","B":"x","C":"x","C-QB":"x"}}]}
        self.sources={n:{"artifact_id":1,"run_id":2,"sha256":"a"*64,"commit":"b"*40,"verified":True}
                      for n in ("A","B","C","C-QB")}
    def run_audit(self,**kwargs):
        return audit(self.schedule,self.c,self.q,self.card,"2026-11-04T16:00:00Z",
                     official_qb_evidence=kwargs.get("qb",True),source_artifacts=kwargs.get("sources",self.sources))
    def test_research_only(self):
        v=self.run_audit();self.assertEqual(v["status"],"RESEARCH_CONTRACT_PASS");self.assertFalse(v["productionReady"])
    def test_week8_stale(self):
        self.card["week"]=8;self.assertIn("STALE_WEEK",self.run_audit()["reasons"])
    def test_model_c_after_cutoff(self):
        self.c["generatedAt"]="2026-11-04T16:49:00Z"
        self.assertIn("POST_CUTOFF_C",self.run_audit()["reasons"])
    def test_qb_after_cutoff(self):
        self.q["generatedAt"]="2026-11-04T16:49:00Z"
        self.assertIn("POST_CUTOFF_C-QB",self.run_audit()["reasons"])
    def test_qb_unverified(self):
        self.assertIn("QB_VERIFICATION_MISSING",self.run_audit(qb=False)["reasons"])
    def test_a_artifact_missing(self):
        del self.sources["A"];self.assertIn("IMMUTABLE_SOURCE_MISSING_A",self.run_audit()["reasons"])
    def test_b_artifact_missing(self):
        del self.sources["B"];self.assertIn("IMMUTABLE_SOURCE_MISSING_B",self.run_audit()["reasons"])
    def test_missing_game(self):
        self.card["games"]=[];self.assertIn("INCOMPLETE_OR_MISMATCHED_GAMES",self.run_audit()["reasons"])
    def test_missing_model(self):
        del self.card["games"][0]["picks"]["C-QB"]
        self.assertIn("FOUR_MODEL_PICKS_MISSING",self.run_audit()["reasons"])
    def test_post_cutoff_card(self):
        self.card["frozenAt"]="2026-11-04T17:18:26Z"
        self.assertIn("POST_CUTOFF_CARD",self.run_audit()["reasons"])
    def test_wrong_local_hour(self):
        v=audit(self.schedule,self.c,self.q,self.card,"2026-11-04T15:00:00Z",
                official_qb_evidence=True,source_artifacts=self.sources)
        self.assertIn("NOT_WEDNESDAY_11_ET",v["reasons"])
    def test_missing_sources(self):
        self.assertIn("IMMUTABLE_SOURCE_MISSING_C",self.run_audit(sources={})["reasons"])
if __name__=="__main__":unittest.main()
