"""Standalone offline safeguard fixtures. No network, repository writes, or live capture."""
import copy
import hashlib
import json
import threading
import unittest
from nfl_future_evidence_safeguards import MemoryAppendOnlyEvidence

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
K="2026-11-08T18:00:00Z"
def fixture():
    schedule={"gameId":"401123456","season":2026,"week":10,"homeTeamId":"1","awayTeamId":"2","kickoffAt":K}
    event={"id":"401123456","season":{"year":2026},"week":{"number":10},"date":K,"status":{"type":{"completed":True}},"competitions":[{"competitors":[{"homeAway":"home","team":{"id":"1"},"score":"21"},{"homeAway":"away","team":{"id":"2"},"score":"17"}]}]}
    raw=json.dumps({"events":[event]},sort_keys=True)
    record={"gameId":"401123456","source":URL,"kickoffAt":K,"observedFinalAt":"2026-11-08T22:00:00Z","retrievedAt":"2026-11-08T22:01:00Z","rawResponse":raw,"contentSha256":hashlib.sha256(raw.encode()).hexdigest()}
    return record,schedule
def change_event(record,callback):
    payload=json.loads(record["rawResponse"]);callback(payload["events"][0])
    record["rawResponse"]=json.dumps(payload,sort_keys=True)
    record["contentSha256"]=hashlib.sha256(record["rawResponse"].encode()).hexdigest()
class SafeguardTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryAppendOnlyEvidence();self.record,self.schedule=fixture()
    def reject(self,expected):
        ok,reason=self.store.submit(self.record,self.schedule)
        self.assertFalse(ok);self.assertEqual(reason,expected);self.assertIsNone(self.store.get("401123456"))
    def test_valid(self):
        self.assertEqual(self.store.submit(self.record,self.schedule),(True,"FIRST_FINAL_OBSERVED"))
    def test_duplicate(self):
        self.store.submit(self.record,self.schedule)
        self.assertEqual(self.store.submit(self.record,self.schedule)[1],"EXISTING_FIRST_OBSERVATION_IMMUTABLE")
    def test_concurrent_duplicate(self):
        results=[];lock=threading.Lock()
        def worker():
            result=self.store.submit(self.record,self.schedule)
            with lock: results.append(result)
        threads=[threading.Thread(target=worker) for _ in range(16)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(ok for ok,_ in results),1)
    def test_caller_mutation_does_not_change_store(self):
        self.store.submit(self.record,self.schedule);original=self.store.get("401123456")
        self.record["rawResponse"]="changed"
        self.assertEqual(self.store.get("401123456"),original)
        fetched=self.store.get("401123456");fetched["rawResponse"]="changed"
        self.assertEqual(self.store.get("401123456"),original)
    def test_wrong_game_id(self):
        self.record["gameId"]="999";self.reject("GAME_ID_MISMATCH")
    def test_wrong_season(self):
        change_event(self.record,lambda e:e["season"].update(year=2025));self.reject("SEASON_WEEK_MISMATCH")
    def test_wrong_week(self):
        change_event(self.record,lambda e:e["week"].update(number=9));self.reject("SEASON_WEEK_MISMATCH")
    def test_wrong_team(self):
        change_event(self.record,lambda e:e["competitions"][0]["competitors"][0]["team"].update(id="9"));self.reject("TEAM_MISMATCH")
    def test_swapped_teams(self):
        change_event(self.record,lambda e:[t.update(homeAway=("away" if t["homeAway"]=="home" else "home")) for t in e["competitions"][0]["competitors"]]);self.reject("TEAM_MISMATCH")
    def test_supplied_kickoff_mismatch(self):
        self.record["kickoffAt"]="2026-11-08T19:00:00Z";self.reject("KICKOFF_MISMATCH")
    def test_event_kickoff_mismatch(self):
        change_event(self.record,lambda e:e.update(date="2026-11-08T19:00:00Z"));self.reject("EVENT_KICKOFF_MISMATCH")
    def test_missing_schedule(self):
        self.reject_missing_schedule()
    def reject_missing_schedule(self):
        self.assertEqual(self.store.submit(self.record,{})[0],False)
    def test_altered_raw_response(self):
        self.record["rawResponse"]+=" ";self.reject("CONTENT_HASH_MISMATCH")
    def test_missing_hash(self):
        del self.record["contentSha256"];self.reject("UNVERIFIABLE_EVIDENCE")
    def test_not_final(self):
        change_event(self.record,lambda e:e["status"]["type"].update(completed=False));self.reject("NOT_FINAL")
    def test_observed_before_kickoff(self):
        self.record["observedFinalAt"]="2026-11-08T17:59:00Z";self.reject("INCONSISTENT_TIMESTAMPS")
    def test_retrieved_before_observed(self):
        self.record["retrievedAt"]="2026-11-08T21:59:00Z";self.reject("INCONSISTENT_TIMESTAMPS")
    def test_unverified_delay(self):
        self.record["retrievedAt"]="2026-11-08T22:10:00Z";self.reject("OBSERVATION_DELAY_UNVERIFIED")
    def test_naive_timestamp(self):
        self.record["retrievedAt"]="2026-11-08T22:01:00";self.reject("UNVERIFIABLE_EVIDENCE")
    def test_untrusted_source(self):
        self.record["source"]="https://evil.example/scoreboard";self.reject("INVALID_SOURCE")
if __name__=="__main__":unittest.main()
