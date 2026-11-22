"""Synthetic contract acceptance tests. NOT EXECUTED."""
import copy
import unittest

from research.nfl_synthetic_scoring_contract_v1 import (
    MODELS, RESEARCH, SHADOW,
    assemble_synthetic_candidate,
)

CUTOFF = "2026-11-18T16:00:00Z"
EARLY = "2026-11-17T12:00:00Z"
LATE = "2026-11-19T12:00:00Z"
HASH = "a" * 64


def fixture():
    game = {
        "id": "SYNTHETIC-001",
        "home": "Alpha",
        "away": "Beta",
        "kickoffUtc": "2026-11-19T20:00:00Z",
    }
    picks = {
        "A": "Alpha", "B": "Alpha",
        "C": "Beta", "C-QB": "Alpha",
    }
    margins = {"A": 4, "B": 2, "C": -1, "C-QB": 3}
    totals = {"A": 44, "B": 42, "C": 41, "C-QB": 43}

    providers = {
        m: {
            "gameId": game["id"],
            "expectedHomeMargin": margins[m],
            "expectedTotal": totals[m],
            "classification":
                SHADOW if m == "C-QB" else RESEARCH,
        }
        for m in MODELS
    }
    calibration = {
        m: {
            "model": m,
            "gameId": game["id"],
            "winnerProbability": 0.6,
            "artifactId": "CAL-" + m,
            "trainingCount": 30,
            "validationCount": 20,
            "trainingEndUtc": "2026-10-01T12:00:00Z",
            "validationStartUtc": "2026-10-02T12:00:00Z",
            "validationEndUtc": "2026-11-01T12:00:00Z",
        }
        for m in MODELS
    }
    features = {
        m: {
            "model": m,
            "gameId": game["id"],
            "sourceId": "SYNTH-" + m,
            "sampleSize": 5,
            "artifactId": "FEATURE-" + m,
            "sha256": HASH,
            "availableAtUtc": EARLY,
        }
        for m in MODELS
    }
    features["C"]["modelCDraftId"] = "SYNTH-C-DRAFT"
    features["C-QB"].update({
        "qbStatus": SHADOW,
        "qbSourceId": "SYNTH-QB",
        "qbAvailableAtUtc": EARLY,
    })
    provenance = {
        "contractVersion": "synthetic-scoring-v1",
        "syntheticOnly": True,
        "independentVerification": False,
        "published": False,
        "gameId": game["id"],
        "cutoffUtc": CUTOFF,
        "generatedAtUtc": EARLY,
        "modelEvidence": {
            m: {
                "featureArtifactId": "FEATURE-" + m,
                "featureSha256": HASH,
                "featureAvailableAtUtc": EARLY,
                "providerVersion": "synthetic-" + m,
                "calibrationArtifactId": "CAL-" + m,
                "calibrationAvailableAtUtc": EARLY,
                "classification":
                    SHADOW if m == "C-QB" else RESEARCH,
            }
            for m in MODELS
        },
    }
    return [
        game, picks, providers, calibration, features,
        {"homeSpread": -3.5, "total": 42.5},
        provenance,
    ]


def run(args, cutoff=CUTOFF):
    return assemble_synthetic_candidate(
        *args, cutoff_utc=cutoff
    )


