import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from nfl_week9_integrity_research import build_rows,pick_ab,SCORES

class IntegrityTests(unittest.TestCase):
 def test_scores_unique(self):
  self.assertEqual(len(SCORES),14)
  self.assertEqual(len({(a,h) for a,h,_,_ in SCORES}),14)
 def test_no_original_timestamps_invented(self):
  week8={"games":[{"id":str(i),"date":"2026-11-01T18:00:00Z","away":a,"home":h} for i,(a,h,_,_) in enumerate(SCORES)]}
  rows=build_rows(week8)
  self.assertEqual(len(rows),14)
  self.assertTrue(all(x["finalizationTimestamp"] is None and x["originalRetrievalTimestamp"] is None and x["availabilityAtWeek9Freeze"]=="UNPROVEN" for x in rows))
 def test_future_result_not_used(self):
  g={"date":"2026-11-08T18:00:00Z","home":"Home","away":"Away"}
  h={"games":[{"season":2026,"date":"2026-11-09T18:00:00Z","home":"Home","away":"Away","homeScore":100,"awayScore":0}]}
  self.assertEqual(pick_ab(g,h,dt.datetime(2026,11,4,tzinfo=dt.timezone.utc)),{"A":"Home","B":"Home"})
if __name__=="__main__":unittest.main()
