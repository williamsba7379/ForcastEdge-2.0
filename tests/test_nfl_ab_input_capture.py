import base64
import hashlib
import json
import unittest
from scripts.nfl_ab_input_capture import capture
from scripts.nfl_ab_strict_replay import replay
from scripts.nfl_team_strength import team_metrics

CUTOFF="2026-11-04T16:46:43Z"
SEEN="2026-11-04T16:40:00Z"

def response(events):
    body=json.dumps({"events":events}).encode()
    return {"payload":{"events":events},"retrievedAt":SEEN,
            "rawBodyBase64":base64.b64encode(body).decode("ascii"),
            "responseSha256":hashlib.sha256(body).hexdigest()}

def board(url):
    from urllib.parse import parse_qs,urlparse
    week=int(parse_qs(urlparse(url).query)["week"][0])
    if week>2:
        return response([])
    return response([{"id":str(week),"date":"2026-09-%02dT18:00:00Z"%(10+week),
        "status":{"type":{"completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":"Home"},"score":"24"},
            {"homeAway":"away","team":{"displayName":"Away"},"score":"14"}]}]}])

def frozen():
    return {"frozenAt":CUTOFF,"season":2026,"games":[
        {"id":"next","date":"2026-11-06T01:15:00Z","home":"Home","away":"Away",
         "baseline30Pick":"Home","experimental0Pick":"Home"}]}

class CaptureTests(unittest.TestCase):
    def test_real_team_metrics_replay(self):
        snap=capture(board,2026,CUTOFF)
        self.assertEqual(len(snap["observations"]),2)
        self.assertEqual(replay(snap,frozen(),team_metrics),
                         [{"id":"next","A":"Home","B":"Home"}])
        self.assertEqual(snap["observations"][0]["finalObservationType"],"FIRST_OBSERVED_BY_COLLECTOR")
    def test_late_capture_rejected(self):
        def late(url):
            result=board(url)
            result["retrievedAt"]="2026-11-04T17:00:00Z"
            return result
        with self.assertRaisesRegex(ValueError,"AFTER_CUTOFF"):
            capture(late,2026,CUTOFF)
    def test_unverified_final_type_rejected(self):
        snap=capture(board,2026,CUTOFF)
        del snap["observations"][0]["finalObservationType"]
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_FINAL_OBSERVATION_TYPE"):
            replay(snap,frozen(),team_metrics)
    def test_unfinished_games_ignored(self):
        def empty(url):
            return response([{"id":"1","status":{"type":{"completed":False}}}])
        self.assertEqual(capture(empty,2026,CUTOFF)["observations"],[])
    def test_tampered_score_rejected(self):
        snap=capture(board,2026,CUTOFF)
        snap["observations"][0]["game"]["homeScore"]=99
        with self.assertRaisesRegex(ValueError,"HASH"):
            replay(snap,frozen(),team_metrics)

if __name__=="__main__":
    unittest.main()
