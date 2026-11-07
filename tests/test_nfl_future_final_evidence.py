"""Offline fixtures: no HTTP, no historical archive, no production writes."""
import datetime as dt
import json
import unittest
from nfl_future_final_evidence import capture
from nfl_historical_availability_audit import validate

UTC=dt.timezone.utc
K=dt.datetime(2026,11,8,18,0,tzinfo=UTC)
R=dt.datetime(2026,11,8,22,0,tzinfo=UTC)
N=dt.datetime(2026,11,8,22,1,tzinfo=UTC)
URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def raw(completed=True, score="21", game="401123456"):
    return json.dumps({"events":[{"id":game,"status":{"type":{"completed":completed}},
      "competitions":[{"competitors":[{"homeAway":"home","score":score},
      {"homeAway":"away","score":"17"}]}]}]}).encode()

def run(**kw):
    args=dict(game_id="401123456",kickoff_at=K,source=URL,
              raw_response=raw(),retrieved_at=R,now=N)
    args.update(kw)
    return capture(**args)

class FutureEvidenceTests(unittest.TestCase):
    def test_first_final_and_validator_compatible(self):
        record,reason=run()
        self.assertEqual(reason,"FIRST_FINAL_OBSERVED")
        self.assertEqual(validate(record,"2026-11-09T00:00:00Z")[0],True)
    def test_not_final(self):
        self.assertEqual(run(raw_response=raw(False))[1],"NOT_FINAL")
    def test_wrong_game(self):
        self.assertEqual(run(raw_response=raw(game="999"))[1],"GAME_ID_NOT_UNIQUE")
    def test_missing_score(self):
        self.assertEqual(run(raw_response=raw(score=""))[1],"MISSING_FINAL_SCORE")
    def test_untrusted_host(self):
        self.assertEqual(run(source="https://evil.example/scoreboard")[1],"UNTRUSTED_SOURCE")
    def test_insecure_source(self):
        self.assertEqual(run(source=URL.replace("https","http"))[1],"UNTRUSTED_SOURCE")
    def test_stale_retrieval(self):
        self.assertEqual(run(retrieved_at=R-dt.timedelta(minutes=10))[1],"STALE_OR_FUTURE_RETRIEVAL")
    def test_future_retrieval(self):
        self.assertEqual(run(retrieved_at=N+dt.timedelta(seconds=1))[1],"STALE_OR_FUTURE_RETRIEVAL")
    def test_before_kickoff(self):
        self.assertEqual(run(now=K,retrieved_at=K)[1],"BEFORE_KICKOFF")
    def test_immutable_first(self):
        self.assertEqual(run(previous={"gameId":"401123456"})[1],"EXISTING_FIRST_OBSERVATION_IMMUTABLE")
    def test_malformed_json(self):
        self.assertEqual(run(raw_response=b"broken")[1],"UNVERIFIABLE_RESPONSE")
    def test_missing_events(self):
        self.assertEqual(run(raw_response=b'{}')[1],"MISSING_EVENTS")
    def test_naive_time(self):
        self.assertEqual(run(now=N.replace(tzinfo=None))[1],"UNVERIFIABLE_RESPONSE")
    def test_missing_raw(self):
        self.assertEqual(run(raw_response=b"")[1],"INVALID_RAW_RESPONSE")

if __name__=="__main__":
    unittest.main()
