"""Synthetic null-passer regression definitions. Not executed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model_c_qb_injury_audit_v2 import build


class NullHistoricalPasserTests(unittest.TestCase):
    def setUp(self):
        self.game = {"id": "synthetic", "date": "2026-11-26T18:00:00Z",
                     "home": "Home", "away": "Away",
                     "quarterbacks": {"home": {"reportedQuarterbacks": [
                         {"name": "Known QB", "status": "out"}]}}}
        self.draft = {"season": 2026, "week": 12, "games": [self.game]}
        self.shadow = {"games": [{"id": "synthetic", "qbAdjustments": {
            "home": {"status": "NO_ADJUSTMENT"}, "away": {"status": "NO_ADJUSTMENT"}}}]}

    def test_null_historical_passer_does_not_crash_or_count(self):
        history = {"records": [
            {"team": "Home", "primaryPasser": None, "gameDate": "2026-11-01T18:00:00Z"},
            {"team": "Home", "primaryPasser": "Known QB", "gameDate": "2026-11-02T18:00:00Z"}]}
        result = build(self.draft, self.shadow, history)
        self.assertEqual(result["alerts"][0]["priorPrimaryPasserGames"]["Known QB"], 1)
        self.assertEqual(result["alerts"][0]["pointsAdjustment"], 0)

    def test_missing_reported_name_never_becomes_verified(self):
        self.game["quarterbacks"]["home"]["reportedQuarterbacks"] = [
            {"name": None, "status": "out"}]
        result = build(self.draft, self.shadow, {"records": []})
        self.assertEqual(result["alerts"][0]["priorPrimaryPasserGames"], {})
        self.assertEqual(result["alerts"][0]["priority"], "P2_ROLE_REVIEW_REQUIRED")

    def test_null_historical_date_does_not_crash(self):
        result = build(self.draft, self.shadow, {"records": [
            {"team": "Home", "primaryPasser": "Known QB", "gameDate": None}]})
        self.assertEqual(result["alerts"][0]["priorPrimaryPasserGames"]["Known QB"], 0)


if __name__ == "__main__":
    unittest.main()
