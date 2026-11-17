#!/usr/bin/env python3
"""Read-only gate tests: authentic archive is research-only, never production-ready."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from nfl_week9_isolated_delivery_gate import gate

FIX = ROOT / "tests" / "fixtures"
COMMIT = "9a0c8af1b786c32fb4df6421553be32fc623f660"
DIGEST = "6b74de78645bd17f910f5f0e5b51679b324c4f452aafb8e199f1ba3a4c32c250"

class IsolatedWednesdayDeliveryGate(unittest.TestCase):
    def setUp(self):
        self.raw = (FIX / "nfl_week9_20261104_actual_snapshot.json").read_bytes()
        self.snapshot = json.loads(self.raw)
        self.schedule = json.loads((FIX / "nfl_week9_20261104_espn_schedule.json").read_bytes())
        self.manifest = json.loads((FIX / "nfl_week9_20261104_artifact_manifest.json").read_bytes())
        self.ids = [str(g["id"]) for g in self.schedule["games"]]

    def check(self, season=2026, week=9, raw=None, schedule=None, manifest=None, commit=COMMIT, digest=DIGEST, ids=None):
        return gate(season, week, self.raw if raw is None else raw,
                    self.schedule if schedule is None else schedule,
                    self.manifest if manifest is None else manifest,
                    commit, digest, self.ids if ids is None else ids)

    def test_authentic_research_archive_accepted_but_not_production(self):
        result = self.check()
        self.assertEqual(result["status"], "RESEARCH_ONLY_VALIDATED")
        self.assertFalse(result["productionReady"])
        self.assertFalse(result["productionFreezeVerified"])
        self.assertEqual(result["gameCount"], 15)

    def test_stale_week8_request_rejected(self):
        with self.assertRaisesRegex(ValueError, "season/week"):
            self.check(week=8)

    def test_stale_week8_snapshot_rejected(self):
        stale = copy.deepcopy(self.snapshot)
        stale["week"] = 8
        with self.assertRaisesRegex(ValueError, "digest"):
            self.check(raw=json.dumps(stale).encode())

    def test_synthetic_commit_rejected(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.check(commit="a" * 40)

    def test_synthetic_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.check(digest="b" * 64)

    def test_missing_expected_game_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "game IDs"):
            self.check(ids=self.ids[:-1])

    def test_wrong_expected_game_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "game IDs"):
            self.check(ids=self.ids[:-1] + ["not-a-game"])

    def test_duplicate_game_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "game IDs"):
            self.check(ids=self.ids[:-1] + [self.ids[0]])

    def test_missing_explicit_commit_rejected(self):
        with self.assertRaisesRegex(ValueError, "required"):
            self.check(commit="")

    def test_post_kickoff_manifest_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["frozenAt"] = "2026-11-09T23:00:00Z"
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.check(manifest=m)

    def test_production_claim_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["mode"] = "PRODUCTION_FROZEN"
        with self.assertRaisesRegex(ValueError, "production freeze"):
            self.check(manifest=m)

    def test_wrong_schedule_kickoff_rejected(self):
        s = copy.deepcopy(self.schedule)
        s["games"][2]["date"] = "2026-11-08T19:00:00Z"
        with self.assertRaisesRegex(ValueError, "Kickoff"):
            self.check(schedule=s)

if __name__ == "__main__":
    unittest.main()
