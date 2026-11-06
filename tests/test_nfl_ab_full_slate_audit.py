"""Offline full-slate tests using production team_metrics, not mocked model scores."""
import base64
import hashlib
import json
import unittest
from scripts.nfl_ab_input_capture import capture
from scripts.nfl_ab_full_slate_audit import audit

CUTOFF="2026-11-04T16:00:00Z"
TEAMS=["Team %02d"%i for i in range(30)]

def fixture():
    def fetch(url):
        from urllib.parse import parse_qs,urlparse
        week=int(parse_qs(urlparse(url).query)["week"][0])
        events=[]
        if week<=2:
            for i in range(15):
                home,away=TEAMS[i*2:i*2+2]
                events.append({"id":str(week*100+i),"date":"2026-09-%02dT18:00:00Z"%(10+week),
                    "status":{"type":{"completed":True}},
                    "competitions":[{"competitors":[
                        {"homeAway":"home","team":{"displayName":home},"score":"24"},
                        {"homeAway":"away","team":{"displayName":away},"score":"14"}]}]})
        body=json.dumps({"events":events}).encode()
        return {"payload":{"events":events},
                "retrievedAt":"2026-11-04T15:%02d:00Z"%week,
                "rawBodyBase64":base64.b64encode(body).decode(),
                "responseSha256":hashlib.sha256(body).hexdigest()}
    snap=capture(fetch,2026,CUTOFF)
    slate=[{"id":"future-%02d"%i,"season":2026,"date":"2026-11-08T18:00:00Z",
            "home":TEAMS[2*i],"away":TEAMS[2*i+1]} for i in range(15)]
    return snap,slate

class FullSlateTests(unittest.TestCase):
    def test_all_15_games_independently_calculated(self):
        snap,slate=fixture()
        result=audit(snap,slate,CUTOFF,[g["id"] for g in slate])
        self.assertEqual(result["coverage"],15)
        self.assertEqual(len({r["id"] for r in result["games"]}),15)
        self.assertTrue(all(r["home_history_games"]==2 and r["away_history_games"]==2 for r in result["games"]))
        self.assertTrue(all(r["A"]==r["home"] and r["B"]==r["home"] for r in result["games"]))
        self.assertTrue(all(r["status"]=="RESEARCH_ONLY_NO_BET" for r in result["games"]))
    def test_missing_schedule_game_rejected(self):
        snap,slate=fixture()
        with self.assertRaisesRegex(ValueError,"SCHEDULE_COVERAGE_MISMATCH"):
            audit(snap,slate[:-1],CUTOFF,[g["id"] for g in slate])
    def test_duplicate_schedule_game_rejected(self):
        snap,slate=fixture()
        with self.assertRaisesRegex(ValueError,"SCHEDULE_COVERAGE_MISMATCH"):
            audit(snap,slate+[slate[0]],CUTOFF,[g["id"] for g in slate])
    def test_postcutoff_capture_rejected(self):
        snap,slate=fixture()
        snap["responses"][0]["retrievedAt"]="2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"RESPONSE_AFTER_CUTOFF"):
            audit(snap,slate,CUTOFF,[g["id"] for g in slate])
    def test_changed_raw_response_rejected(self):
        snap,slate=fixture()
        snap["responses"][0]["rawBodyBase64"]=base64.b64encode(b"{}").decode()
        with self.assertRaisesRegex(ValueError,"RAW_ESPN_HASH_MISMATCH"):
            audit(snap,slate,CUTOFF,[g["id"] for g in slate])
    def test_insufficient_team_history_rejected(self):
        snap,slate=fixture()
        slate[0]["home"]="Unknown Team"
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_VERIFIED_HISTORY"):
            audit(snap,slate,CUTOFF,[g["id"] for g in slate])
    def test_no_week9_replay_from_november6_capture(self):
        snap,slate=fixture()
        with self.assertRaisesRegex(ValueError,"RESPONSE_AFTER_CUTOFF"):
            audit(snap,slate,"2026-09-01T00:00:00Z",[g["id"] for g in slate])
    def test_tampered_normalized_score_rejected(self):
        snap,slate=fixture()
        snap["observations"][0]["game"]["homeScore"]=99
        with self.assertRaisesRegex(ValueError,"GAME_HASH_MISMATCH"):
            audit(snap,slate,CUTOFF,[g["id"] for g in slate])
if __name__=="__main__":
    unittest.main()
