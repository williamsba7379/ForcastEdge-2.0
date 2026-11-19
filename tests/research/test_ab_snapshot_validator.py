"""Synthetic-only tests: no network, no production imports, no live score data."""
import copy
import unittest
from datetime import datetime, timezone
from research.ab_snapshot.validator import canonical, digest, validate, cutoff

def fixture(day="2026-10-28"):
    limit = cutoff(day)
    stamp = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    before = stamp(limit.replace(minute=59, hour=limit.hour-1))
    game = {"id":"synthetic-001","status":{"type":{"completed":True}},
            "competitions":[{"competitors":[
                {"homeAway":"home","team":{"id":"H"},"score":24},
                {"homeAway":"away","team":{"id":"A"},"score":17}]}]}
    raw = canonical({"events":[game]})
    schedule = canonical({"events":[{"id":"synthetic-001","homeTeamId":"H","awayTeamId":"A",
        "kickoffUtc":"2026-10-25T17:00:00.000Z","state":"FINAL"}]})
    p = {"schemaVersion":"1.2-synthetic","purpose":"research-ab-score-snapshot",
         "freezeDate":day,"cutoffUtc":stamp(limit),"scheduleSha256":digest(schedule),
         "excludedGameIds":[],
         "responses":[{"responseId":"r1","url":"synthetic://scoreboard",
                       "requestStartedUtc":before,"responseCompletedUtc":before,
                       "sha256":digest(raw),"byteLength":len(raw)}],
         "games":[{"gameId":"synthetic-001","responseId":"r1",
                   "homeTeamId":"H","awayTeamId":"A",
                   "kickoffUtc":"2026-10-25T17:00:00.000Z",
                   "homeScore":24,"awayScore":17,"winnerTeamId":"H"}]}
    return p, {"r1":raw}, schedule

def run(p, responses, schedule, attestation_overrides=None):
    raw = canonical(p)
    a = {"capturePayloadSha256":digest(raw),"scheduleSha256":digest(schedule),
         "kind":"SYNTHETIC_TEST_ONLY","proof":"SYNTHETIC_VALID",
         "timingClassification":"SYNTHETIC_VERIFIED"}
    a.update(attestation_overrides or {})
    return validate(raw, responses, schedule, a)

class ValidatorTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(run(*fixture())["errors"], [])
    def test_cutoff_dst(self):
        for day, hour in [("2026-03-04",16),("2026-03-11",15),
                          ("2026-10-28",15),("2026-11-04",16)]:
            self.assertEqual(cutoff(day).hour, hour)
    def test_exact_boundary(self):
        p, r, s = fixture()
        p["responses"][0]["responseCompletedUtc"] = p["cutoffUtc"]
        self.assertTrue(run(p,r,s)["passed"])
    def test_late(self):
        p, r, s = fixture()
        p["responses"][0]["responseCompletedUtc"] = "2026-10-28T15:00:00.001Z"
        self.assertIn("E005_CAPTURE_LATE",run(p,r,s)["errors"])
    def test_tampered_response(self):
        p, r, s = fixture()
        r["r1"] += b" "
        self.assertIn("E003_SOURCE_HASH_MISMATCH",run(p,r,s)["errors"])
    def test_missing_response(self):
        p, r, s = fixture()
        self.assertIn("E004_SOURCE_MISSING",run(p,{},s)["errors"])
    def test_claimed_time(self):
        p, r, s = fixture()
        self.assertIn("E006_TIME_UNVERIFIED",run(p,r,s,{"timingClassification":"CLAIMED"})["errors"])
    def test_invalid_attestation(self):
        p, r, s = fixture()
        self.assertIn("E017_ATTESTATION_INVALID",run(p,r,s,{"proof":"FORGED"})["errors"])
    def test_missing_final(self):
        p, r, s = fixture()
        e = {"events":[{"id":"synthetic-001","status":{"type":{"completed":False}},
            "competitions":[{"competitors":[{"homeAway":"home","team":{"id":"H"},"score":24},
            {"homeAway":"away","team":{"id":"A"},"score":17}]}]}]}
        r["r1"]=canonical(e);p["responses"][0]["sha256"]=digest(r["r1"]);p["responses"][0]["byteLength"]=len(r["r1"])
        self.assertIn("E008_STATUS_NOT_FINAL",run(p,r,s)["errors"])
    def test_duplicate(self):
        p, r, s = fixture()
        p["games"].append(copy.deepcopy(p["games"][0]))
        self.assertIn("E010_GAME_DUPLICATE",run(p,r,s)["errors"])
    def test_conflict(self):
        p, r, s = fixture()
        p["games"][0]["homeScore"]=28
        self.assertIn("E011_GAME_CONFLICT",run(p,r,s)["errors"])
    def test_missing_coverage(self):
        p, r, s = fixture()
        p["games"]=[]
        self.assertIn("E012_COVERAGE_MISSING",run(p,r,s)["errors"])
    def test_unexpected_game(self):
        p, r, s = fixture()
        p["games"][0]["gameId"]="synthetic-999"
        self.assertIn("E013_COVERAGE_UNEXPECTED",run(p,r,s)["errors"])
    def test_bad_schedule(self):
        p, r, s = fixture()
        self.assertIn("E014_SCHEDULE_INVALID",run(p,r,s+b" ")["errors"])
    def test_bad_payload(self):
        p, r, s = fixture()
        self.assertIn("E015_PAYLOAD_HASH_MISMATCH",run(p,r,s,{"capturePayloadSha256":"0"*64})["errors"])
    def test_artifact_missing(self):
        p, r, s = fixture()
        self.assertIn("E016_ARTIFACT_INVALID",run(p,r,s,{"artifactSha256":"0"*64})["errors"])

if __name__ == "__main__":
    unittest.main()
