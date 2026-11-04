import copy
import unittest
from scripts.nfl_week9_history_sync_provenance import validate,SOURCE

FROZEN={"frozenAt":"2026-11-04T17:18:26+00:00"}
def fixtures():
    results=[]
    for i in range(14):
        results.append({"gameId":str(1000+i),"date":"2026-11-01T18:00Z","home":"Home "+str(i),"away":"Away "+str(i),"homeScore":20+i,"awayScore":10,"winner":"Home "+str(i),"scoreSource":SOURCE})
    report={"season":2026,"week":8,"status":"COMPLETE","gamesCompleted":14,"gamesRemaining":0,"results":results}
    history={"games":[{"season":2026,"id":g["gameId"],"week":8,**{k:g[k] for k in ("date","home","away","homeScore","awayScore","winner")}} for g in results]}
    return report,history

class TestHistorySync(unittest.TestCase):
    def test_consistent_but_never_promotable(self):
        r,h=fixtures(); x=validate(r,h,FROZEN)
        self.assertEqual(x["status"],"CONSISTENT_NOT_PROMOTABLE")
        self.assertFalse(x["promotionAuthorized"])
    def test_fourteen_missing(self):
        r,h=fixtures();h["games"]=[]
        x=validate(r,h,FROZEN)
        self.assertEqual(len(x["missingGameIds"]),14)
        self.assertIn("MISSING_HISTORY_GAMES",x["failures"])
    def test_partial_history(self):
        r,h=fixtures();h["games"].pop()
        self.assertEqual(len(validate(r,h,FROZEN)["missingGameIds"]),1)
    def test_duplicate_source_ids(self):
        r,h=fixtures();r["results"][1]["gameId"]=r["results"][0]["gameId"]
        self.assertIn("DUPLICATE_SOURCE_IDS",validate(r,h,FROZEN)["failures"])
    def test_duplicate_history_ids(self):
        r,h=fixtures();h["games"].append(copy.deepcopy(h["games"][0]))
        self.assertIn("DUPLICATE_HISTORY_IDS",validate(r,h,FROZEN)["failures"])
    def test_conflicting_scores(self):
        r,h=fixtures();h["games"][0]["homeScore"]=99
        self.assertIn("CONFLICTING_RESULTS",validate(r,h,FROZEN)["failures"])
    def test_conflicting_winner(self):
        r,h=fixtures();r["results"][0]["winner"]="Away 0"
        self.assertIn("CONFLICTING_RESULTS",validate(r,h,FROZEN)["failures"])
    def test_conflicting_teams(self):
        r,h=fixtures();h["games"][0]["home"]="Other"
        self.assertIn("CONFLICTING_RESULTS",validate(r,h,FROZEN)["failures"])
    def test_future_result(self):
        r,h=fixtures();r["results"][0]["date"]="2026-11-06T00:00Z"
        self.assertIn("INVALID_RESULT_CUTOFF",validate(r,h,FROZEN)["failures"])
    def test_naive_timestamp(self):
        r,h=fixtures();r["results"][0]["date"]="2026-11-01T18:00:00"
        self.assertIn("INVALID_RESULT_CUTOFF",validate(r,h,FROZEN)["failures"])
    def test_unapproved_source(self):
        r,h=fixtures();r["results"][0]["scoreSource"]="https://site.api.espn.com.evil.test"
        self.assertIn("INVALID_SCORE_SOURCE",validate(r,h,FROZEN)["failures"])
    def test_missing_source(self):
        r,h=fixtures();r["results"][0].pop("scoreSource")
        self.assertIn("INVALID_SCORE_SOURCE",validate(r,h,FROZEN)["failures"])
    def test_incomplete_report(self):
        r,h=fixtures();r["gamesCompleted"]=13
        self.assertIn("INCOMPLETE_SOURCE_REPORT",validate(r,h,FROZEN)["failures"])
    def test_invalid_score(self):
        r,h=fixtures();r["results"][0]["homeScore"]=-1
        self.assertIn("CONFLICTING_RESULTS",validate(r,h,FROZEN)["failures"])
    def test_wrong_week_history(self):
        r,h=fixtures();h["games"][0]["week"]=7
        self.assertIn("CONFLICTING_RESULTS",validate(r,h,FROZEN)["failures"])
if __name__=="__main__": unittest.main()
