"""Regression for the actual November 4 stale Week 8 and market mismatch paths."""
import copy
import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "research"))
from nfl_weekly_delivery_gate import validate

CUTOFF = "2026-11-04T16:00:00Z"

def fixture():
    game = {"id": "week9-game", "away": "AWAY", "home": "HOME", "date": "2026-11-06T01:15:00Z"}
    schedule = {"season": 2026, "week": 9, "source": "espn", "sha256": "a"*64,
                "capturedAt": "2026-11-04T15:50:00Z", "games": [game]}
    independent = copy.deepcopy(schedule)
    independent.update(source="nfl-official", sha256="b"*64)
    draft = {"season": 2026, "week": 9, "generatedAt": "2026-11-04T15:55:00Z", "games": [game]}
    shadow = copy.deepcopy(draft)
    shadow["generatedAt"] = "2026-11-04T15:56:00Z"
    card = {"season": 2026, "week": 9, "frozenAt": CUTOFF,
            "games": [{**game, "picks": {m: "HOME" for m in ("A","B","C","C-QB")}}]}
    market = {"season": 2026, "week": 9, "games": []}
    return [schedule, independent, draft, shadow, card, market, CUTOFF]

class WeekNineFailureRegression(unittest.TestCase):
    def test_valid_research_only(self):
        result = validate(*fixture())
        self.assertEqual(result["modelRows"], 4)
        self.assertFalse(result["productionReady"])

    def test_both_models_stale_week8(self):
        args = fixture()
        args[2]["week"] = args[3]["week"] = 8
        with self.assertRaisesRegex(ValueError, "STALE_WEEK_MODEL_C"):
            validate(*args)

    def test_week8_market_snapshot(self):
        args = fixture()
        args[5]["week"] = 8
        with self.assertRaisesRegex(ValueError, "MARKET_WEEK_MISMATCH"):
            validate(*args)

    def test_independent_schedule_disagrees(self):
        args = fixture()
        args[1]["games"][0]["home"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_SCHEDULE_MISMATCH"):
            validate(*args)

    def test_same_source_rejected(self):
        args = fixture()
        args[1]["source"] = args[0]["source"]
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_SCHEDULE_SOURCE_REQUIRED"):
            validate(*args)

    def test_missing_game_rejected(self):
        args = fixture()
        args[4]["games"] = []
        with self.assertRaisesRegex(ValueError, "INVALID_OR_DUPLICATE_SLATE|SLATE_MISMATCH_CARD"):
            validate(*args)

    def test_missing_model_rejected(self):
        args = fixture()
        del args[4]["games"][0]["picks"]["C-QB"]
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_FOUR_MODEL_CARD"):
            validate(*args)

    def test_post_cutoff_rejected(self):
        args = fixture()
        args[2]["generatedAt"] = "2026-11-04T16:49:00Z"
        with self.assertRaisesRegex(ValueError, "STALE_OR_LATE_MODEL_C"):
            validate(*args)

    def test_old_schedule_rejected(self):
        args = fixture()
        args[1]["capturedAt"] = "2026-11-02T15:50:00Z"
        with self.assertRaisesRegex(ValueError, "SCHEDULE_CAPTURE_OUTSIDE_WINDOW"):
            validate(*args)

    def test_never_mutates_input(self):
        args = fixture()
        before = copy.deepcopy(args)
        validate(*args)
        self.assertEqual(args, before)


    def test_controlled_full_thursday_monday_slate(self):
        args = fixture()
        # Synthetic full slate: one Thursday, twelve Sunday, one Monday, one Friday.
        dates = ["2026-11-06T01:15:00Z"] + ["2026-11-08T18:00:00Z"] * 12 + [
            "2026-11-10T01:15:00Z", "2026-11-07T01:00:00Z"]
        games = [{**args[0]["games"][0], "id": str(i), "date": date}
                 for i, date in enumerate(dates)]
        args[0]["games"] = copy.deepcopy(games)
        args[1]["games"] = copy.deepcopy(games)
        args[2]["games"] = copy.deepcopy(games)
        args[3]["games"] = copy.deepcopy(games)
        args[4]["games"] = [{**game, "picks": {m: "HOME" for m in ("A", "B", "C", "C-QB")}}
                             for game in games]
        result = validate(*args)
        self.assertEqual(result["games"], 15)
        self.assertEqual(result["modelRows"], 60)
        self.assertFalse(result["productionReady"])
        args[3]["games"].pop()
        with self.assertRaisesRegex(ValueError, "SLATE_MISMATCH_MODEL_C_QB"):
            validate(*args)

    def test_market_week_mismatch_blocks_full_slate(self):
        args = fixture()
        args[5]["week"] = 8
        before = copy.deepcopy(args)
        with self.assertRaisesRegex(ValueError, "MARKET_WEEK_MISMATCH"):
            validate(*args)
        self.assertEqual(args, before)

if __name__ == "__main__":
    unittest.main()
