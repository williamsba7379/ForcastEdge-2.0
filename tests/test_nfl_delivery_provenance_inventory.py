import unittest
from research.nfl_delivery_provenance_inventory import audit

NOW="2026-11-11T17:30:00Z"
GAME={"id":"1","date":"2026-11-13T01:15:00Z","away":"Away","home":"Home"}
SCHEDULE={"season":2026,"weeks":[{"week":10,"games":[GAME]}]}
CARD={"season":2026,"week":10,"games":[dict(GAME,picks={"A":"Away","B":"Home","C":"Away","C-QB":"Home"})]}

class ProvenanceInventoryTests(unittest.TestCase):
    def test_missing_evidence_fails_all_four(self):
        report=audit(SCHEDULE,CARD,NOW)
        self.assertEqual(report["expectedRows"],4)
        self.assertEqual(report["completeRows"],0)
        self.assertTrue(all("projectedHomeScore" in r["missing"] for r in report["rows"]))
        self.assertTrue(all("spreadPick" in r["missing"] for r in report["rows"]))
        self.assertTrue(all(r["noBet"] for r in report["rows"]))
        self.assertFalse(report["published"])
    def test_cutoff_is_11_am_eastern(self):
        self.assertEqual(audit(SCHEDULE,CARD,NOW)["cutoffET"],"2026-11-11T11:00:00-05:00")
    def test_missing_qb_is_explicit(self):
        rows=audit(SCHEDULE,CARD,NOW)["rows"]
        self.assertNotIn("OFFICIAL_GAME_SPECIFIC_QB",rows[0]["missing"])
        self.assertIn("OFFICIAL_GAME_SPECIFIC_QB",rows[2]["missing"])
    def test_stale_card_has_no_winner(self):
        report=audit(SCHEDULE,dict(CARD,week=8),NOW)
        self.assertTrue(all("winner" in r["missing"] for r in report["rows"]))
    def test_future_capture_cannot_pass_cutoff(self):
        evidence={"1":{"A":{"generatedAt":"2026-11-11T17:20:00Z"}}}
        report=audit(SCHEDULE,CARD,NOW,evidence=evidence)
        self.assertIn("VERIFIED_PRE_11AM_MODEL_CAPTURE",report["rows"][0]["missing"])

if __name__=="__main__":
    unittest.main()
