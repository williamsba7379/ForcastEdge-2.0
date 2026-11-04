import copy
import unittest
from scripts.nfl_week9_in_memory_repair import prepare
from scripts.nfl_week9_history_sync_provenance import SOURCE

def sample():
    results=[{"gameId":str(1000+i),"date":"2026-11-01T18:00Z","home":"H"+str(i),"away":"A"+str(i),"homeScore":20,"awayScore":10,"winner":"H"+str(i),"scoreSource":SOURCE} for i in range(14)]
    report={"season":2026,"week":8,"status":"COMPLETE","gamesCompleted":14,"gamesRemaining":0,"results":results}
    history={"games":[]}
    frozen={"frozenAt":"2026-11-04T17:18:26+00:00"}
    return report,history,frozen
def run(r,h,f,stamp="2026-11-03T05:08:17+00:00",blob="a"*40):
    return prepare(r,h,f,stamp,blob)
class Tests(unittest.TestCase):
    def test_complete_in_memory(self):
        r,h,f=sample();x,c=run(r,h,f)
        self.assertEqual(x["addedCount"],14);self.assertEqual(x["status"],"RESEARCH_READY")
        self.assertEqual(len(h["games"]),0);self.assertEqual(len(c["games"]),14)
        self.assertFalse(x["promotionAuthorized"])
    def test_hash_rollback(self):
        r,h,f=sample();x,c=run(r,h,f)
        self.assertNotEqual(x["originalHistorySha256"],x["candidateSha256"])
        self.assertEqual(len(h["games"]),0)
    def test_replay_idempotent(self):
        r,h,f=sample();x,c=run(r,h,f);y,d=run(r,c,f)
        self.assertEqual(y["addedCount"],0);self.assertEqual(y["candidateSha256"],x["candidateSha256"])
    def test_existing_history_preserved(self):
        r,h,f=sample();h["games"].append({"season":2025,"id":"old","week":1})
        x,c=run(r,h,f);self.assertEqual(c["games"][0],h["games"][0])
    def test_conflicting_score_blocks(self):
        r,h,f=sample();h["games"].append({"season":2026,"id":"1000","week":8,"homeScore":999})
        x,c=run(r,h,f);self.assertEqual(x["status"],"BLOCKED");self.assertEqual(x["addedCount"],0)
    def test_duplicate_source_blocks(self):
        r,h,f=sample();r["results"][1]["gameId"]="1000"
        self.assertEqual(run(r,h,f)[0]["status"],"BLOCKED")
    def test_duplicate_history_blocks(self):
        r,h,f=sample();h["games"]=[{"season":2026,"id":"1000"},{"season":2026,"id":"1000"}]
        self.assertEqual(run(r,h,f)[0]["status"],"BLOCKED")
    def test_future_commit_blocks(self):
        r,h,f=sample();self.assertEqual(run(r,h,f,"2026-11-05T00:00:00+00:00")[0]["status"],"BLOCKED")
    def test_future_game_blocks(self):
        r,h,f=sample();r["results"][0]["date"]="2026-11-05T18:00Z"
        self.assertEqual(run(r,h,f)[0]["status"],"BLOCKED")
    def test_source_change_blocks(self):
        r,h,f=sample();r["results"][0]["scoreSource"]="https://example.org"
        self.assertEqual(run(r,h,f)[0]["status"],"BLOCKED")
    def test_missing_blob_blocks(self):
        r,h,f=sample();self.assertEqual(run(r,h,f,blob="")[0]["status"],"BLOCKED")
    def test_incomplete_blocks(self):
        r,h,f=sample();r["gamesCompleted"]=13
        self.assertEqual(run(r,h,f)[0]["status"],"BLOCKED")
if __name__=="__main__":unittest.main()
