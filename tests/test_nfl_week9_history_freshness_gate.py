import copy
import unittest
from scripts.nfl_week9_history_freshness_gate import check

FROZEN={"season":2026,"week":9,"frozenAt":"2026-11-04T17:18:26+00:00"}
def fixtures():
    results=[{"gameId":str(1000+i),"date":"2026-11-01T18:00Z","homeScore":20+i,"awayScore":10,"winner":"Home","scoreSource":"https://site.api.espn.com/scoreboard"} for i in range(14)]
    return {"season":2026,"week":8,"status":"COMPLETE","gamesCompleted":14,"results":results}, {"games":[{"season":2026,"id":g["gameId"],"homeScore":g["homeScore"],"awayScore":g["awayScore"],"winner":g["winner"]} for g in results]}

class TestFreshnessGate(unittest.TestCase):
    def test_complete_history_matches_but_never_promotes(self):
        report,history=fixtures()
        x=check(report,history,FROZEN)
        self.assertEqual(x["status"],"HISTORY_IDS_AND_SCORES_MATCH")
        self.assertEqual(x["missingIds"],[])
        self.assertFalse(x["promotionAuthorized"])
    def test_all_fourteen_missing_fail_closed(self):
        report,_=fixtures()
        x=check(report,{"games":[]},FROZEN)
        self.assertEqual(x["status"],"BLOCKED")
        self.assertEqual(len(x["missingIds"]),14)
        self.assertIn("MISSING_ELIGIBLE_FINALS",x["errors"])
    def test_one_missing_fails(self):
        report,history=fixtures()
        history["games"].pop()
        self.assertEqual(len(check(report,history,FROZEN)["missingIds"]),1)
    def test_score_mismatch_fails(self):
        report,history=fixtures()
        history["games"][0]["homeScore"]=999
        self.assertEqual(len(check(report,history,FROZEN)["mismatchedIds"]),1)
    def test_duplicate_history_id_fails(self):
        report,history=fixtures()
        history["games"].append(copy.deepcopy(history["games"][0]))
        self.assertEqual(len(check(report,history,FROZEN)["mismatchedIds"]),1)
    def test_duplicate_evidence_fails(self):
        report,history=fixtures()
        report["results"][1]["gameId"]=report["results"][0]["gameId"]
        self.assertIn("DUPLICATE_VERIFIED_GAME_ID",check(report,history,FROZEN)["errors"])
    def test_unverified_source_fails(self):
        report,history=fixtures()
        report["results"][0]["scoreSource"]="https://example.org"
        self.assertIn("UNVERIFIED_SCORE_SOURCE_1000",check(report,history,FROZEN)["errors"])
    def test_future_game_fails(self):
        report,history=fixtures()
        report["results"][0]["date"]="2026-11-05T18:00Z"
        self.assertIn("RESULT_NOT_PRE_FREEZE_1000",check(report,history,FROZEN)["errors"])
    def test_wrong_week_fails(self):
        report,history=fixtures()
        report["week"]=7
        self.assertIn("SOURCE_REPORT_NOT_COMPLETE",check(report,history,FROZEN)["errors"])
if __name__=="__main__":
    unittest.main()
