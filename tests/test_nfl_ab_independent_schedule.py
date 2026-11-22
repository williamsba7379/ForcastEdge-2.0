"""Second-source fail-closed schedule comparison; offline synthetic fixtures only."""
import json
import unittest
from scripts.nfl_ab_independent_schedule import capture_official_schedule,verify_independent_schedule
from test_nfl_ab_schedule_provenance import setup,CUTOFF

def second(schedule):
    games=[{k:g[k] for k in ("date","home","away")} for g in schedule]
    raw=json.dumps({"games":games}).encode()
    return capture_official_schedule(raw,"2026-11-04T15:58:00Z","https://www.nfl.com/schedules/2026/reg9/")

class IndependentScheduleTests(unittest.TestCase):
    def test_two_matching_sources(self):
        _,_,schedule,espn=setup()
        result=verify_independent_schedule(espn,second(schedule),CUTOFF,schedule)
        self.assertTrue(result["independentSourceVerified"])
        self.assertEqual(result["gameCount"],15)
    def test_missing_second_source(self):
        _,_,schedule,espn=setup()
        with self.assertRaisesRegex(ValueError,"MISSING_SECOND_SOURCE"):
            verify_independent_schedule(espn,None,CUTOFF,schedule)
    def test_missing_game(self):
        _,_,schedule,espn=setup()
        proof=second(schedule[:-1])
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_SCHEDULE_MISMATCH"):
            verify_independent_schedule(espn,proof,CUTOFF,schedule)
    def test_changed_kickoff(self):
        _,_,schedule,espn=setup()
        altered=[dict(g) for g in schedule]
        altered[0]["date"]="2026-11-10T18:00:00Z"
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_SCHEDULE_MISMATCH"):
            verify_independent_schedule(espn,second(altered),CUTOFF,schedule)
    def test_late_second_source(self):
        _,_,schedule,espn=setup()
        proof=second(schedule)
        proof["retrievedAt"]="2026-11-04T16:01:00Z"
        with self.assertRaisesRegex(ValueError,"SECOND_SOURCE_AFTER_CUTOFF"):
            verify_independent_schedule(espn,proof,CUTOFF,schedule)
    def test_hash_tampering(self):
        _,_,schedule,espn=setup()
        proof=second(schedule)
        proof["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SECOND_SOURCE_HASH_MISMATCH"):
            verify_independent_schedule(espn,proof,CUTOFF,schedule)
    def test_espn_reuse_rejected(self):
        _,_,schedule,espn=setup()
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_SECOND_SOURCE"):
            verify_independent_schedule(espn,espn,CUTOFF,schedule)
    def test_duplicate_second_game(self):
        _,_,schedule,espn=setup()
        altered=[dict(g) for g in schedule]
        altered[1]=dict(altered[0])
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_SCHEDULE_MISMATCH"):
            verify_independent_schedule(espn,second(altered),CUTOFF,schedule)
if __name__=="__main__":
    unittest.main()
