"""Offline, isolated tests for read-only current-week input preflight."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research.nfl_current_week_input_preflight import check

NOW = dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc)
GAME = {"id": "g1", "date": "2026-11-13T01:15:00Z",
        "home": "Home", "away": "Away", "status": "STATUS_SCHEDULED"}

class InputPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {
            "nfl-schedule.json": {"season": 2026, "weeks": [{"week": 10, "games": [GAME]}]},
            "nfl-historical-results.json": {"games": [{"id": "old", "season": 2026,
                "date": "2026-11-02T01:00:00Z"}]},
            "model-c-automated-draft.json": {"season": 2026, "week": 10,
                "generatedAt": "2026-11-11T15:50:00Z", "games": [GAME]},
            "model-c-qb-shadow.json": {"season": 2026, "week": 10,
                "generatedAt": "2026-11-11T15:50:00Z", "games": [GAME]},
            "model-c-qb-reviewed-announcements.json": {"entries": []},
            "model-c-qb-starters.json": {"teams": {}},
        }
    def run_check(self):
        for name, obj in self.files.items():
            (self.root / name).write_text(json.dumps(obj))
        return check(self.root, NOW)
    def codes(self, result):
        return [i["code"] for i in result["issues"]]
    def test_week_and_game_mismatch(self):
        self.files["model-c-automated-draft.json"]["week"] = 8
        self.files["model-c-qb-shadow.json"]["games"] = []
        result = self.run_check()
        self.assertIn("MODEL_WEEK_MISMATCH", self.codes(result))
        self.assertIn("MODEL_GAME_IDS_MISMATCH", self.codes(result))
        self.assertFalse(result["wednesdayHandoffReady"])
    def test_missing_completed_historical_game(self):
        self.files["nfl-schedule.json"]["weeks"][0]["games"][0]["status"] = "FINAL"
        self.assertIn("MISSING_COMPLETED_HISTORY", self.codes(self.run_check()))
    def test_missing_official_qb_evidence(self):
        result = self.run_check()
        self.assertEqual(2, self.codes(result).count("QB_OFFICIAL_CONFIRMATION_MISSING"))
        self.assertEqual(2, self.codes(result).count("QB_VERIFIED_INTAKE_MISSING"))
    def test_read_only_and_blocked(self):
        result = self.run_check()
        self.assertEqual("BLOCKED_MISSING_INPUTS", result["status"])
        self.assertFalse(result["published"])
        self.assertTrue(result["readOnly"])
        self.assertFalse(result["wednesdayHandoffReady"])
    def test_no_write_operations(self):
        self.run_check()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.run_check()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

if __name__ == "__main__":
    unittest.main()
