import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/three_market_evaluation.py"
spec = importlib.util.spec_from_file_location("three_market_evaluation", SCRIPT)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.p = dict(game_id="1", home_id="H", away_id="A", model="M",
                      start_utc="2026-10-31T19:00:00Z", frozen_at_utc="2026-10-31T16:00:00Z",
                      winner_id="H", projected_margin=5, projected_total=45, wagering_status="NO_BET")
        self.r = {k: self.p[k] for k in ("game_id", "home_id", "away_id", "start_utc")}
        self.r.update(final=True, home_points=27, away_points=20)
        self.m = {k: self.p[k] for k in ("game_id", "home_id", "away_id", "start_utc")}
        self.m.update(source="https://example.org/odds", bookmaker="test", home_spread=-3,
                      total_points=46, captured_at_utc="2026-10-31T15:30:00Z", spread_convention="SIGNED_HOME")

    def run_grade(self):
        return ev.evaluate([self.p], [self.r], [self.m])

    def test_separate_categories_and_errors(self):
        summary = self.run_grade()["summary"]["M"]
        self.assertEqual(summary["winner"]["wins"], 1)
        self.assertEqual(summary["spread"]["wins"], 1)
        self.assertEqual(summary["total"]["losses"], 1)
        self.assertEqual(summary["margin_mae"], 2)
        self.assertEqual(summary["total_mae"], 2)

    def test_home_favorite_cover_sign(self):
        self.m["home_spread"] = -10
        row = self.run_grade()["rows"][0]
        self.assertEqual(row["spread"]["research_direction"], "AWAY")
        self.assertEqual(row["spread"]["status"], "WIN")

    def test_home_underdog_sign(self):
        self.p["projected_margin"] = -5
        self.m["home_spread"] = 3
        self.r.update(home_points=20, away_points=21)
        self.assertEqual(self.run_grade()["rows"][0]["spread"]["status"], "LOSS")

    def test_pushes_excluded_from_accuracy(self):
        self.m.update(home_spread=-7, total_points=47)
        summary = self.run_grade()["summary"]["M"]
        for category in ("spread", "total"):
            self.assertEqual(summary[category]["pushes"], 1)
            self.assertIsNone(summary[category]["accuracy"])

    def test_no_direction_is_not_loss(self):
        self.m.update(home_spread=-5, total_points=45)
        self.assertEqual(self.run_grade()["rows"][0]["spread"]["status"], "NO_DIRECTION")
        self.assertEqual(self.run_grade()["summary"]["M"]["total"]["losses"], 0)

    def test_no_bet_never_actionable_loss(self):
        self.assertEqual(self.run_grade()["summary"]["M"]["actionable_wagers"], 0)
        self.assertEqual(self.run_grade()["wagering_status"], "NO_BET")
        self.p["wagering_status"] = "EDGE"
        with self.assertRaises(ValueError):
            self.run_grade()

    def test_pending_and_missing_do_not_count_as_losses(self):
        report = ev.evaluate([self.p])
        self.assertEqual(report["rows"][0]["winner"]["status"], "PENDING_RESULT")
        self.assertEqual(report["summary"]["M"]["winner"]["losses"], 0)

    def test_empty_prediction_set_fails(self):
        with self.assertRaises(ValueError):
            ev.evaluate([])

    def test_missing_market_keeps_mae(self):
        report = ev.evaluate([self.p], [self.r])
        self.assertEqual(report["rows"][0]["spread"]["status"], "MISSING_MARKET")
        self.assertEqual(report["summary"]["M"]["margin_mae"], 2)

    def test_partial_market_keeps_valid_category(self):
        del self.m["home_spread"]
        row = self.run_grade()["rows"][0]
        self.assertEqual(row["spread"]["status"], "MISSING_MARKET_FIELD")
        self.assertEqual(row["total"]["status"], "LOSS")

    def test_market_time_boundaries(self):
        for captured, status in (("2026-10-31T19:00:00Z", "POST_START_MARKET"),
                                 ("2026-10-31T17:00:00Z", "MARKET_AFTER_FORECAST"),
                                 ("2026-10-29T16:00:00Z", "STALE_MARKET")):
            self.m["captured_at_utc"] = captured
            self.assertEqual(self.run_grade()["rows"][0]["spread"]["status"], status)

    def test_market_requires_source_and_signed_spread(self):
        del self.m["spread_convention"]
        self.assertEqual(self.run_grade()["rows"][0]["spread"]["status"], "UNVERIFIED_SPREAD_SIGN")
        del self.m["source"]
        self.assertEqual(self.run_grade()["rows"][0]["total"]["status"], "MISSING_MARKET_PROVENANCE")

    def test_game_team_and_start_must_match(self):
        self.m["away_id"] = "OTHER"
        self.assertEqual(self.run_grade()["rows"][0]["total"]["status"], "MARKET_GAME_MISMATCH")
        self.r["start_utc"] = "2026-10-31T20:00:00Z"
        self.assertEqual(self.run_grade()["rows"][0]["winner"]["status"], "RESULT_GAME_MISMATCH")

    def test_prediction_and_timezone_boundaries(self):
        for frozen in (self.p["start_utc"], "2026-10-31T16:00:00"):
            self.p["frozen_at_utc"] = frozen
            with self.assertRaises(ValueError):
                self.run_grade()

    def test_duplicates_rejected(self):
        for args in (([self.p, self.p], [self.r], [self.m]),
                     ([self.p], [self.r, self.r], [self.m]),
                     ([self.p], [self.r], [self.m, self.m])):
            with self.assertRaises(ValueError):
                ev.evaluate(*args)

    def test_invalid_numbers_rejected_or_flagged(self):
        for value in (float("nan"), float("inf"), True):
            self.p["projected_margin"] = value
            with self.assertRaises(ValueError):
                self.run_grade()
        self.p["projected_margin"] = 5
        for value in (float("nan"), -1, 2.5, None):
            self.r["home_points"] = value
            self.assertEqual(self.run_grade()["rows"][0]["winner"]["status"], "INVALID_FINAL_SCORE")

    def test_tie_and_no_pick_separate(self):
        self.r.update(home_points=20, away_points=20)
        self.assertEqual(self.run_grade()["rows"][0]["winner"]["status"], "TIE")
        self.p["winner_id"] = None
        self.assertEqual(self.run_grade()["rows"][0]["winner"]["status"], "NO_PREDICTION")

    def test_inputs_not_mutated(self):
        original = copy.deepcopy((self.p, self.r, self.m))
        self.run_grade()
        self.assertEqual((self.p, self.r, self.m), original)

    def test_cfb_rating_and_companion_scores_not_point_predictions(self):
        raw = dict(game_id="1", home_team_id="H", away_team_id="A", model="A1_balanced",
                   kickoff_utc=self.p["start_utc"], generated_at_utc=self.p["frozen_at_utc"],
                   predicted_winner_id="H", score_difference=4.8,
                   experimental_home_score=40, experimental_away_score=10)
        p = ev.native_predictions([raw], "CFB")
        report = ev.evaluate(p, [self.r], [self.m])
        self.assertEqual(report["rows"][0]["spread"]["status"], "NO_POINT_FORECAST")
        self.assertEqual(report["rows"][0]["total"]["status"], "NO_POINT_FORECAST")

    def test_nfl_preserves_original_winner_only(self):
        raw = dict(status="FROZEN_PREKICKOFF", frozenAt=self.p["frozen_at_utc"], games=[
            dict(id="1", home="H", away="A", date=self.p["start_utc"], picks={"A": "H", "B": "A"})])
        rows = ev.native_predictions(raw, "NFL")
        self.assertEqual([p["winner_id"] for p in rows], ["H", "A"])
        self.assertTrue(all("projected_margin" not in p for p in rows))
        raw["status"] = "FRESH_PREKICKOFF_SNAPSHOT"
        self.assertEqual(ev.native_predictions(raw, "NFL"), rows)
        raw["status"] = "RESEARCH_ONLY_NO_MARKET_LINES"
        with self.assertRaises(ValueError):
            ev.native_predictions(raw, "NFL")

    def test_nba_native_points_and_cutoff(self):
        raw = dict(game_id="1", home_id="H", away_id="A", home="Home", away="Away",
                   model="NBA-baseline", tipoff_utc=self.p["start_utc"],
                   frozen_at_utc=self.p["frozen_at_utc"], feature_cutoff_utc="2026-10-31T00:00:00Z",
                   predicted_winner="Home", predicted_margin=5, predicted_total=45,
                   status="FROZEN", wagering_status="NO_BET")
        result = ev.evaluate(ev.native_predictions(raw, "NBA"), [self.r], [self.m])
        self.assertEqual(result["summary"]["NBA-baseline"]["spread"]["wins"], 1)
        raw["feature_cutoff_utc"] = "2026-10-31T17:00:00Z"
        with self.assertRaises(ValueError):
            ev.native_predictions(raw, "NBA")

    def test_cli_exclusive_output_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p, r, m, out = [root / name for name in ("p.json", "r.json", "m.json", "out.json")]
            p.write_text(json.dumps({"canonical_predictions": [self.p]}))
            r.write_text(json.dumps([self.r]))
            m.write_text(json.dumps([self.m]))
            before = [x.read_bytes() for x in (p, r, m)]
            command = [sys.executable, str(SCRIPT), "--predictions", str(p), "--results", str(r),
                       "--markets", str(m), "--output", str(out)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            saved = out.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(out.read_bytes(), saved)
            self.assertEqual([x.read_bytes() for x in (p, r, m)], before)


if __name__ == "__main__":
    unittest.main()
