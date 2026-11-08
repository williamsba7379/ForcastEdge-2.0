"""Design-only contract examples. No network, production imports, or filesystem writes."""
import copy
import unittest

def evaluate_design_contract(request, evidence):
    """Reference decision table, NOT a production verifier or approved security boundary."""
    reasons = []
    if (request.get("season"), request.get("week")) != (evidence.get("season"), evidence.get("week")):
        reasons.append("STALE_WEEK")
    ids = request.get("game_ids", [])
    games = evidence.get("games", [])
    if not ids or len(ids) != len(set(ids)) or set(ids) != {g.get("id") for g in games} or len(games) != len(ids):
        reasons.append("SCHEDULE_MISMATCH")
    if not evidence.get("independent_schedule_verified"):
        reasons.append("INDEPENDENT_SCHEDULE_MISSING")
    for name in ("model_c", "model_c_qb", "ab_baseline", "card"):
        source = evidence.get(name) or {}
        if not all(source.get(k) for k in ("run_id", "artifact_id", "commit", "sha256", "cutoff_ok", "identity_verified")):
            reasons.append("MISSING_OR_UNVERIFIED_" + name.upper())
    if evidence.get("mode") != "PRODUCTION_CANDIDATE":
        reasons.append("RESEARCH_ONLY_NOT_PRODUCTION")
    if not evidence.get("four_model_parity"):
        reasons.append("MODEL_PARITY_MISSING")
    if not evidence.get("no_bet_preserved"):
        reasons.append("NO_BET_NOT_VERIFIED")
    return {"status": "NOT_READY" if reasons else "DESIGN_CONTRACT_SATISFIED_NOT_PRODUCTION_CERTIFIED",
            "productionReady": False, "reasonCodes": reasons}

class WednesdayDesignCases(unittest.TestCase):
    def setUp(self):
        self.request = {"season": 2026, "week": 9, "game_ids": ["g1", "g2"]}
        source = {"run_id": 42, "artifact_id": 7, "commit": "a"*40,
                  "sha256": "b"*64, "cutoff_ok": True, "identity_verified": True}
        self.evidence = {"season": 2026, "week": 9,
                         "games": [{"id": "g1"}, {"id": "g2"}],
                         "independent_schedule_verified": True,
                         "model_c": copy.deepcopy(source), "model_c_qb": copy.deepcopy(source),
                         "ab_baseline": copy.deepcopy(source), "card": copy.deepcopy(source),
                         "mode": "PRODUCTION_CANDIDATE", "four_model_parity": True,
                         "no_bet_preserved": True}

    def test_complete_contract_never_certifies_production(self):
        result = evaluate_design_contract(self.request, self.evidence)
        self.assertEqual(result["status"], "DESIGN_CONTRACT_SATISFIED_NOT_PRODUCTION_CERTIFIED")
        self.assertFalse(result["productionReady"])

    def test_stale_week8_fails(self):
        self.evidence["week"] = 8
        self.assertIn("STALE_WEEK", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_missing_qb_artifact_fails(self):
        del self.evidence["model_c_qb"]
        self.assertIn("MISSING_OR_UNVERIFIED_MODEL_C_QB", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_missing_schedule_source_fails(self):
        self.evidence["independent_schedule_verified"] = False
        self.assertIn("INDEPENDENT_SCHEDULE_MISSING", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_mismatched_game_ids_fail(self):
        self.evidence["games"][0]["id"] = "wrong"
        self.assertIn("SCHEDULE_MISMATCH", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_post_cutoff_input_fails(self):
        self.evidence["model_c"]["cutoff_ok"] = False
        self.assertIn("MISSING_OR_UNVERIFIED_MODEL_C", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_unverified_source_identity_fails(self):
        self.evidence["card"]["identity_verified"] = False
        self.assertIn("MISSING_OR_UNVERIFIED_CARD", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_missing_digest_fails(self):
        self.evidence["ab_baseline"]["sha256"] = ""
        self.assertIn("MISSING_OR_UNVERIFIED_AB_BASELINE", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

    def test_research_only_cannot_certify_production(self):
        self.evidence["mode"] = "READ_ONLY_NO_FREEZE"
        result = evaluate_design_contract(self.request, self.evidence)
        self.assertIn("RESEARCH_ONLY_NOT_PRODUCTION", result["reasonCodes"])
        self.assertFalse(result["productionReady"])

    def test_no_bet_integrity_required(self):
        self.evidence["no_bet_preserved"] = False
        self.assertIn("NO_BET_NOT_VERIFIED", evaluate_design_contract(self.request, self.evidence)["reasonCodes"])

if __name__ == "__main__":
    unittest.main()
