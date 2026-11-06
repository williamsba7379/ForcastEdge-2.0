import datetime as dt
import hashlib
import unittest
from scripts.nfl_ab_strict_replay import canonical,replay

CUTOFF="2026-11-04T16:46:43Z"
def fixture():
    games=[]
    observations=[]
    for i in range(4):
        game={"id":str(i),"date":"2026-10-%02dT18:00:00Z"%(10+i),
              "season":2026,"home":"Home","away":"Away","homeScore":27,"awayScore":17,"completed":True}
        observations.append({"game":game,"sourceUrl":"https://example.org/verified",
                             "observedFinalAt":"2026-10-%02dT22:00:00Z"%(10+i),
                             "retrievedAt":"2026-10-%02dT23:00:00Z"%(10+i),
                             "sha256":hashlib.sha256(canonical(game)).hexdigest()})
    frozen={"frozenAt":CUTOFF,"season":2026,"games":[{"id":"target","date":"2026-11-06T01:15:00Z",
        "home":"Home","away":"Away","baseline30Pick":"Home","experimental0Pick":"Home"}]}
    def metrics(rows,team):
        return {"games":len(rows),"pointDifferential":10 if team=="Home" else -10,
                "recentDifferential":10 if team=="Home" else -10}
    return {"observations":observations},frozen,metrics
class StrictReplayTests(unittest.TestCase):
    def test_replay_identical_winners(self):
        self.assertEqual(replay(*fixture()),[{"id":"target","A":"Home","B":"Home"}])
    def test_late_retrieval_rejected(self):
        a,b,m=fixture();a["observations"][0]["retrievedAt"]="2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"FUTURE"):replay(a,b,m)
    def test_missing_observed_final_rejected(self):
        a,b,m=fixture();del a["observations"][0]["observedFinalAt"]
        with self.assertRaisesRegex(ValueError,"PROVENANCE"):replay(a,b,m)
    def test_modified_score_rejected(self):
        a,b,m=fixture();a["observations"][0]["game"]["homeScore"]=99
        with self.assertRaisesRegex(ValueError,"HASH"):replay(a,b,m)
    def test_future_final_rejected(self):
        a,b,m=fixture();a["observations"][0]["observedFinalAt"]="2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"FUTURE"):replay(a,b,m)
    def test_mismatched_archived_pick_rejected(self):
        a,b,m=fixture();b["games"][0]["experimental0Pick"]="Away"
        with self.assertRaisesRegex(ValueError,"MISMATCH"):replay(a,b,m)
if __name__=="__main__":unittest.main()
