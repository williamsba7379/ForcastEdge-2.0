"""Offline design examples only: no real artifact verification, writes or production authority."""
import datetime as dt
from zoneinfo import ZoneInfo
import unittest

def design_review(request, evidence):
    reasons = []
    ids = request.get("game_ids", [])
    schedule = evidence.get("schedule_games", [])
    if not ids or len(set(ids)) != len(ids) or len(schedule) != len(ids) or {g.get("id") for g in schedule} != set(ids):
        reasons.append("INCOMPLETE_OR_DUPLICATE_SCHEDULE")
    if (request.get("season"), request.get("week")) != (evidence.get("season"), evidence.get("week")):
        reasons.append("STALE_WEEK")
    if not evidence.get("nfl_independent") or not evidence.get("espn_independent"):
        reasons.append("INDEPENDENT_SCHEDULE_UNVERIFIED")
    if not evidence.get("producer_success") or not evidence.get("source_artifact_authenticated"):
        reasons.append("PRODUCER_OR_ARTIFACT_UNVERIFIED")
    if not evidence.get("model_c_present") or not evidence.get("model_c_qb_present"):
        reasons.append("MODEL_EVIDENCE_MISSING")
    cutoff = request.get("cutoff")
    if not isinstance(cutoff, dt.datetime) or cutoff.tzinfo is None:
        reasons.append("INVALID_CUTOFF")
    else:
        cutoff_ny = cutoff.astimezone(ZoneInfo("America/New_York"))
        if cutoff_ny.weekday() != 2 or (cutoff_ny.hour, cutoff_ny.minute) != (11, 0):
            reasons.append("INVALID_WEDNESDAY_CUTOFF")
        for value in evidence.get("prediction_input_times", []):
            if value.tzinfo is None or value > cutoff:
                reasons.append("POST_CUTOFF_INPUT")
                break
    if evidence.get("market_join_source") == "latest_glob":
        reasons.append("UNSAFE_MARKET_SELECTION")
    if evidence.get("market_join_source") == "explicit_card" and not evidence.get("market_card_digest_matches"):
        reasons.append("MARKET_CARD_MISMATCH")
    if evidence.get("mode") != "PRODUCTION_CANDIDATE":
        reasons.append("RESEARCH_ONLY")
    return {"status": "NOT_READY" if reasons else "DESIGN_ACCEPTANCE_ONLY",
            "productionReady": False, "reasonCodes": reasons}

class WednesdayDependencyDesignTests(unittest.TestCase):
    def setUp(self):
        cutoff = dt.datetime(2026, 11, 11, 11, 0, tzinfo=ZoneInfo("America/New_York"))
        self.req = {"season": 2026, "week": 10, "game_ids": ["g1", "g2", "g3"], "cutoff": cutoff}
        self.ev = {"season": 2026, "week": 10, "schedule_games": [{"id": i} for i in self.req["game_ids"]],
                   "nfl_independent": True, "espn_independent": True,
                   "producer_success": True, "source_artifact_authenticated": True,
                   "model_c_present": True, "model_c_qb_present": True,
                   "prediction_input_times": [cutoff - dt.timedelta(minutes=1)],
                   "market_join_source": "explicit_card", "market_card_digest_matches": True,
                   "mode": "PRODUCTION_CANDIDATE"}

    def codes(self):
        return design_review(self.req, self.ev)["reasonCodes"]

    def test_dynamic_three_game_slate_design(self):
        self.assertEqual(self.codes(), [])
        self.assertFalse(design_review(self.req, self.ev)["productionReady"])

    def test_missing_game_fails(self):
        self.ev["schedule_games"].pop()
        self.assertIn("INCOMPLETE_OR_DUPLICATE_SCHEDULE", self.codes())

    def test_duplicate_expected_id_fails(self):
        self.req["game_ids"] = ["g1", "g1", "g3"]
        self.assertIn("INCOMPLETE_OR_DUPLICATE_SCHEDULE", self.codes())

    def test_missing_independent_nfl_source_fails(self):
        self.ev["nfl_independent"] = False
        self.assertIn("INDEPENDENT_SCHEDULE_UNVERIFIED", self.codes())

    def test_failed_producer_fails(self):
        self.ev["producer_success"] = False
        self.assertIn("PRODUCER_OR_ARTIFACT_UNVERIFIED", self.codes())

    def test_missing_qb_fails(self):
        self.ev["model_c_qb_present"] = False
        self.assertIn("MODEL_EVIDENCE_MISSING", self.codes())

    def test_post_cutoff_but_prekickoff_input_fails(self):
        self.ev["prediction_input_times"] = [self.req["cutoff"] + dt.timedelta(minutes=1)]
        self.assertIn("POST_CUTOFF_INPUT", self.codes())

    def test_latest_glob_market_fails(self):
        self.ev["market_join_source"] = "latest_glob"
        self.assertIn("UNSAFE_MARKET_SELECTION", self.codes())

    def test_wrong_card_digest_market_fails(self):
        self.ev["market_card_digest_matches"] = False
        self.assertIn("MARKET_CARD_MISMATCH", self.codes())

    def test_summer_dst_cutoff_is_11_am_ny(self):
        summer = dt.datetime(2026, 7, 8, 15, 0, tzinfo=dt.timezone.utc)
        self.req["cutoff"] = summer
        self.ev["prediction_input_times"] = [summer - dt.timedelta(minutes=1)]
        self.assertNotIn("INVALID_WEDNESDAY_CUTOFF", self.codes())

    def test_winter_dst_cutoff_is_11_am_ny(self):
        self.assertNotIn("INVALID_WEDNESDAY_CUTOFF", self.codes())

    def test_research_only_cannot_certify(self):
        self.ev["mode"] = "READ_ONLY_NO_FREEZE"
        self.assertIn("RESEARCH_ONLY", self.codes())

if __name__ == "__main__":
    unittest.main()
