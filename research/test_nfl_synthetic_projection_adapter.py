"""Synthetic-only acceptance tests. Not yet executed."""
import copy
import unittest

from research.nfl_synthetic_projection_adapter import (
    MODELS, SHADOW, RESEARCH, project_four_models
)


def fixture():
    game = {
        "id": "SYNTHETIC-001",
        "home": "Alpha",
        "away": "Beta",
    }
    picks = {
        "A": "Alpha",
        "B": "Alpha",
        "C": "Beta",
        "C-QB": "Alpha",
    }
    margins = {"A": 4, "B": 2, "C": -1, "C-QB": 3}
    totals = {"A": 44, "B": 42, "C": 41, "C-QB": 43}
    inputs = {
        m: {
            "expectedHomeMargin": margins[m],
            "expectedTotal": totals[m],
            "classification": (
                SHADOW if m == "C-QB" else RESEARCH
            ),
        }
        for m in MODELS
    }
    market = {"homeSpread": -3.5, "total": 42.5}
    calibration = {
        m: {"winnerProbability": 0.60}
        for m in MODELS
    }
    provenance = {"syntheticOnly": True}
    return [
        game, picks, inputs, market,
        calibration, provenance
    ]


def run(args):
    return project_four_models(*args)


class AdapterTests(unittest.TestCase):

    def setUp(self):
        self.args = fixture()

    def assertBlocked(self, args, reason):
        result = run(args)
        self.assertEqual(result["status"], "DELIVERY_BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["published"], False)

    def test_01_complete_research_result(self):
        result = run(self.args)
        self.assertEqual(
            result["status"], "RESEARCH_ONLY_NOT_DELIVERABLE"
        )
        self.assertFalse(result["published"])
        self.assertEqual(set(result["models"]), set(MODELS))

    def test_02_winners_unchanged(self):
        original = copy.deepcopy(self.args[1])
        result = run(self.args)
        self.assertEqual(
            {m: result["models"][m]["winner"] for m in MODELS},
            original
        )
        self.assertEqual(self.args[1], original)

    def test_03_missing_model(self):
        del self.args[2]["C-QB"]
        self.assertBlocked(self.args, "INCOMPLETE_MODELS")

    def test_04_missing_margin(self):
        del self.args[2]["A"]["expectedHomeMargin"]
        self.assertBlocked(self.args, "MISSING_CALCULATION")

    def test_05_missing_total(self):
        del self.args[2]["B"]["expectedTotal"]
        self.assertBlocked(self.args, "MISSING_CALCULATION")

    def test_06_missing_calibration(self):
        del self.args[4]["C"]
        self.assertBlocked(self.args, "INCOMPLETE_MODELS")

    def test_07_nonfinite(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                args = fixture()
                args[2]["A"]["expectedTotal"] = value
                self.assertBlocked(
                    args, "MISSING_CALCULATION"
                )

    def test_08_impossible_score(self):
        self.args[2]["A"]["expectedHomeMargin"] = 50
        self.assertBlocked(self.args, "IMPOSSIBLE_SCORES")

    def test_09_invalid_market(self):
        del self.args[3]["homeSpread"]
        self.assertBlocked(self.args, "INVALID_MARKET")

    def test_10_qb_shadow_classification(self):
        self.args[2]["C-QB"]["classification"] = RESEARCH
        self.assertBlocked(
            self.args, "INVALID_CLASSIFICATION"
        )

    def test_11_missing_synthetic_marker(self):
        self.args[5] = {}
        self.assertBlocked(self.args, "NOT_SYNTHETIC")

    def test_12_winner_score_conflict(self):
        original = copy.deepcopy(self.args[1])
        self.args[2]["C"]["expectedHomeMargin"] = 1
        self.assertBlocked(
            self.args, "SCORE_WINNER_INCONSISTENCY"
        )
        self.assertEqual(self.args[1], original)

    def test_13_arithmetic(self):
        result = run(self.args)
        a = result["models"]["A"]
        self.assertEqual(a["projectedHomeScore"], 24)
        self.assertEqual(a["projectedAwayScore"], 20)
        self.assertEqual(a["projectedMargin"], 4)
        self.assertEqual(a["projectedTotal"], 44)
        self.assertEqual(a["spreadPick"], "Alpha")
        self.assertEqual(a["totalPick"], "Over")

    def test_14_no_input_mutation(self):
        before = copy.deepcopy(self.args)
        run(self.args)
        self.assertEqual(self.args, before)

    def test_15_malformed_inputs(self):
        for index, bad in (
            (0, None),
            (1, []),
            (2, "invalid"),
            (3, None),
            (4, []),
            (5, None),
        ):
            with self.subTest(index=index):
                args = fixture()
                args[index] = bad
                self.assertBlocked(args, "MALFORMED_INPUT")

        args = fixture()
        args[2]["A"] = []
        self.assertBlocked(args, "INVALID_MODEL_INPUT")

    def test_16_zero_margin(self):
        self.args[2]["A"]["expectedHomeMargin"] = 0
        self.assertBlocked(
            self.args, "SCORE_WINNER_INCONSISTENCY"
        )

    def test_17_probability_out_of_range(self):
        self.args[4]["A"]["winnerProbability"] = 1.2
        self.assertBlocked(self.args, "INVALID_CONFIDENCE")

    def test_18_spread_and_total_push(self):
        self.args[3]["homeSpread"] = -4
        self.args[3]["total"] = 44
        result = run(self.args)
        a = result["models"]["A"]
        self.assertEqual(a["spreadPick"], "Push")
        self.assertEqual(a["totalPick"], "Push")


if __name__ == "__main__":
    unittest.main()
