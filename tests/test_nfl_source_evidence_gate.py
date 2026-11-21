import copy
import hashlib
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "research"))
from nfl_source_evidence_gate import verify

CUTOFF = "2026-11-04T16:00:00Z"
CAPTURE = "2026-11-04T15:45:00Z"

def sample():
    game = {"id": "week9-test-game", "home": "HOME", "away": "AWAY", "date": "2026-11-06T01:15:00Z"}
    raw = json.dumps({"season": 2026, "week": 9, "games": [game]}, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    a = {"source": "espn-archive", "raw": raw, "sha256": digest, "capturedAt": CAPTURE}
    b = {**a, "source": "nfl-official-archive"}
    qb = [{"gameId": game["id"], "side": side, "starter": "CONTROLLED_TEST_QB",
           "verification": "OFFICIAL_GAME_SPECIFIC", "source": "controlled-official-fixture",
           "capturedAt": CAPTURE} for side in ("home", "away")]
    market = {"season": 2026, "week": 9, "games": [
        {"id": game["id"], "provider": "controlled-book", "source": "controlled-fixture",
         "spread": -3.5, "total": 42.5, "capturedAt": CAPTURE}]}
    return dict(schedule_a=a, schedule_b=b, qb=qb, markets=market, cutoff=CUTOFF)

class EvidenceGateTests(unittest.TestCase):
    def assertRejected(self, args, message):
        with self.assertRaisesRegex(ValueError, message):
            verify(**args)

    def test_controlled_evidence_passes_research_only(self):
        result = verify(**sample())
        self.assertEqual(result["status"], "RESEARCH_EVIDENCE_PASS")
        self.assertFalse(result["productionReady"])

    def test_schedule_bytes_tampered(self):
        x = sample()
        x["schedule_a"]["raw"] += b" "
        self.assertRejected(x, "SOURCE_HASH_MISMATCH")

    def test_missing_schedule_hash(self):
        x = sample()
        x["schedule_a"]["sha256"] = ""
        self.assertRejected(x, "INVALID_HASH_EVIDENCE")

    def test_schedule_sources_not_independent(self):
        x = sample()
        x["schedule_b"]["source"] = x["schedule_a"]["source"]
        self.assertRejected(x, "INDEPENDENT_SOURCES_REQUIRED")

    def test_schedule_disagreement(self):
        x = sample()
        payload = json.loads(x["schedule_b"]["raw"])
        payload["games"][0]["home"] = "OTHER"
        x["schedule_b"]["raw"] = json.dumps(payload, sort_keys=True).encode()
        x["schedule_b"]["sha256"] = hashlib.sha256(x["schedule_b"]["raw"]).hexdigest()
        self.assertRejected(x, "SCHEDULE_DISAGREEMENT")

    def test_schedule_after_cutoff(self):
        x = sample()
        x["schedule_a"]["capturedAt"] = "2026-11-04T16:01:00Z"
        self.assertRejected(x, "EVIDENCE_OUTSIDE_CUTOFF_WINDOW")

    def test_stale_week8_market(self):
        x = sample()
        x["markets"]["week"] = 8
        self.assertRejected(x, "MARKET_WEEK_MISMATCH")

    def test_market_timestamp_after_cutoff(self):
        x = sample()
        x["markets"]["games"][0]["capturedAt"] = "2026-11-04T16:01:00Z"
        self.assertRejected(x, "EVIDENCE_OUTSIDE_CUTOFF_WINDOW")

    def test_market_missing_line(self):
        x = sample()
        del x["markets"]["games"][0]["total"]
        self.assertRejected(x, "MARKET_LINE_MISSING")

    def test_missing_market_game(self):
        x = sample()
        x["markets"]["games"] = []
        self.assertRejected(x, "MARKET_COVERAGE_MISSING")

    def test_missing_qb_side(self):
        x = sample()
        x["qb"].pop()
        self.assertRejected(x, "QB_EVIDENCE_MISSING")

    def test_qb_not_verified(self):
        x = sample()
        x["qb"][0]["verification"] = "UNVERIFIED"
        self.assertRejected(x, "QB_NOT_OFFICIALLY_VERIFIED")

    def test_qb_after_cutoff(self):
        x = sample()
        x["qb"][0]["capturedAt"] = "2026-11-04T16:01:00Z"
        self.assertRejected(x, "EVIDENCE_OUTSIDE_CUTOFF_WINDOW")

    def test_inputs_immutable(self):
        x = sample()
        original = copy.deepcopy(x)
        verify(**x)
        self.assertEqual(x, original)

if __name__ == "__main__":
    unittest.main()
