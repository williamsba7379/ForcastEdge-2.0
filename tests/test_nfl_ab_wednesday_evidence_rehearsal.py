"""Offline fail-closed tests for manual NFL/ESPN evidence rehearsal."""
import base64
import datetime as dt
import hashlib
import json
import unittest
from unittest.mock import patch
from scripts.nfl_ab_wednesday_evidence_rehearsal import compare_captures
from scripts.nfl_ab_schedule_provenance import capture_schedule_response

CUTOFF="2026-11-18T16:00:00Z"
AT="2026-11-18T15:50:00Z"
KICKOFF="2026-11-19T01:15:00Z"
SNIPPET="Giants at Commanders, Thursday, November 18th, 8:15 PM"
RAW=("<html><body>"+SNIPPET+"</body></html>").encode()
URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=11"

def fixture():
    nfl={"kind":"RAW_NFL_HTML_CAPTURE","sourceUrl":"https://www.nfl.com/schedules/2026/by-week/week-11",
         "retrievedAt":AT,"responseSha256":hashlib.sha256(RAW).hexdigest(),
         "rawBodyBase64":base64.b64encode(RAW).decode()}
    reviewed=[{"date":KICKOFF,"home":"Washington Commanders","away":"New York Giants","sourceSnippet":SNIPPET}]
    event={"id":"test-espn-id","date":KICKOFF,"competitions":[{"competitors":[
        {"homeAway":"home","team":{"displayName":"Washington Commanders"}},
        {"homeAway":"away","team":{"displayName":"New York Giants"}}]}]}
    raw=json.dumps({"events":[event]}).encode()
    espn={"season":2026,"week":11,"expectedSchedule":[{"id":"test-espn-id","date":KICKOFF,
          "home":"Washington Commanders","away":"New York Giants","season":2026}],
          "scheduleEvidence":capture_schedule_response(raw,AT,URL)}
    return nfl,reviewed,espn

class RehearsalTests(unittest.TestCase):
    def test_verified_mapping_and_nonproduction(self):
        result=compare_captures(*fixture(),CUTOFF)
        self.assertEqual(result["verifiedEspnIds"],["test-espn-id"])
        self.assertFalse(result["productionReady"])
        self.assertFalse(result["officialFrozen"])
    def test_tampered_official_bytes_rejected(self):
        nfl,reviewed,espn=fixture()
        nfl["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"OFFICIAL_RAW_HASH_MISMATCH"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_tampered_espn_bytes_rejected(self):
        nfl,reviewed,espn=fixture()
        espn["scheduleEvidence"]["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SCHEDULE_HASH_MISMATCH"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_missing_official_snippet_rejected(self):
        nfl,reviewed,espn=fixture()
        reviewed[0]["sourceSnippet"]="not on page"
        with self.assertRaisesRegex(ValueError,"REVIEW_SNIPPET_NOT_IN_RAW_HTML"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_kickoff_mismatch_rejected(self):
        nfl,reviewed,espn=fixture()
        reviewed[0]["date"]="2026-11-19T02:15:00Z"
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_SCHEDULE_MISMATCH"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_late_nfl_capture_rejected(self):
        nfl,reviewed,espn=fixture()
        nfl["retrievedAt"]="2026-11-18T16:00:01Z"
        with self.assertRaisesRegex(ValueError,"OFFICIAL_RESPONSE_AFTER_CUTOFF"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_older_than_24_hours_rejected(self):
        nfl,reviewed,espn=fixture()
        nfl["retrievedAt"]="2026-11-17T15:00:00Z"
        with self.assertRaisesRegex(ValueError,"CAPTURE_OUTSIDE_24H_WINDOW"):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_extra_espn_game_rejected(self):
        nfl,reviewed,espn=fixture()
        espn["expectedSchedule"].append(dict(espn["expectedSchedule"][0],id="extra"))
        with self.assertRaises(ValueError):
            compare_captures(nfl,reviewed,espn,CUTOFF)
    def test_duplicate_reviewed_game_rejected(self):
        nfl,reviewed,espn=fixture()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_REVIEWED_GAME"):
            compare_captures(nfl,reviewed+reviewed,espn,CUTOFF)
    def test_original_inputs_not_mutated(self):
        nfl,reviewed,espn=fixture()
        before=json.dumps([nfl,reviewed,espn],sort_keys=True)
        compare_captures(nfl,reviewed,espn,CUTOFF)
        self.assertEqual(json.dumps([nfl,reviewed,espn],sort_keys=True),before)

if __name__=="__main__":
    unittest.main()
