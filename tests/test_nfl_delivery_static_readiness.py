"""Offline regressions for nonpublishing review imports and workflow gates."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StaticDeliveryReadinessTests(unittest.TestCase):
    def test_four_model_import_has_no_top_level_directory_creation(self):
        source = (ROOT / "scripts/nfl_four_model_head_to_head.py").read_text()
        module = ast.parse(source)
        top_level_calls = [n for n in module.body if isinstance(n, ast.Expr)
                           and isinstance(n.value, ast.Call)]
        self.assertFalse(any(isinstance(n.value.func, ast.Attribute)
                             and n.value.func.attr == "mkdir" for n in top_level_calls))
        self.assertIn("OUT.mkdir(parents=True,exist_ok=True)", source)

    def test_injury_audit_does_not_count_null_historical_qb(self):
        source = (ROOT / "scripts/model_c_qb_injury_audit_v2.py").read_text()
        self.assertIn('isinstance(r.get("primaryPasser"),str)', source)
        self.assertIn('isinstance(r.get("gameDate"),str)', source)
        self.assertIn('"pointsAdjustment":0', source)

    def test_model_c_archive_remains_after_injury_audit(self):
        source = (ROOT / ".github/workflows/model-c-draft.yml").read_text()
        self.assertLess(source.index("Audit unmodeled critical QB injuries"),
                        source.index("Validate generated Model C review draft"))
        self.assertLess(source.index("Validate generated Model C review draft"),
                        source.index("Create same-run review-only archive"))
        self.assertNotIn("git push", source)

    def test_new_review_preflight_cannot_publish(self):
        source = (ROOT / ".github/workflows/nfl-four-model-review-preflight.yml").read_text()
        self.assertIn("contents: read", source)
        self.assertNotIn("git push", source)
        self.assertNotIn("upload-artifact", source)


if __name__ == "__main__":
    unittest.main()
