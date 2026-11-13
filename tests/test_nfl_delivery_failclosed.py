import datetime as dt
import unittest
from research.nfl_delivery_failclosed import validate

NOW="2026-11-11T16:00:00Z"
G={"id":"1","date":"2026-11-13T01:15:00Z","away":"Away","home":"Home"}
S={"season":2026,"weeks":[{"week":10,"games":[G]}]}
C={"season":2026,"week":10,"games":[dict(G,picks={"A":"Away","B":"Home","C":"Away","C-QB":"Home"})]}
class FailClosedTests(unittest.TestCase):
    def test_missing_card_fails(self):
        self.assertIn("MISSING_OR_STALE_FROZEN_CARD",validate(S,None,NOW)["issues"])
    def test_stale_week_fails(self):
        self.assertIn("MISSING_OR_STALE_FROZEN_CARD",validate(S,dict(C,week=8),NOW)["issues"])
    def test_winner_only_fails(self):
        r=validate(S,C,NOW)
        self.assertEqual(r["expectedRows"],4)
        self.assertEqual(r["validCompleteRows"],0)
        self.assertEqual(len(r["unavailable"]),4)
    def test_missing_qb_evidence_fails(self):
        evidence={"1":{m:{"projectedAwayScore":17,"projectedHomeScore":20,"projectedMargin":3,"projectedTotal":37,"modelArtifactId":m,"engineSha256":"abc","inputSha256":"def","generatedAt":NOW} for m in ("A","B","C","C-QB")}}
        r=validate(S,C,NOW,source_evidence=evidence)
        self.assertEqual(r["validCompleteRows"],2)
        self.assertEqual(r["status"],"FAILED_COMPLETENESS_CHECK")
    def test_complete_evidence_passes(self):
        evidence={"1":{m:{"projectedAwayScore":17,"projectedHomeScore":20,"projectedMargin":3,"projectedTotal":37,"modelArtifactId":m,"engineSha256":"abc","inputSha256":"def","generatedAt":NOW} for m in ("A","B","C","C-QB")}}
        qb={"1":{m:{"officialGameSpecific":True} for m in ("C","C-QB")}}
        self.assertEqual(validate(S,C,NOW,source_evidence=evidence,qb_evidence=qb)["status"],"PASS")
if __name__=="__main__":
    unittest.main()
