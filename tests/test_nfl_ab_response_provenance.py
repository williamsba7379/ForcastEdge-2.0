import base64
import hashlib
import json
import unittest
from scripts.nfl_ab_input_capture import capture
from scripts.nfl_ab_strict_replay import replay
from scripts.nfl_team_strength import team_metrics

def fixture():
    calls=[]
    def fetch(url):
        from urllib.parse import parse_qs,urlparse
        week=int(parse_qs(urlparse(url).query)["week"][0])
        now="2026-11-04T15:%02d:00Z"%week
        events=[]
        if week<=2:
            events=[{"id":str(week),"date":"2026-09-%02dT18:00:00Z"%(10+week),
                "status":{"type":{"completed":True}},
                "competitions":[{"competitors":[
                    {"homeAway":"home","team":{"displayName":"Home"},"score":"24"},
                    {"homeAway":"away","team":{"displayName":"Away"},"score":"14"}]}]}]
        body=json.dumps({"events":events}).encode()
        calls.append(now)
        return {"payload":{"events":events},"retrievedAt":now,
                "rawBodyBase64":base64.b64encode(body).decode(),
                "responseSha256":hashlib.sha256(body).hexdigest()}
    snap=capture(fetch,2026,"2026-11-04T16:00:00Z")
    frozen={"frozenAt":"2026-11-04T16:00:00Z","season":2026,"games":[
        {"id":"next","date":"2026-11-06T01:15:00Z","home":"Home","away":"Away",
         "baseline30Pick":"Home","experimental0Pick":"Home"}]}
    return snap,frozen

class ResponseProvenanceTests(unittest.TestCase):
    def test_each_week_uses_its_own_retrieval_timestamp(self):
        snap,_=fixture()
        self.assertNotEqual(snap["responses"][0]["retrievedAt"],snap["responses"][1]["retrievedAt"])
        self.assertEqual(snap["observations"][0]["retrievedAt"],snap["responses"][0]["retrievedAt"])
    def test_raw_response_hashes_and_real_metrics(self):
        snap,frozen=fixture()
        self.assertEqual(replay(snap,frozen,team_metrics),[{"id":"next","A":"Home","B":"Home"}])
    def test_tampered_raw_response_rejected(self):
        snap,frozen=fixture()
        snap["responses"][0]["rawBodyBase64"]=base64.b64encode(b"{}").decode()
        with self.assertRaisesRegex(ValueError,"RAW_ESPN_HASH_MISMATCH"):
            replay(snap,frozen,team_metrics)
    def test_modified_retrieval_timestamp_rejected(self):
        snap,frozen=fixture()
        snap["observations"][0]["retrievedAt"]="2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"LINK_MISMATCH"):
            replay(snap,frozen,team_metrics)
    def test_response_after_cutoff_rejected(self):
        def fetch(url):
            return {"payload":{"events":[]},"retrievedAt":"2026-11-05T00:00:00Z"}
        with self.assertRaisesRegex(ValueError,"CAPTURE_AFTER_CUTOFF"):
            capture(fetch,2026,"2026-11-04T16:00:00Z")
if __name__=="__main__":unittest.main()
