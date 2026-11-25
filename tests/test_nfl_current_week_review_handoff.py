"""Offline regressions for the current-week review handoff."""
import copy
import datetime as dt
import sys
import unittest
from unittest.mock import patch
from io import StringIO
from urllib.parse import parse_qs, urlsplit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_current_week_review_handoff import prepare
from nfl_four_model_head_to_head import freeze
from nfl_four_model_totals_research import build_from_draft
from nfl_market_totals_compare import compare
from nfl_market_totals_feed import collect

NOW = dt.datetime(2026, 11, 25, 16, 5, tzinfo=dt.timezone.utc)
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

    def test_reject_before_window(self):
        with self.assertRaisesRegex(ValueError, "cannot precede 11 AM"):
            self.run_handoff(dt.datetime(2026, 11, 25, 15, 59, tzinfo=dt.timezone.utc))

    def test_delayed_output_not_on_time(self):
        report = self.run_handoff(dt.datetime(2026, 11, 25, 16, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(report["deliveryTiming"], "AFTER_11AM_NOT_ON_TIME")


    def projections(self):
        self.history["games"] = [
            {"date": f"2026-11-{day:02d}T19:00:00Z", "season": 2026,
             "home": "Home", "away": "Away", "homeScore": 24, "awayScore": 17}
            for day in (1, 8, 15)
        ]
        card = freeze(self.draft, self.shadow, self.history, NOW)
        with patch("nfl_four_model_totals_research.dt.datetime", wraps=dt.datetime) as clock:
            clock.now.return_value = NOW
            return build_from_draft(card, self.history, self.draft)

    def test_review_contains_validated_experimental_scores(self):
        projections = self.projections()
        report = prepare(self.schedule, self.draft, self.shadow, self.history, NOW, projections)
        for model, pick in report["games"][0]["models"].items():
            expected = projections["games"][0]["models"][model]
            self.assertEqual(pick["projectedHome"], expected["projectedHome"])
            self.assertEqual(pick["projectedAway"], expected["projectedAway"])
            self.assertEqual(pick["wagerStatus"], "NO BET")

    def test_reject_altered_or_wrong_week_projections(self):
        projections = self.projections()
        altered = copy.deepcopy(projections)
        altered["games"][0]["models"]["C"]["projectedHome"] += 1
        wrong_week = dict(projections, week=11)
        for report in (altered, wrong_week, dict(projections, games=[])):
            with self.subTest(report=report):
                with self.assertRaisesRegex(ValueError, "same-run model inputs"):
                    prepare(self.schedule, self.draft, self.shadow, self.history, NOW, report)

    def test_reject_future_projections(self):
        projections = self.projections()
        projections["generatedAt"] = (NOW + dt.timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "Projection timestamps"):
            prepare(self.schedule, self.draft, self.shadow, self.history, NOW, projections)

    def test_espn_query_and_capture_timestamp(self):
        payload = StringIO('{"events":[{"id":"synthetic-1","competitions":'
                           '[{"odds":[{"overUnder":44.5,"provider":{"name":"Fixture"}}]}]}]}')
        capture = NOW - dt.timedelta(seconds=1)
        with patch("nfl_market_totals_feed.urllib.request.urlopen", return_value=payload) as fetch:
            with patch("nfl_market_totals_feed.dt.datetime", wraps=dt.datetime) as clock:
                clock.now.return_value = capture
                market = collect(self.draft)
        request = fetch.call_args.args[0]
        self.assertEqual(parse_qs(urlsplit(request.full_url).query),
                         {"dates": ["2026"], "seasontype": ["2"], "week": ["12"]})
        quote = market["games"][0]
        self.assertEqual(quote["source"], request.full_url)
        self.assertEqual(quote["capturedAt"], capture.isoformat())
        result = compare(self.projections(), market)
        self.assertEqual(result["games"][0]["models"]["A"]["marketCapturedAt"], capture.isoformat())
        quote["capturedAt"] = (NOW + dt.timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "later than frozen"):
            compare(self.projections(), market)


if __name__ == "__main__":
    unittest.main()
