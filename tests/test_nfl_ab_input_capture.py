import hashlib
import unittest
from scripts.nfl_ab_input_capture import capture
from scripts.nfl_ab_strict_replay import replay
from scripts.nfl_team_strength import team_metrics

CUTOFF="2026-11-04T16:46:43Z"
SEEN="2026-11-04T16:40:00Z"
def board(url):
    # One completed game in each of two prior weeks; subsequent weeks empty.
    from urllib.parse import parse_qs,urlparse
    week=int(parse_qs(urlparse(url).query)["week"][0])
    if week>2:return {"events":[]}
    return {"events":[{"id":str(week),"date":"2026-09-%02dT18:00:00Z"%(10+week),
        "status":{"type":{"completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":"Home"},"score":"24"},
            {"homeAway":"away","team":{"displayName":"Away"},"score":"14"}]}]}]}
def frozen():
    return {"frozenAt":CUTOFF,"season":2026,"games":[
        {"id":"next","date":"2026-11-06T01:15:00Z","home":"Home","away":"Away",
         "baseline30Pick":"Home","experimental0Pick":"Home"}]}
class CaptureTests(unittest.TestCase):
    def test_real_team_metrics_replay(self):
        snap=capture(board,2026,CUTOFF,SEEN)
        self.assertEqual(len(snap["observations"]),2)
        self.assertEqual(replay(snap,frozen(),team_metrics),
                         [{"id":"next","A":"Home","B":"Home"}])
        self.assertEqual(snap["observations"][0]["finalObservationType"],"FIRST_OBSERVED_BY_COLLECTOR")
    def test_late_capture_rejected(self):
        with self.assertRaisesRegex(ValueError,"AFTER_CUTOFF"):
            capture(board,2026,CUTOFF,"2026-11-04T17:00:00Z")
    def test_unverified_final_type_rejected(self):
        snap=capture(board,2026,CUTOFF,SEEN)
        del snap["observations"][0]["finalObservationType"]
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_FINAL_OBSERVATION_TYPE"):
            replay(snap,frozen(),team_metrics)
    def test_unfinished_games_ignored(self):
        def empty(url):return {"events":[{"id":"1","status":{"type":{"completed":False}}}]}
        self.assertEqual(capture(empty,2026,CUTOFF,SEEN)["observations"],[])
    def test_tampered_score_rejected(self):
        snap=capture(board,2026,CUTOFF,SEEN)
        snap["observations"][0]["game"]["homeScore"]=99
        with self.assertRaisesRegex(ValueError,"HASH"):
            replay(snap,frozen(),team_metrics)
if __name__=="__main__":unittest.main()