class ContractTests(unittest.TestCase):

    def setUp(self):
        self.a = fixture()

    def blocked(self, reason):
        result = run(self.a)
        self.assertEqual(result["status"], "DELIVERY_BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["published"], False)

    def test_01_complete(self):
        result = run(self.a)
        self.assertEqual(
            result["status"], "RESEARCH_ONLY_NOT_DELIVERABLE"
        )
        self.assertEqual(set(result["models"]), set(MODELS))
        self.assertFalse(result["published"])

    def test_02_preserved_winners(self):
        result = run(self.a)
        self.assertEqual(
            {m: result["models"][m]["winner"] for m in MODELS},
            self.a[1],
        )

    def test_03_arithmetic(self):
        a = run(self.a)["models"]["A"]
        self.assertEqual(a["projectedHomeScore"], 24)
        self.assertEqual(a["projectedAwayScore"], 20)
        self.assertEqual(a["projectedTotal"], 44)

    def test_04_market(self):
        a = run(self.a)["models"]["A"]
        self.assertEqual(a["spreadPick"], "Alpha")
        self.assertEqual(a["totalPick"], "Over")

    def test_05_missing_model(self):
        del self.a[2]["C"]
        self.blocked("INCOMPLETE_MODELS")

    def test_06_extra_model(self):
        self.a[1]["X"] = "Alpha"
        self.blocked("INCOMPLETE_MODELS")

    def test_07_bad_game(self):
        self.a[0]["away"] = "Alpha"
        self.blocked("INVALID_GAME")

    def test_08_bad_market(self):
        self.a[5]["total"] = float("nan")
        self.blocked("INVALID_MARKET")

    def test_09_bad_margin(self):
        self.a[2]["A"]["expectedHomeMargin"] = True
        self.blocked("INVALID_ESTIMATE")

    def test_10_bad_total(self):
        self.a[2]["A"]["expectedTotal"] = float("inf")
        self.blocked("INVALID_ESTIMATE")

    def test_11_impossible_score(self):
        self.a[2]["A"]["expectedHomeMargin"] = 50
        self.blocked("IMPOSSIBLE_SCORES")

    def test_12_winner_conflict(self):
        self.a[2]["C"]["expectedHomeMargin"] = 1
        self.blocked("SCORE_WINNER_INCONSISTENCY")

    def test_13_projected_tie(self):
        self.a[2]["A"]["expectedHomeMargin"] = 0
        self.blocked("SCORE_WINNER_INCONSISTENCY")

    def test_14_bad_probability(self):
        self.a[3]["A"]["winnerProbability"] = 1.2
        self.blocked("INVALID_CONFIDENCE")

    def test_15_training_too_small(self):
        self.a[3]["A"]["trainingCount"] = 29
        self.blocked("INSUFFICIENT_CALIBRATION")

    def test_16_validation_too_small(self):
        self.a[3]["A"]["validationCount"] = 19
        self.blocked("INSUFFICIENT_CALIBRATION")

    def test_17_calibration_overlap(self):
        self.a[3]["A"]["validationStartUtc"] = (
            "2026-09-30T12:00:00Z"
        )
        self.blocked("CALIBRATION_LEAKAGE")

    def test_18_future_calibration(self):
        self.a[6]["modelEvidence"]["A"][
            "calibrationAvailableAtUtc"
        ] = LATE
        self.blocked("FUTURE_CALIBRATION")

    def test_19_future_features(self):
        self.a[6]["modelEvidence"]["A"][
            "featureAvailableAtUtc"
        ] = LATE
        self.blocked("FUTURE_FEATURE")

    def test_20_bad_hash(self):
        self.a[6]["modelEvidence"]["A"][
            "featureSha256"
        ] = "invalid"
        self.blocked("INVALID_HASH")

    def test_21_feature_hash_mismatch(self):
        self.a[4]["A"]["sha256"] = "b" * 64
        self.blocked("FEATURE_PROVENANCE_MISMATCH")

    def test_22_missing_source(self):
        self.a[4]["A"]["sourceId"] = ""
        self.blocked("INSUFFICIENT_FEATURES")

    def test_23_wrong_provider_game(self):
        self.a[2]["A"]["gameId"] = "OTHER"
        self.blocked("PROVIDER_GAME_MISMATCH")

    def test_24_wrong_calibration_model(self):
        self.a[3]["A"]["model"] = "B"
        self.blocked("CALIBRATION_MISMATCH")

    def test_25_qb_label(self):
        self.a[2]["C-QB"]["classification"] = RESEARCH
        self.blocked("INVALID_CLASSIFICATION")

    def test_26_missing_qb_source(self):
        self.a[4]["C-QB"]["qbSourceId"] = ""
        self.blocked("INVALID_QB_SHADOW")

    def test_27_missing_c_draft(self):
        self.a[4]["C"]["modelCDraftId"] = ""
        self.blocked("MISSING_MODEL_C_DRAFT")

    def test_28_false_independence(self):
        self.a[6]["independentVerification"] = True
        self.blocked("FALSE_AUTHORITY")

    def test_29_publication_attempt(self):
        self.a[6]["published"] = True
        self.blocked("PUBLICATION_FORBIDDEN")

    def test_30_input_immutability(self):
        before = copy.deepcopy(self.a)
        run(self.a)
        self.assertEqual(self.a, before)


if __name__ == "__main__":
    unittest.main()
