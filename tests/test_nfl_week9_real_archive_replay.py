#!/usr/bin/env python3
"""Immutable November 4 Week 9 archive replay; offline, read-only, no predictions."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
import unittest

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"
DIGEST = "6b74de78645bd17f910f5f0e5b51679b324c4f452aafb8e199f1ba3a4c32c250"
COMMIT = "9a0c8af1b786c32fb4df6421553be32fc623f660"
RUN = 41876281307
ARTIFACT = 13346712960
MODELS = {"A", "B", "C", "C-QB"}

def load(name):
    return json.loads((FIX / name).read_bytes())

def utc(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result.astimezone(dt.timezone.utc)

def verify(snapshot, schedule, manifest, raw):
    if hashlib.sha256(raw).hexdigest() != DIGEST or manifest.get("artifactSha256") != DIGEST:
        raise ValueError("Archived JSON digest mismatch")
    if manifest.get("sourceRunId") != RUN or manifest.get("sourceCommit") != COMMIT or manifest.get("artifactId") != ARTIFACT:
        raise ValueError("Synthetic or stale provenance")
    if manifest.get("mode") != "READ_ONLY_NO_FREEZE":
        raise ValueError("Cannot claim a production freeze")
    if manifest.get("status") != "FRESH_PREKICKOFF_SNAPSHOT" or snapshot.get("status") != manifest["status"]:
        raise ValueError("Invalid isolated research snapshot status")
    if manifest.get("season") != 2026 or manifest.get("week") != 9 or manifest.get("gameCount") != 15 or manifest.get("modelCount") != 4:
        raise ValueError("Invalid manifest coverage")
    if (snapshot.get("season"), snapshot.get("week"), schedule.get("season"), schedule.get("week")) != (2026, 9, 2026, 9):
        raise ValueError("Stale week")
    expected = schedule.get("games", [])
    actual = snapshot.get("games", [])
    if len(expected) != 15 or len(actual) != 15:
        raise ValueError("Incomplete schedule or frozen card")
    index = {str(g["id"]): g for g in expected}
    if len(index) != 15 or len({str(g["id"]) for g in actual}) != 15:
        raise ValueError("Duplicate game IDs")
    if set(index) != {str(g["id"]) for g in actual}:
        raise ValueError("Schedule game IDs differ")
    freeze = utc(snapshot["frozenAt"])
    if snapshot["frozenAt"] != manifest.get("frozenAt") or utc(manifest["firstKickoff"]) != min(utc(g["date"]) for g in expected):
        raise ValueError("Freeze metadata mismatch")
    for g in actual:
        reference = index[str(g["id"])]
        if (g["home"], g["away"]) != (reference["home"], reference["away"]):
            raise ValueError("Team identity mismatch")
        if utc(g["date"]) != utc(reference["date"]):
            raise ValueError("Kickoff mismatch")
        if not freeze < utc(g["date"]):
            raise ValueError("Post-kickoff freeze")
        if set(g.get("picks", {})) != MODELS:
            raise ValueError("Incomplete four-model parity")
        if any(g["picks"][model] not in (g["home"], g["away"]) for model in MODELS):
            raise ValueError("Invalid winner selection")
    return True

class ArchivedWeek9Replay(unittest.TestCase):
    def setUp(self):
        self.raw = (FIX / "nfl_week9_20261104_actual_snapshot.json").read_bytes()
        self.snapshot = json.loads(self.raw)
        self.schedule = load("nfl_week9_20261104_espn_schedule.json")
        self.manifest = load("nfl_week9_20261104_artifact_manifest.json")

    def check(self, snapshot=None, schedule=None, manifest=None, raw=None):
        return verify(snapshot if snapshot is not None else self.snapshot,
                      schedule if schedule is not None else self.schedule,
                      manifest if manifest is not None else self.manifest,
                      raw if raw is not None else self.raw)

    def test_original_archive_and_schedule_all_15_games(self):
        self.assertTrue(self.check())

    def test_original_json_sha256_is_pinned(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), DIGEST)

    def test_changed_artifact_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            self.check(raw=self.raw + b" ")

    def test_synthetic_run_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["sourceRunId"] = 123
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            self.check(manifest=m)

    def test_stale_commit_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["sourceCommit"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            self.check(manifest=m)

    def test_wrong_artifact_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["artifactId"] = 1
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            self.check(manifest=m)

    def test_mismatched_game_id_rejected(self):
        s = copy.deepcopy(self.schedule)
        s["games"][0]["id"] = "incorrect"
        with self.assertRaisesRegex(ValueError, "game IDs"):
            self.check(schedule=s)

    def test_changed_team_rejected(self):
        s = copy.deepcopy(self.schedule)
        s["games"][0]["home"] = "Wrong Team"
        with self.assertRaisesRegex(ValueError, "Team identity"):
            self.check(schedule=s)

    def test_changed_kickoff_rejected(self):
        s = copy.deepcopy(self.schedule)
        s["games"][0]["date"] = "2026-11-06T02:15:00Z"
        with self.assertRaisesRegex(ValueError, "Kickoff"):
            self.check(schedule=s)

    def test_missing_model_rejected(self):
        a = copy.deepcopy(self.snapshot)
        a["games"][0]["picks"].pop("C-QB")
        with self.assertRaisesRegex(ValueError, "four-model"):
            self.check(snapshot=a)

    def test_stale_week_rejected(self):
        s = copy.deepcopy(self.schedule)
        s["week"] = 8
        with self.assertRaisesRegex(ValueError, "Stale week"):
            self.check(schedule=s)

    def test_production_freeze_claim_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["mode"] = "PRODUCTION_FROZEN"
        with self.assertRaisesRegex(ValueError, "production freeze"):
            self.check(manifest=m)

if __name__ == "__main__":
    unittest.main()
