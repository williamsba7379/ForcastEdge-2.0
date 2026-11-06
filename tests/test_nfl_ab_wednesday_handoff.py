"""Isolated A/B Wednesday handoff regression tests; no production writes."""
import copy
import unittest
from scripts.nfl_ab_wednesday_handoff import build_ab_wednesday_handoff
from test_nfl_ab_full_slate_audit import fixture,CUTOFF

def inputs():
    snapshot,slate=fixture()
    schedule=[{k:g[k] for k in ("id","date","home","away","season")} for g in slate]
    return snapshot,slate,schedule

class WednesdayHandoffTests(unittest.TestCase):
    def test_15_independent_model_rows_and_provenance(self):
        snap,slate,schedule=inputs()
        out=build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
        self.assertEqual(out["expectedCount"],15)
        self.assertEqual(len(out["games"]),15)
        self.assertEqual(len({g["id"] for g in out["games"]}),15)
        self.assertTrue(all(set(g["picks"])=={"A","B"} for g in out["games"]))
        self.assertTrue(all(g["picks"]["A"]==g["picks"]["B"] for g in out["games"]))
        self.assertFalse(out["publishable"])
        self.assertFalse(out["officialFrozen"])
        self.assertTrue(out["noBet"])
        self.assertEqual(len(out["snapshotSha256"]),64)
    def test_repeat_is_deterministic_and_input_unchanged(self):
        snap,slate,schedule=inputs()
        before=copy.deepcopy((snap,slate,schedule))
        first=build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
        self.assertEqual(first,build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule))
        self.assertEqual((snap,slate,schedule),before)
    def test_missing_game_rejected(self):
        snap,slate,schedule=inputs()
        with self.assertRaisesRegex(ValueError,"SCHEDULE_COVERAGE_MISMATCH"):
            build_ab_wednesday_handoff(snap,slate[:-1],CUTOFF,schedule)
    def test_changed_team_rejected(self):
        snap,slate,schedule=inputs()
        slate[0]["home"]="Changed Team"
        with self.assertRaisesRegex(ValueError,"SCHEDULE_IDENTITY_MISMATCH"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_changed_kickoff_rejected(self):
        snap,slate,schedule=inputs()
        schedule[0]["date"]="2026-11-09T18:00:00Z"
        with self.assertRaisesRegex(ValueError,"SCHEDULE_IDENTITY_MISMATCH"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_duplicate_expected_ids_rejected(self):
        snap,slate,schedule=inputs()
        schedule[1]["id"]=schedule[0]["id"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_EMPTY_EXPECTED_ID"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_late_capture_rejected(self):
        snap,slate,schedule=inputs()
        snap["responses"][0]["retrievedAt"]="2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"RESPONSE_AFTER_CUTOFF"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_raw_tampering_rejected(self):
        snap,slate,schedule=inputs()
        snap["responses"][0]["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"RAW_ESPN_HASH_MISMATCH"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_missing_history_rejected(self):
        snap,slate,schedule=inputs()
        slate[0]["home"]="Unknown Team"
        schedule[0]["home"]="Unknown Team"
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_VERIFIED_HISTORY"):
            build_ab_wednesday_handoff(snap,slate,CUTOFF,schedule)
    def test_never_backfill_november4(self):
        snap,slate,schedule=inputs()
        with self.assertRaises(ValueError):
            build_ab_wednesday_handoff(snap,slate,"2026-09-01T00:00:00Z",schedule)

if __name__=="__main__":
    unittest.main()
