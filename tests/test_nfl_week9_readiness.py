import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_week9_readiness import validate

NOW = dt.datetime(2026, 11, 4, 17, 0, tzinfo=dt.timezone.utc)

def fixtures():
    names = [(f"Away{i}", f"Home{i}") for i in range(15)]
    draft = {"week":"2026 NFL Week 9 — UNREVIEWED AUTO DRAFT",
             "games":[{"away":a,"home":h,"date":"2026-11-08","time":"13:00"} for a,h in names]}
    c = {"season":2026,"week":9,"status":"AUTOMATED_REVIEW_ONLY","generatedAt":"2026-11-04T16:00:00Z",
         "games":[{"id":str(i),"away":a,"home":h,"date":"2026-11-08T18:00:00Z",
                   "pick":h,"homeEdgePoints":1} for i,(a,h) in enumerate(names)]}
    qb = {"season":2026,"week":9,"status":"EXPERIMENTAL_SHADOW_ONLY","generatedAt":"2026-11-04T16:00:00Z",
          "games":[{"id":str(i),"away":a,"home":h,"date":"2026-11-08T18:00:00Z",
                    "originalPick":h,"originalHomeEdgePoints":1,
                    "qbAdjustments":{"home":{"status":"NO_ADJUSTMENT","points":0},
                                     "away":{"status":"NO_ADJUSTMENT","points":0}}}
                   for i,(a,h) in enumerate(names)]}
    return draft,c,qb

class ReadinessTests(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(validate(*fixtures(),NOW), [])
    def test_stale_week(self):
        d,c,q=fixtures();c["week"]=8
        self.assertIn("C_STALE_OR_WRONG_WEEK",validate(d,c,q,NOW))
    def test_missing_game(self):
        d,c,q=fixtures();q["games"].pop()
        self.assertIn("C-QB_NOT_15",validate(d,c,q,NOW))
    def test_duplicate(self):
        d,c,q=fixtures();d["games"][1]=copy.deepcopy(d["games"][0])
        self.assertIn("SCHEDULE_DUPLICATE_OR_MISSING_TEAM",validate(d,c,q,NOW))
    def test_future_timestamp(self):
        d,c,q=fixtures();c["generatedAt"]="2026-11-05T16:00:00Z"
        self.assertIn("C_TIMESTAMP_STALE_OR_FUTURE",validate(d,c,q,NOW))
    def test_unverified_qb(self):
        d,c,q=fixtures();q["games"][0]["qbAdjustments"]["home"]["points"]=3
        self.assertIn("QB_UNVERIFIED_ADJUSTMENT",validate(d,c,q,NOW))
    def test_baseline_tampering(self):
        d,c,q=fixtures();q["games"][0]["originalPick"]="Other"
        self.assertIn("C_QB_BASELINE_CHANGED",validate(d,c,q,NOW))
    def test_kickoff_passed(self):
        d,c,q=fixtures()
        self.assertIn("SCHEDULE_KICKOFF_PASSED",validate(d,c,q,dt.datetime(2026,11,9,tzinfo=dt.timezone.utc)))
if __name__ == "__main__": unittest.main()
