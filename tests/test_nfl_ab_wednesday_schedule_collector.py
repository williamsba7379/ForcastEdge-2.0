"""Offline tests for isolated ESPN schedule collector and strict handoff."""
import json
import unittest
from scripts.nfl_ab_wednesday_schedule_collector import collect_wednesday_schedule
from scripts.nfl_ab_wednesday_handoff import build_verified_wednesday_handoff
from scripts.nfl_ab_schedule_provenance import capture_schedule_response,verify_schedule_evidence
from test_nfl_ab_wednesday_handoff import inputs,CUTOFF

def fake_raw(schedule):
    return json.dumps({"events":[{"id":g["id"],"date":g["date"],
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":g["home"]}},
            {"homeAway":"away","team":{"displayName":g["away"]}}]}]} for g in schedule]}).encode()

class CollectorTests(unittest.TestCase):
    def test_capture_and_strict_15_game_handoff(self):
        snapshot,fixtures,schedule=inputs()
        url_seen=[]
        def fetch(url):
            url_seen.append(url)
            return fake_raw(schedule),"2026-11-04T15:59:00Z"
        result=collect_wednesday_schedule(2026,9,CUTOFF,fetch=fetch)
        self.assertEqual(len(result["expectedSchedule"]),15)
        self.assertIn("week=9",url_seen[0])
        self.assertEqual(len(result["scheduleEvidence"]["responseSha256"]),64)
        self.assertFalse(result["publishable"])
        snapshot["capturedAt"]="2026-11-04T15:59:30Z"
        handoff=build_verified_wednesday_handoff(snapshot,fixtures,CUTOFF,
            result["expectedSchedule"],result["scheduleEvidence"])
        self.assertEqual(len(handoff["games"]),15)
        self.assertEqual(handoff["scheduleProvenance"]["gameCount"],15)
    def test_late_fetch_rejected(self):
        _,_,schedule=inputs()
        with self.assertRaisesRegex(ValueError,"SCHEDULE_AFTER_CUTOFF"):
            collect_wednesday_schedule(2026,9,CUTOFF,
                fetch=lambda url:(fake_raw(schedule),"2026-11-04T16:01:00Z"))
    def test_empty_week_rejected(self):
        with self.assertRaisesRegex(ValueError,"EMPTY_WEEK_SCHEDULE"):
            collect_wednesday_schedule(2026,9,CUTOFF,
                fetch=lambda url:(b'{"events":[]}',"2026-11-04T15:59:00Z"))
    def test_invalid_week_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SEASON_WEEK"):
            collect_wednesday_schedule(2026,19,CUTOFF,fetch=lambda url:None)
    def test_schedule_source_spoof_rejected(self):
        _,_,schedule=inputs()
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_SCHEDULE_SOURCE"):
            capture_schedule_response(fake_raw(schedule),"2026-11-04T15:59:00Z",
                "https://site.api.espn.com.evil.test/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=9")
    def test_schedule_bytes_tamper_rejected(self):
        _,_,schedule=inputs()
        result=collect_wednesday_schedule(2026,9,CUTOFF,
            fetch=lambda url:(fake_raw(schedule),"2026-11-04T15:59:00Z"))
        result["scheduleEvidence"]["responseSha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"SCHEDULE_HASH_MISMATCH"):
            verify_schedule_evidence(result["scheduleEvidence"],CUTOFF,result["expectedSchedule"])
    def test_independent_matchup_mismatch_rejected(self):
        _,_,schedule=inputs()
        result=collect_wednesday_schedule(2026,9,CUTOFF,
            fetch=lambda url:(fake_raw(schedule),"2026-11-04T15:59:00Z"))
        result["expectedSchedule"][0]["home"]="Wrong Team"
        with self.assertRaisesRegex(ValueError,"SCHEDULE_IDENTITY_MISMATCH"):
            verify_schedule_evidence(result["scheduleEvidence"],CUTOFF,result["expectedSchedule"])
if __name__=="__main__":
    unittest.main()
