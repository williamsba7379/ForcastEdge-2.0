import copy
import json
import unittest
from scripts.nfl_espn_trusted_capture_offline import inspect_response

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def event(i):
    return {"id":str(i),"date":"2026-11-15T18:00:00Z","status":{"type":{"completed":True,"name":"STATUS_FINAL"}},"competitions":[{"competitors":[{"homeAway":"home","score":"21","team":{"displayName":"Home"+str(i)}},{"homeAway":"away","score":"10","team":{"displayName":"Away"+str(i)}}]}]}
def fixture():
    return [URL,{"events":[event(101),event(102)]},"2026-11-16T03:00:00Z","2026-11-18T17:00:00Z",2026,10,["101","102"]]
def execute(change=None):
    args=fixture()
    if change:change(args)
    args[1]=json.dumps(args[1]).encode()
    return inspect_response(*args)
class CaptureTests(unittest.TestCase):
    def test_valid(self):
        x=execute();self.assertEqual(x["status"],"CAPTURE_VALIDATED_OFFLINE");self.assertEqual(len(x["results"]),2);self.assertFalse(x["promotionAuthorized"])
    def test_digest(self):
        import hashlib
        x=execute();self.assertEqual(x["rawResponseSha256"],hashlib.sha256(json.dumps(fixture()[1]).encode()).hexdigest())
    def test_missing(self):
        self.assertEqual(execute(lambda a:a[1]["events"].pop())["status"],"BLOCKED")
    def test_duplicate(self):
        self.assertEqual(execute(lambda a:a[1]["events"][1].update(id="101"))["status"],"BLOCKED")
    def test_unfinished(self):
        self.assertEqual(execute(lambda a:a[1]["events"][0]["status"]["type"].update(completed=False))["status"],"BLOCKED")
    def test_bad_status(self):
        self.assertEqual(execute(lambda a:a[1]["events"][0]["status"]["type"].update(name="STATUS_IN_PROGRESS"))["status"],"BLOCKED")
    def test_wrong_score(self):
        self.assertEqual(execute(lambda a:a[1]["events"][0]["competitions"][0]["competitors"][0].update(score="-1"))["status"],"BLOCKED")
    def test_tie(self):
        self.assertEqual(execute(lambda a:a[1]["events"][0]["competitions"][0]["competitors"][0].update(score="10"))["status"],"BLOCKED")
    def test_late_capture(self):
        self.assertEqual(execute(lambda a:a.__setitem__(2,"2026-11-19T00:00:00Z"))["status"],"BLOCKED")
    def test_future_game(self):
        self.assertEqual(execute(lambda a:a[1]["events"][0].update(date="2026-11-20T18:00:00Z"))["status"],"BLOCKED")
    def test_http(self):
        self.assertEqual(execute(lambda a:a.__setitem__(0,URL.replace("https:","http:")))["status"],"BLOCKED")
    def test_spoofed_host(self):
        self.assertEqual(execute(lambda a:a.__setitem__(0,URL.replace("site.api.espn.com","site.api.espn.com.evil.test")))["status"],"BLOCKED")
    def test_wrong_week(self):
        self.assertEqual(execute(lambda a:a.__setitem__(0,URL.replace("week=10","week=9")))["status"],"BLOCKED")
    def test_wrong_expected_ids(self):
        self.assertEqual(execute(lambda a:a.__setitem__(6,["101","999"]))["status"],"BLOCKED")
    def test_naive_time(self):
        self.assertEqual(execute(lambda a:a.__setitem__(2,"2026-11-16T03:00:00"))["status"],"BLOCKED")
    def test_malformed_bytes(self):
        args=fixture();self.assertEqual(inspect_response(args[0],b"invalid",*args[2:])["status"],"BLOCKED")
    def test_duplicate_expected_ids(self):
        self.assertEqual(execute(lambda a:a.__setitem__(6,["101","101"]))["status"],"BLOCKED")
if __name__=="__main__":unittest.main()
