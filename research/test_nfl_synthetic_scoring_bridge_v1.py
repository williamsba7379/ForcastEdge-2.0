"""ForecastEdge synthetic bridge v1 acceptance tests.

DESIGN ONLY. Not executed or committed.
"""
import copy
import unittest
from unittest.mock import patch

from research import nfl_synthetic_scoring_bridge_v1 as bridge
from research.test_nfl_synthetic_scoring_contract_v1 import (
    fixture, CUTOFF, LATE
)

CONTRACT = (
    "research.nfl_synthetic_scoring_bridge_v1."
    "contract.assemble_synthetic_candidate"
)
ADAPTER = (
    "research.nfl_synthetic_scoring_bridge_v1."
    "adapter.project_four_models"
)


def run(args, cutoff=CUTOFF):
    return bridge.bridge_synthetic_scoring(
        *args, cutoff_utc=cutoff
    )


def fake_adapter_result(args):
    translated = bridge.translate_for_adapter(
        args[0], args[1], args[2], args[3],
        args[5], args[6]
    )
    return bridge.adapter.project_four_models(
        *translated
    )


class BridgeTests(unittest.TestCase):

    def setUp(self):
        self.a = fixture()

    def assert_blocked(self, reason):
        result = run(self.a)
        self.assertEqual(result, {
            "status": "DELIVERY_BLOCKED",
            "reason": reason,
            "published": False,
        })

    def mock_adapter_change(self, change):
        result = fake_adapter_result(self.a)
        change(result)
        with patch(ADAPTER, return_value=result):
            self.assert_blocked(
                "ADAPTER_PARITY_MISMATCH"
            )

    def test_01_complete_research_result(self):
        result = run(self.a)
        self.assertEqual(
            result["status"],
            "RESEARCH_ONLY_NOT_DELIVERABLE"
        )
        self.assertIs(result["published"], False)

    def test_02_four_models_present(self):
        result = run(self.a)
        self.assertEqual(
            set(result["models"]), set(bridge.MODELS)
        )

    def test_03_original_winners_preserved(self):
        result = run(self.a)
        self.assertEqual(
            {m: result["models"][m]["winner"]
             for m in bridge.MODELS},
            self.a[1]
        )

    def test_04_projected_scores(self):
        result = run(self.a)["models"]["A"]
        self.assertEqual(
            (result["projectedHomeScore"],
             result["projectedAwayScore"]),
            (24, 20)
        )

    def test_05_spread_pick(self):
        self.assertEqual(
            run(self.a)["models"]["A"]["spreadPick"],
            "Alpha"
        )

    def test_06_total_pick(self):
        self.assertEqual(
            run(self.a)["models"]["A"]["totalPick"],
            "Over"
        )

    def test_07_confidence(self):
        self.assertEqual(
            run(self.a)["models"]["A"]["confidence"],
            0.6
        )

    def test_08_c_qb_shadow(self):
        self.assertEqual(
            run(self.a)["models"]["C-QB"][
                "classification"
            ],
            bridge.SHADOW
        )

    def test_09_other_model_classifications(self):
        result = run(self.a)["models"]
        for model in ("A", "B", "C"):
            self.assertEqual(
                result[model]["classification"],
                bridge.RESEARCH
            )

    def test_10_missing_model(self):
        del self.a[2]["C"]
        self.assert_blocked("INCOMPLETE_MODELS")

    def test_11_extra_model(self):
        self.a[1]["X"] = "Alpha"
        self.assert_blocked("INCOMPLETE_MODELS")

    def test_12_non_synthetic(self):
        self.a[6]["syntheticOnly"] = False
        self.assert_blocked("UNSAFE_PROVENANCE")

    def test_13_false_independent_authority(self):
        self.a[6]["independentVerification"] = True
        self.assert_blocked("UNSAFE_PROVENANCE")

    def test_14_publication_attempt(self):
        self.a[6]["published"] = True
        self.assert_blocked("UNSAFE_PROVENANCE")

    def test_15_future_feature(self):
        self.a[6]["modelEvidence"]["A"][
            "featureAvailableAtUtc"
        ] = LATE
        self.assert_blocked("FUTURE_FEATURE")

    def test_16_future_calibration(self):
        self.a[6]["modelEvidence"]["A"][
            "calibrationAvailableAtUtc"
        ] = LATE
        self.assert_blocked("FUTURE_CALIBRATION")

    def test_17_invalid_hash(self):
        self.a[6]["modelEvidence"]["A"][
            "featureSha256"
        ] = "invalid"
        self.assert_blocked("INVALID_HASH")

    def test_18_feature_hash_mismatch(self):
        self.a[4]["A"]["sha256"] = "b" * 64
        self.assert_blocked(
            "FEATURE_PROVENANCE_MISMATCH"
        )

    def test_19_winner_conflict(self):
        self.a[2]["C"]["expectedHomeMargin"] = 1
        self.assert_blocked(
            "SCORE_WINNER_INCONSISTENCY"
        )

    def test_20_invalid_margin(self):
        self.a[2]["A"]["expectedHomeMargin"] = True
        self.assert_blocked("INVALID_ESTIMATE")

    def test_21_invalid_total(self):
        self.a[2]["A"]["expectedTotal"] = float("inf")
        self.assert_blocked("INVALID_ESTIMATE")

    def test_22_invalid_confidence(self):
        self.a[3]["A"]["winnerProbability"] = 1.1
        self.assert_blocked("INVALID_CONFIDENCE")

    def test_23_missing_qb_source(self):
        self.a[4]["C-QB"]["qbSourceId"] = ""
        self.assert_blocked("INVALID_QB_SHADOW")

    def test_24_missing_c_draft(self):
        self.a[4]["C"]["modelCDraftId"] = ""
        self.assert_blocked("MISSING_MODEL_C_DRAFT")

    def test_25_adapter_score_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["A"].update(
                projectedHomeScore=99
            )
        )

    def test_26_adapter_winner_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["A"].update(
                winner="Beta"
            )
        )

    def test_27_adapter_classification_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["C-QB"].update(
                classification=bridge.RESEARCH
            )
        )

    def test_28_adapter_confidence_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["B"].update(
                confidence=0.9
            )
        )

    def test_29_adapter_spread_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["A"].update(
                spreadPick="Beta"
            )
        )

    def test_30_adapter_total_mismatch(self):
        self.mock_adapter_change(
            lambda r: r["models"]["A"].update(
                totalPick="Under"
            )
        )

    def test_31_adapter_published_true(self):
        self.mock_adapter_change(
            lambda r: r.update(published=True)
        )

    def test_32_adapter_extra_field(self):
        self.mock_adapter_change(
            lambda r: r.update(approved=True)
        )

    def test_33_adapter_missing_model(self):
        self.mock_adapter_change(
            lambda r: r["models"].pop("C")
        )

    def test_34_adapter_exception(self):
        with patch(
            ADAPTER, side_effect=RuntimeError("synthetic")
        ):
            self.assert_blocked("BRIDGE_EXCEPTION")

    def test_35_contract_exception(self):
        with patch(
            CONTRACT, side_effect=ValueError("synthetic")
        ):
            self.assert_blocked("BRIDGE_EXCEPTION")

    def test_36_input_immutability(self):
        before = copy.deepcopy(self.a)
        run(self.a)
        self.assertEqual(self.a, before)


if __name__ == "__main__":
    unittest.main()
