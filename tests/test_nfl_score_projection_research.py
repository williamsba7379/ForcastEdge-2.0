import datetime as dt
import unittest
from research.nfl_score_projection_research import prior, project, walkforward

def history():
    games=[]
    for i in range(6):
        day=(dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)+dt.timedelta(days=i)).isoformat()
        games.append({"season":2026,"date":day,"away":"Away","home":"Home","awayScore":17+i,"homeScore":24+i})
    return {"games":games}

class ScoreResearchTests(unittest.TestCase):
    def test_no_data_fails_closed(self):
        self.assertEqual(project([],"Home","Away")["status"],"INSUFFICIENT_PRIOR_TEAM_GAMES")
    def test_no_qb_projection_without_verified_delta(self):
        p=project(prior(history(),dt.datetime(2026,9,10,tzinfo=dt.timezone.utc),2026),"Home","Away")
        self.assertEqual(p["models"]["C-QB"]["status"],"QB_ADJUSTMENT_NOT_VERIFIED")
        self.assertNotIn("projectedHomeScore",p["models"]["C-QB"])
        self.assertFalse(p["published"])
    def test_score_margin_and_total_consistent(self):
        p=project(prior(history(),dt.datetime(2026,9,10,tzinfo=dt.timezone.utc),2026),"Home","Away")
        for m in ("A","B","C"):
            r=p["models"][m]
            self.assertAlmostEqual(r["projectedHomeScore"]+r["projectedAwayScore"],r["projectedTotal"],places=1)
            self.assertAlmostEqual(r["projectedHomeScore"]-r["projectedAwayScore"],r["projectedMargin"],places=1)
            self.assertEqual(r["rating"],"NO BET")
    def test_future_history_not_used(self):
        rows=prior(history(),dt.datetime(2026,9,3,tzinfo=dt.timezone.utc),2026)
        self.assertEqual(len(rows),2)
        self.assertEqual(project(rows,"Home","Away")["status"],"INSUFFICIENT_PRIOR_TEAM_GAMES")
    def test_walkforward_is_unvalidated_and_no_qb(self):
        r=walkforward(history(),2026)
        self.assertEqual(r["C-QB"]["graded"],0)
        self.assertFalse(r["published"])
        self.assertEqual(r["metrics"]["A"]["graded"],2)

if __name__=="__main__":
    unittest.main()
