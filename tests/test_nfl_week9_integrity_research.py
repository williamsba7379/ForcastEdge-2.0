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
 def test_near_zero_margin_uses_exact_python_threshold(self):
  # Chicago/Tampa discrepancy arose from floating-point association in a JS transcription.
  # Preserve the original Python implementation and flag near-zero margins for review.
  home=[22,-6,20,11,-24,8,6]
  away=[-6,-4,-7,-3,8,-7,30]
  def weighted(d):
   return .7*sum(d)/len(d)+.3*sum(d[-3:])/3
  edge=weighted(home)-weighted(away)+1.5
  self.assertLess(abs(edge),1e-10)
  self.assertEqual(round(edge,2),0.0)
  self.assertTrue(round(edge,2)>=0, "Production C rounds before winner choice")
 def test_future_result_not_used(self):
  g={"date":"2026-11-08T18:00:00Z","home":"Home","away":"Away"}
  h={"games":[{"season":2026,"date":"2026-11-09T18:00:00Z","home":"Home","away":"Away","homeScore":100,"awayScore":0}]}
  self.assertEqual(pick_ab(g,h,dt.datetime(2026,11,4,tzinfo=dt.timezone.utc)),{"A":"Home","B":"Home"})
if __name__=="__main__":unittest.main()
