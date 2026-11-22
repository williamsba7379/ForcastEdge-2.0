"""Synthetic test definitions for current-week handoff. Not executed."""
import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_current_week_review_handoff import prepare

NOW = dt.datetime(2026, 11, 25, 15, 55, tzinfo=dt.timezone.utc)
KICKOFF = "2026-11-26T18:00:00Z"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        game = {"id": "synthetic-1", "date": KICKOFF, "home": "Home", "away": "Away"}
        self.schedule = {"season": 2026, "weeks": [{"week": 12, "games": [game]}]}
        self.draft = {"season": 2026, "week": 12, "generatedAt": "2026-11-25T15:50:00Z",
                      "games": [{**game, "pick": "Home", "homeEdgePoints": 1.5}]}
        self.shadow = {"season": 2026, "week": 12, "generatedAt": "2026-11-25T15:51:00Z",
                       "status": "EXPERIMENTAL_SHADOW_ONLY",
                       "games": [{**game, "originalPick": "Home", "originalHomeEdgePoints": 1.5,
                                  "experimentalPick": "Away", "qbHomeEdgeAdjustment": -2.0,
                                  "qbAdjustments": {"home": {"status": "NO_ADJUSTMENT"},
                                                    "away": {"status": "NO_ADJUSTMENT"}}}]}
        self.history = {"games": []}

    def run_handoff(self, now=NOW):
        return prepare(self.schedule, self.draft, self.shadow, self.history, now)

    def test_all_four_models_preserved_as_review_only(self):
        before = copy.deepcopy((self.draft, self.shadow, self.history))
        report = self.run_handoff()
        picks = report["games"][0]["models"]
        self.assertEqual([picks[m]["winner"] for m in ("A", "B", "C", "C-QB")],
                         ["Home", "Home", "Home", "Away"])
        self.assertEqual(report["status"], "REVIEW_ONLY_INCOMPLETE")
        self.assertIsNone(report["sourceFrozenAt"])
        self.assertEqual(before, (self.draft, self.shadow, self.history))
        self.assertTrue(all(p["wagerStatus"] == "NO BET" for p in picks.values()))

    def test_reject_stale_model_c(self):
        self.draft["generatedAt"] = "2026-11-24T01:00:00Z"
        with self.assertRaisesRegex(ValueError, "stale"):
            self.run_handoff()

    def test_reject_wrong_week(self):
        self.shadow["week"] = 11
        with self.assertRaisesRegex(ValueError, "week mismatch"):
            self.run_handoff()

    def test_reject_missing_game(self):
        self.shadow["games"] = []
        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            self.run_handoff()

    def test_reject_wrong_kickoff(self):
        self.shadow["games"][0]["date"] = "2026-11-27T18:00:00Z"
        with self.assertRaisesRegex(ValueError, "matchup/kickoff mismatch"):
            self.run_handoff()

    def test_reject_after_cutoff(self):
        with self.assertRaisesRegex(ValueError, "Past Wednesday"):
            self.run_handoff(dt.datetime(2026, 11, 25, 16, 1, tzinfo=dt.timezone.utc))


if __name__ == "__main__":
    unittest.main()
