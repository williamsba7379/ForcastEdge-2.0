"""Focused synthetic checks for nonpublishing four-model review report. Not executed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_four_model_review_report import build, render, MISSING


class ReviewReportTests(unittest.TestCase):
    def setUp(self):
        self.card = {
            "season": 2026, "week": 12, "status": "FRESH_PREKICKOFF_SNAPSHOT",
            "frozenAt": "2026-11-25T16:00:00Z",
            "games": [{
                "id": "synthetic-1", "date": "2026-11-26T18:00:00Z",
                "home": "Home", "away": "Away",
                "picks": {"A": "Home", "B": "Away", "C": "Home", "C-QB": "Home"}
            }]
        }

    def test_four_independent_winners_retained(self):
        rows = build(self.card)["games"][0]["models"]
        self.assertEqual([rows[m]["winner"] for m in ("A", "B", "C", "C-QB")],
                         ["Home", "Away", "Home", "Home"])

    def test_no_fabricated_lines_or_confidence(self):
        rows = build(self.card)["games"][0]["models"]
        for m in rows.values():
            self.assertEqual(m["spread"], MISSING)
            self.assertEqual(m["overUnder"], MISSING)
            self.assertEqual(m["confidence"], MISSING)
            self.assertEqual(m["wagerStatus"], "NO BET")

    def test_optional_research_score_is_labeled(self):
        research = {"season": 2026, "week": 12, "games": [
            {"id": "synthetic-1", "models": {"A": {
                "projectedHome": 23.5, "projectedAway": 20.5,
                "status": "EXPERIMENTAL_UNCALIBRATED"}}}]}
        row = build(self.card, research)["games"][0]["models"]
        self.assertEqual(row["A"]["projectedHome"], 23.5)
        self.assertEqual(row["B"]["projectedHome"], MISSING)
        self.assertEqual(row["A"]["projectionStatus"], "EXPERIMENTAL_UNCALIBRATED")

    def test_mismatched_research_rejected(self):
        with self.assertRaisesRegex(ValueError, "Research week mismatch"):
            build(self.card, {"season": 2026, "week": 11, "games": []})

    def test_missing_model_rejected(self):
        del self.card["games"][0]["picks"]["C-QB"]
        with self.assertRaisesRegex(ValueError, "four independent"):
            build(self.card)

    def test_printable_html_escapes_input(self):
        self.card["games"][0]["home"] = "<script>"
        self.card["games"][0]["picks"]["A"] = "<script>"
        self.card["games"][0]["picks"]["C"] = "<script>"
        self.card["games"][0]["picks"]["C-QB"] = "<script>"
        page = render(build(self.card))
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("window.print()", page)
        self.assertIn("NOT OFFICIAL", page)


if __name__ == "__main__":
    unittest.main()
