#!/usr/bin/env python3
"""Offline, research-only regressions for November 4 NFL Week 9 provenance.
No network, production file writes, or prediction regeneration.
"""
import copy
import datetime as dt
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from nfl_market_totals_compare import compare

EXPECTED = {"season": 2026, "week": 9, "games": 15}
FREEZE = "2026-11-04T17:18:26.363923+00:00"
FIRST_KICKOFF = "2026-11-06T01:15:00+00:00"

def require_week9_manifest(manifest, source):
    """A success claim requires explicit immutable evidence, never a latest-file glob."""
    if not isinstance(manifest, dict) or manifest.get("season") != 2026 or manifest.get("week") != 9:
        raise ValueError("Missing explicit Week 9 manifest")
    if manifest.get("gameCount") != 15 or manifest.get("modelCount") != 4:
        raise ValueError("Incomplete four-model Week 9 coverage")
    if manifest.get("status") not in ("FROZEN_PREKICKOFF", "FRESH_PREKICKOFF_SNAPSHOT"):
        raise ValueError("Unfrozen or unrecognized snapshot")
    for key in ("sourceRunId", "sourceCommit", "artifactId", "artifactSha256", "frozenAt", "firstKickoff"):
        if not manifest.get(key):
            raise ValueError("Missing provenance: " + key)
    if not isinstance(manifest["sourceRunId"], int) or not isinstance(manifest["artifactId"], int):
        raise ValueError("Invalid source identity")
    if len(manifest["sourceCommit"]) != 40 or len(manifest["artifactSha256"]) != 64:
        raise ValueError("Invalid immutable source digest")
    frozen = dt.datetime.fromisoformat(manifest["frozenAt"].replace("Z", "+00:00"))
    kickoff = dt.datetime.fromisoformat(manifest["firstKickoff"].replace("Z", "+00:00"))
    if frozen.tzinfo is None or kickoff.tzinfo is None or frozen >= kickoff:
        raise ValueError("Missing pre-kickoff proof")
    if source.get("season") != 2026 or source.get("week") != 9 or len(source.get("games", [])) != 15:
        raise ValueError("Source artifact does not match Week 9 manifest")
    if source.get("frozenAt") != manifest["frozenAt"]:
        raise ValueError("Freeze timestamp differs from source artifact")
    for game in source["games"]:
        if set(game.get("picks", {})) != {"A", "B", "C", "C-QB"}:
            raise ValueError("Missing four-model game pick")
    return True

class FailClosedWeek9Regression(unittest.TestCase):
    def setUp(self):
        self.research = {"season": 2026, "week": 9,
                         "sourceComparisonFrozenAt": FREEZE,
                         "games": [{"id": "g1", "date": FIRST_KICKOFF,
                                    "models": {"A": {"projectedTotal": 42}}}]}
        self.manifest = {"season": 2026, "week": 9, "gameCount": 15, "modelCount": 4,
                         "status": "FRESH_PREKICKOFF_SNAPSHOT",
                         "sourceRunId": 41876281307, "sourceCommit": "a"*40,
                         "artifactId": 13346712960, "artifactSha256": "b"*64,
                         "frozenAt": FREEZE, "firstKickoff": FIRST_KICKOFF}
        self.source = {"season": 2026, "week": 9, "frozenAt": FREEZE,
                       "games": [{"picks": {k: "Home" for k in ("A", "B", "C", "C-QB")}} for _ in range(15)]}

    def test_market_week8_rejected_even_when_empty(self):
        with self.assertRaisesRegex(ValueError, "Market week mismatch"):
            compare(copy.deepcopy(self.research), {"season": 2026, "week": 8, "games": []})

    def test_matching_week_with_zero_quotes_is_explicit_no_lines(self):
        result = compare(copy.deepcopy(self.research), {"season": 2026, "week": 9, "games": []})
        self.assertEqual(result["status"], "NO_SOURCED_MARKET_LINES")
        self.assertEqual(result["marketLinesAvailable"], 0)
        self.assertNotIn("overUnderPick", result["games"][0]["models"]["A"])

    def test_week8_source_cannot_be_selected_as_week9(self):
        stale = copy.deepcopy(self.source)
        stale["week"] = 8
        with self.assertRaisesRegex(ValueError, "Source artifact"):
            require_week9_manifest(self.manifest, stale)

    def test_week9_manifest_validated_with_complete_model_set(self):
        self.assertTrue(require_week9_manifest(self.manifest, self.source))

    def test_missing_artifact_identity_fails(self):
        self.manifest.pop("artifactSha256")
        with self.assertRaisesRegex(ValueError, "Missing provenance"):
            require_week9_manifest(self.manifest, self.source)

    def test_post_kickoff_freeze_fails(self):
        self.manifest["frozenAt"] = "2026-11-06T01:16:00+00:00"
        self.source["frozenAt"] = self.manifest["frozenAt"]
        with self.assertRaisesRegex(ValueError, "pre-kickoff"):
            require_week9_manifest(self.manifest, self.source)

    def test_missing_model_fails(self):
        self.source["games"][0]["picks"].pop("C-QB")
        with self.assertRaisesRegex(ValueError, "Missing four-model"):
            require_week9_manifest(self.manifest, self.source)

    def test_wrong_source_freeze_fails(self):
        self.source["frozenAt"] = "2026-11-04T17:20:00+00:00"
        with self.assertRaisesRegex(ValueError, "timestamp differs"):
            require_week9_manifest(self.manifest, self.source)

if __name__ == "__main__":
    unittest.main()
