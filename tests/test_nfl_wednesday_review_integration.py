"""Offline integration checks for the Wednesday review workflow."""
import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from nfl_four_model_review_report import build, render


class WednesdayReviewIntegrationTests(unittest.TestCase):
    def test_dst_wednesday_cutoffs(self):
        eastern = ZoneInfo("America/New_York")
        winter = dt.datetime(2026, 11, 25, 11, tzinfo=eastern)
        summer = dt.datetime(2027, 6, 2, 11, tzinfo=eastern)
        self.assertEqual(winter.astimezone(dt.timezone.utc).hour, 16)
        self.assertEqual(summer.astimezone(dt.timezone.utc).hour, 15)

    def test_preflight_is_nonpublishing(self):
        workflow = (ROOT / ".github/workflows/nfl-four-model-review-preflight.yml").read_text()
        self.assertIn("contents: read", workflow)
        self.assertIn("20 15 * * 3", workflow)
        self.assertIn("20 16 * * 3", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("deploy-pages", workflow)

    def test_scheduled_delivery_keeps_archive_on_critical_path(self):
        workflow = (ROOT / ".github/workflows/model-c-draft.yml").read_text()
        self.assertIn("cron: '0 11 * * 3'\n      timezone: America/New_York", workflow)
        self.assertIn("model_c_engine.py --wednesday-review", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertLess(workflow.index("Verify archive completion marker"),
                        workflow.index("Upload one review-only archive"))
        self.assertLess(workflow.index("Upload one review-only archive"),
                        workflow.index("Discover official team QB news links"))

    def test_dashboard_loads_only_explicit_review_file(self):
        dashboard = (ROOT / "four-model-review.js").read_text()
        page = (ROOT / "index.html").read_text()
        self.assertIn("./data/four-model-review-latest.json", dashboard)
        self.assertIn('four-model-review.js', page)
        self.assertIn("REVIEW_ONLY_INCOMPLETE", dashboard)
        self.assertIn("NO BET", dashboard)
        self.assertIn("window.print()", dashboard)

    def test_report_does_not_change_input(self):
        card = {"season": 2026, "week": 12, "frozenAt": "2026-11-25T16:00:00Z",
                "games": [{"id": "synthetic", "date": "2026-11-26T18:00:00Z",
                           "home": "Home", "away": "Away",
                           "picks": {"A": "Home", "B": "Away", "C": "Home", "C-QB": "Home"}}]}
        import copy
        original = copy.deepcopy(card)
        report = build(card)
        self.assertEqual(card, original)
        self.assertIn("NOT OFFICIAL", render(report))
        self.assertEqual(report["sourceFrozenAt"], card["frozenAt"])


if __name__ == "__main__":
    unittest.main()
