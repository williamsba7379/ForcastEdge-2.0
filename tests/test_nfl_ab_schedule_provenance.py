"""Fail-closed independent schedule and capture completion tests."""
import copy
import json
import unittest
from scripts.nfl_ab_schedule_provenance import capture_schedule_response,verify_schedule_evidence
from scripts.nfl_ab_wednesday_handoff import build_verified_wednesday_handoff
from test_nfl_ab_wednesday_handoff import inputs,CUTOFF

def evidence(schedule):
    events=[]
    for g in schedule:
        events.append({"id":g["id"],"date":g["date"],"competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":g["home"]}},
            {"homeAway":"away","team":{"displayName":g["away"]}}]}]})
    return capture_schedule_response(json.dumps({"events":events}).encode(),"2026-11-04T15:59:00Z")

def setup():
    snap,slate,schedule=inputs()
    snap["capturedAt"]="2026-11-04T15:59:30Z"
    return snap,slate,schedule,evidence(schedule)

class ProvenanceTests(unittest.TestCase):
    def test_15_game_verified_handoff(self):
        snap,slate,schedule,proof=setup()
        result=build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
        self.assertEqual(len(result["games"]),15)
        self.assertEqual(result["scheduleProvenance"]["gameCount"],15)
        self.assertFalse(result["publishable"])
    def test_late_schedule_rejected(self):
        snap,slate,schedule,proof=setup()
        proof["retrievedAt"]="2026-11-04T16:01:00Z"
        with self.assertRaisesRegex(ValueError,"SCHEDULE_AFTER_CUTOFF"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_schedule_hash_tampering_rejected(self):
        snap,slate,schedule,proof=setup()
        proof["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SCHEDULE_HASH_MISMATCH"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_schedule_missing_game_rejected(self):
        snap,slate,schedule,proof=setup()
        with self.assertRaisesRegex(ValueError,"SCHEDULE_COVERAGE_MISMATCH"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule[:-1],proof)
    def test_schedule_matchup_changed_rejected(self):
        snap,slate,schedule,proof=setup()
        schedule[0]["away"]="Different Team"
        with self.assertRaisesRegex(ValueError,"SCHEDULE_IDENTITY_MISMATCH"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_capture_completion_after_cutoff_rejected(self):
        snap,slate,schedule,proof=setup()
        snap["capturedAt"]="2026-11-04T16:00:01Z"
        with self.assertRaisesRegex(ValueError,"CAPTURE_COMPLETED_AFTER_CUTOFF"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_capture_before_response_rejected(self):
        snap,slate,schedule,proof=setup()
        snap["capturedAt"]="2026-11-04T15:00:00Z"
        with self.assertRaisesRegex(ValueError,"CAPTURE_BEFORE_LAST_RESPONSE"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_capture_cutoff_mismatch_rejected(self):
        snap,slate,schedule,proof=setup()
        snap["cutoff"]="2026-11-04T15:00:00Z"
        with self.assertRaisesRegex(ValueError,"CAPTURE_CUTOFF_MISMATCH"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,proof)
    def test_missing_evidence_rejected(self):
        snap,slate,schedule,proof=setup()
        with self.assertRaisesRegex(ValueError,"MISSING_SCHEDULE_PROVENANCE"):
            build_verified_wednesday_handoff(snap,slate,CUTOFF,schedule,None)
if __name__=="__main__":
    unittest.main()
