import copy
import unittest
from scripts.nfl_future_history_sync_gate import gate,sha

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def fixture():
    report={"season":2026,"week":10,"status":"COMPLETE","gamesCompleted":2,"gamesRemaining":0,"scoreSource":URL,
      "results":[{"gameId":str(i),"date":"2026-11-15T18:00Z","home":"Home"+str(i),"away":"Away"+str(i),"homeScore":21,"awayScore":10,"winner":"Home"+str(i),"scoreSource":URL} for i in (101,102)]}
    manifest={"provider":"ESPN","sourceUrl":URL,"rawResponseSha256":"a"*64,"archiveCommit":"b"*40,
      "retrievedAt":"2026-11-16T02:00Z","archivedAt":"2026-11-16T03:00Z","reportSha256":sha(report)}
    return {"games":[{"season":2025,"week":1,"id":"old"}]},report,manifest,"2026-11-18T17:00Z",["101","102"]
def run(mutator=None):
    args=list(fixture())
    if mutator:mutator(args)
    return gate(*args)
class Tests(unittest.TestCase):
    def test_success_rollback_no_writes(self):
        args=fixture();original=copy.deepcopy(args[0]);result,candidate=gate(*args)
        self.assertEqual(result["status"],"RESEARCH_READY")
        self.assertEqual(result["addedCount"],2)
        self.assertEqual(args[0],original)
        self.assertEqual(len(candidate["games"]),3)
        self.assertFalse(result["promotionAuthorized"])
    def test_idempotent(self):
        args=fixture();r,c=gate(*args);r2,c2=gate(c,*args[1:])
        self.assertEqual(r2["addedCount"],0);self.assertEqual(r["candidateSha256"],r2["candidateSha256"])
    def test_duplicate_ids(self):
        self.assertEqual(run(lambda a:a[1]["results"][1].update(gameId="101"))[0]["status"],"BLOCKED")
    def test_missing_final(self):
        self.assertEqual(run(lambda a:a[1]["results"].pop())[0]["status"],"BLOCKED")
    def test_conflicting_score(self):
        def change(a):
            a[0]["games"].append({"season":2026,"week":10,"id":"101","date":"2026-11-15T18:00Z","home":"Home101","away":"Away101","homeScore":99,"awayScore":10,"winner":"Home101"})
        self.assertEqual(run(change)[0]["status"],"BLOCKED")
    def test_negative_score(self):
        self.assertEqual(run(lambda a:a[1]["results"][0].update(homeScore=-1))[0]["status"],"BLOCKED")
    def test_winner_mismatch(self):
        self.assertEqual(run(lambda a:a[1]["results"][0].update(winner="Away101"))[0]["status"],"BLOCKED")
    def test_wrong_game_source(self):
        self.assertEqual(run(lambda a:a[1]["results"][0].update(scoreSource="https://other.com"))[0]["status"],"BLOCKED")
    def test_invalid_provider(self):
        self.assertEqual(run(lambda a:a[2].update(provider="unknown"))[0]["status"],"BLOCKED")
    def test_missing_raw_hash(self):
        self.assertEqual(run(lambda a:a[2].update(rawResponseSha256=""))[0]["status"],"BLOCKED")
    def test_archive_late(self):
        self.assertEqual(run(lambda a:a[2].update(archivedAt="2026-11-19T00:00Z"))[0]["status"],"BLOCKED")
    def test_retrieval_later_than_archive(self):
        self.assertEqual(run(lambda a:a[2].update(retrievedAt="2026-11-17T00:00Z"))[0]["status"],"BLOCKED")
    def test_report_hash_mismatch(self):
        self.assertEqual(run(lambda a:a[1]["results"][0].update(homeScore=22))[0]["status"],"BLOCKED")
    def test_duplicate_existing_history(self):
        self.assertEqual(run(lambda a:a[0]["games"].append(copy.deepcopy(a[0]["games"][0])))[0]["status"],"BLOCKED")
    def test_future_game(self):
        self.assertEqual(run(lambda a:a[1]["results"][0].update(date="2026-11-20T00:00Z"))[0]["status"],"BLOCKED")
    def test_missing_archive_commit(self):
        self.assertEqual(run(lambda a:a[2].update(archiveCommit=""))[0]["status"],"BLOCKED")
if __name__=="__main__":unittest.main()
