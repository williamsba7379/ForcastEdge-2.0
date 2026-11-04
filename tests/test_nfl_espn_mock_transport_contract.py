import copy
import json
import unittest
from scripts.nfl_espn_mock_transport_contract import evaluate
from scripts.nfl_future_history_sync_gate import sha

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def fixture():
    g={"id":"101","date":"2026-11-15T18:00:00Z","status":{"type":{"completed":True,"name":"STATUS_FINAL"}},
       "competitions":[{"competitors":[{"homeAway":"home","score":"21","team":{"displayName":"Home"}},
                                    {"homeAway":"away","score":"10","team":{"displayName":"Away"}}]}]}
    raw=json.dumps({"events":[g]}).encode()
    games=[{"id":"101","kickoff":"2026-11-15T18:00:00Z"}]
    manifest={"season":2026,"week":10,"provider":"INDEPENDENT_APPROVED_SCHEDULE",
              "observedAt":"2026-11-15T12:00:00Z","games":games,"scheduleSha256":sha(games)}
    response={"url":URL,"tlsVerified":True,"hostnameVerified":True,"redirectCount":0,"status":200,
              "timeoutSeconds":5,"raw":raw,"contentLength":len(raw),
              "startedAt":"2026-11-16T02:00:00Z","completedAt":"2026-11-16T02:00:01Z"}
    return response,manifest
def test(change=None):
    response,manifest=fixture()
    if change:change(response,manifest)
    return evaluate(response,manifest,2026,10,"2026-11-18T17:00:00Z")
class TransportTests(unittest.TestCase):
    def ok(self):self.assertEqual(test()["status"],"OFFLINE_TRANSPORT_VALIDATED")
    def blocked(self,change):self.assertEqual(test(change)["status"],"BLOCKED")
    def test_good(self):self.ok()
    def test_tls(self):self.blocked(lambda r,m:r.update(tlsVerified=False))
    def test_hostname(self):self.blocked(lambda r,m:r.update(hostnameVerified=False))
    def test_redirect(self):self.blocked(lambda r,m:r.update(redirectCount=1))
    def test_http_302(self):self.blocked(lambda r,m:r.update(status=302))
    def test_http(self):self.blocked(lambda r,m:r.update(url=URL.replace("https:","http:")))
    def test_spoof_host(self):self.blocked(lambda r,m:r.update(url=URL.replace("site.api.espn.com","site.api.espn.com.evil.test")))
    def test_wrong_week(self):self.blocked(lambda r,m:r.update(url=URL.replace("week=10","week=9")))
    def test_timeout(self):self.blocked(lambda r,m:r.update(timeoutSeconds=11))
    def test_long_capture(self):self.blocked(lambda r,m:r.update(completedAt="2026-11-16T02:00:20Z"))
    def test_late_capture(self):self.blocked(lambda r,m:r.update(completedAt="2026-11-19T02:00:01Z"))
    def test_size(self):self.blocked(lambda r,m:r.update(raw=b"x"*2000001))
    def test_content_length(self):self.blocked(lambda r,m:r.update(contentLength=4))
    def test_bad_schedule_provider(self):self.blocked(lambda r,m:m.update(provider="ESPN"))
    def test_bad_schedule_hash(self):self.blocked(lambda r,m:m.update(scheduleSha256="f"*64))
    def test_missing_game(self):
        def change(r,m):
            m["games"].append({"id":"102","kickoff":"2026-11-15T18:00:00Z"});m["scheduleSha256"]=sha(m["games"])
        self.blocked(change)
    def test_duplicate_schedule(self):
        def change(r,m):
            m["games"].append(copy.deepcopy(m["games"][0]));m["scheduleSha256"]=sha(m["games"])
        self.blocked(change)
    def test_late_schedule(self):self.blocked(lambda r,m:m.update(observedAt="2026-11-19T02:00:00Z"))
    def test_unfinished_game(self):
        def change(r,m):
            data=json.loads(r["raw"]);data["events"][0]["status"]["type"]["completed"]=False
            r["raw"]=json.dumps(data).encode();r["contentLength"]=len(r["raw"])
        self.blocked(change)
    def test_no_live_request(self):
        result=test();self.assertIs(result["liveRequestMade"],False);self.assertIs(result["promotionAuthorized"],False)
if __name__=="__main__":unittest.main()
