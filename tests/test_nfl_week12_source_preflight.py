"""Synthetic definitions for read-only source preflight; not executed."""
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_week12_source_preflight import inspect

NOW = dt.datetime(2026, 11, 25, 16, tzinfo=dt.timezone.utc)
GAME = {"id": "synthetic-1", "date": "2026-11-26T18:00:00Z",
        "home": "Home", "away": "Away"}


class SourcePreflightTests(unittest.TestCase):
    def setUp(self):
        self.schedule = {"season": 2026, "weeks": [{"week": 12, "games": [GAME]}]}
        self.draft = {"season": 2026, "week": 12, "generatedAt": "2026-11-25T15:55:00Z",
                      "games": [GAME]}
        self.shadow = {"season": 2026, "week": 12, "generatedAt": "2026-11-25T15:56:00Z",
                       "status": "EXPERIMENTAL_SHADOW_ONLY", "games": [GAME]}
        self.history = {"updatedAt": "2026-11-25T14:00:00Z"}
        self.qb_history = {"generatedAt": "2026-11-25T14:00:00Z"}
        self.starters = {"teams": {"Home": {"status": "CONFIRMED_STARTER"}}}

    def inspect(self):
        return inspect(self.schedule, self.draft, self.shadow, self.history,
                       self.qb_history, self.starters, NOW)

    def test_present_sources_not_claimed_authenticated(self):
        result = self.inspect()
        self.assertEqual(result["status"], "SOURCES_PRESENT_NOT_AUTHENTICATED")
        self.assertEqual(result["expectedModelRows"], 4)

    def test_week8_sources_block_week12(self):
        self.draft["week"] = 8
        self.shadow["week"] = 8
        result = self.inspect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("wrong season/week" in reason for reason in result["reasons"]))

    def test_stale_history_blocks(self):
        self.history["updatedAt"] = "2026-10-28T19:30:06Z"
        self.assertTrue(any("Historical results" in reason for reason in self.inspect()["reasons"]))

    def test_missing_starters_not_invented(self):
        self.starters["teams"] = {}
        self.assertTrue(any("No game-specific" in reason for reason in self.inspect()["reasons"]))

    def test_incomplete_game_coverage_blocks(self):
        self.shadow["games"] = []
        self.assertTrue(any("incomplete/mismatched" in reason for reason in self.inspect()["reasons"]))


if __name__ == "__main__":
    unittest.main()
