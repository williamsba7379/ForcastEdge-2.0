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
         "scheduleCapture":{"responseSha256":digest(schedule),"completedAtUtc":before},
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
    a["syntheticSeal"]={"sealedAtUtc":p["cutoffUtc"]}
    a["syntheticSeal"]["bindingSha256"]=digest(canonical({
        "capturePayloadSha256":digest(raw),"scheduleSha256":digest(schedule),
        "sealedAtUtc":p["cutoffUtc"],"kind":"SYNTHETIC_TEST_ONLY"}))
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



class AdversarialTests(unittest.TestCase):
    def test_before_cutoff_one_ms(self):
        p,r,s=fixture();p["responses"][0]["responseCompletedUtc"]="2026-10-28T14:59:59.999Z"
        self.assertTrue(run(p,r,s)["passed"])
    def test_started_after_completion(self):
        p,r,s=fixture();p["responses"][0]["requestStartedUtc"]="2026-10-28T15:00:00.000Z"
        self.assertIn("E007_TIME_CONFLICT",run(p,r,s)["errors"])
    def test_unverified_schedule_digest(self):
        p,r,s=fixture();p["scheduleSha256"]="0"*64
        self.assertIn("E014_SCHEDULE_INVALID",run(p,r,s)["errors"])
    def test_duplicate_schedule_game(self):
        import json
        p,r,s=fixture();d=json.loads(s);d["events"].append(copy.deepcopy(d["events"][0]))
        s=canonical(d);p["scheduleSha256"]=digest(s);p["scheduleCapture"]["responseSha256"]=digest(s)
        self.assertIn("E010_GAME_DUPLICATE",run(p,r,s)["errors"])
    def test_pending_excluded(self):
        import json
        p,r,s=fixture();d=json.loads(s)
        d["events"].append({"id":"synthetic-pending","homeTeamId":"C","awayTeamId":"D","kickoffUtc":"2026-10-29T00:00:00.000Z","state":"PENDING"})
        s=canonical(d);p["scheduleSha256"]=digest(s);p["scheduleCapture"]["responseSha256"]=digest(s);p["excludedGameIds"]=["synthetic-pending"]
        self.assertTrue(run(p,r,s)["passed"])
    def test_pending_included(self):
        import json
        p,r,s=fixture();d=json.loads(s);d["events"][0]["state"]="PENDING"
        s=canonical(d);p["scheduleSha256"]=digest(s)
        self.assertIn("E013_COVERAGE_UNEXPECTED",run(p,r,s)["errors"])
    def test_untrusted_source_url(self):
        p,r,s=fixture();p["responses"][0]["url"]="https://site.api.espn.com"
        self.assertIn("E018_ISOLATION_VIOLATION",run(p,r,s)["errors"])
    def test_noncanonical_payload(self):
        import json
        p,r,s=fixture();raw=json.dumps(p,indent=2).encode()
        a={"capturePayloadSha256":digest(raw),"scheduleSha256":digest(s),"kind":"SYNTHETIC_TEST_ONLY","proof":"SYNTHETIC_VALID","timingClassification":"SYNTHETIC_VERIFIED"}
        self.assertIn("E002_CANONICAL_INVALID",validate(raw,r,s,a)["errors"])
    def test_duplicate_json_key(self):
        p,r,s=fixture();raw=canonical(p).replace(b'"freezeDate":',b'"freezeDate":"2026-10-28","freezeDate":',1)
        a={"capturePayloadSha256":digest(raw),"scheduleSha256":digest(s),"kind":"SYNTHETIC_TEST_ONLY","proof":"SYNTHETIC_VALID","timingClassification":"SYNTHETIC_VERIFIED"}
        self.assertIn("E001_SCHEMA_INVALID",validate(raw,r,s,a)["errors"])
    def test_malformed_timestamp(self):
        p,r,s=fixture();p["responses"][0]["responseCompletedUtc"]="2026-10-28T15:00:00Z"
        self.assertIn("E007_TIME_CONFLICT",run(p,r,s)["errors"])
    def test_conflicting_source_score(self):
        import json
        p,r,s=fixture();d=json.loads(r["r1"]);d["events"][0]["competitions"][0]["competitors"][0]["score"]=27
        r["r1"]=canonical(d);p["responses"][0]["sha256"]=digest(r["r1"]);p["responses"][0]["byteLength"]=len(r["r1"])
        self.assertIn("E011_GAME_CONFLICT",run(p,r,s)["errors"])
    def test_artifact_wrong_bytes(self):
        p,r,s=fixture();raw=canonical(p)
        a={"capturePayloadSha256":digest(raw),"scheduleSha256":digest(s),"kind":"SYNTHETIC_TEST_ONLY","proof":"SYNTHETIC_VALID","timingClassification":"SYNTHETIC_VERIFIED","artifactSha256":digest(b"expected")}
        self.assertIn("E016_ARTIFACT_INVALID",validate(raw,r,s,a,b"actual")["errors"])


class EvidenceGapTests(unittest.TestCase):
    def test_schedule_after_cutoff(self):
        p,r,s=fixture();p["scheduleCapture"]["completedAtUtc"]="2026-10-28T15:00:00.001Z"
        self.assertIn("E005_CAPTURE_LATE",run(p,r,s)["errors"])
    def test_missing_schedule_capture(self):
        p,r,s=fixture();del p["scheduleCapture"]
        self.assertIn("E014_SCHEDULE_INVALID",run(p,r,s)["errors"])
    def test_seal_wrong_digest(self):
        p,r,s=fixture()
        self.assertIn("E017_ATTESTATION_INVALID",run(p,r,s,{"syntheticSeal":{"sealedAtUtc":p["cutoffUtc"],"bindingSha256":"0"*64}})["errors"])
    def test_seal_after_cutoff(self):
        p,r,s=fixture();seal={"sealedAtUtc":"2026-10-28T15:00:00.001Z"}
        seal["bindingSha256"]=digest(canonical({"capturePayloadSha256":digest(canonical(p)),"scheduleSha256":digest(s),"sealedAtUtc":seal["sealedAtUtc"],"kind":"SYNTHETIC_TEST_ONLY"}))
        self.assertIn("E005_CAPTURE_LATE",run(p,r,s,{"syntheticSeal":seal})["errors"])
    def test_unsafe_integer_rejected(self):
        from research.ab_snapshot.validator import EvidenceError
        with self.assertRaises(EvidenceError): canonical({"x":9007199254740992})
    def test_unicode_utf16_key_order(self):
        self.assertEqual(canonical({"\\U0001f600":1,"\\ue000":2}), '{"😀":1,"":2}'.encode())
    def test_multi_response_conflict(self):
        import json
        p,r,s=fixture()
        other=json.loads(r["r1"]);other["events"][0]["competitions"][0]["competitors"][0]["score"]=99
        r["r2"]=canonical(other)
        second=copy.deepcopy(p["responses"][0]);second["responseId"]="r2";second["sha256"]=digest(r["r2"]);second["byteLength"]=len(r["r2"])
        p["responses"].append(second)
        self.assertIn("E011_GAME_CONFLICT",run(p,r,s)["errors"])
    def test_unsupported_retention_proof(self):
        p,r,s=fixture()
        self.assertIn("E016_ARTIFACT_INVALID",run(p,r,s,{"retentionProof":"unverified-external-claim"})["errors"])

if __name__ == "__main__":
    unittest.main()
