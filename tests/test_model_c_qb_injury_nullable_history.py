"""Review-only QB injury audit tolerates nullable historical passer fields."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model_c_qb_injury_audit_v2 import build

class NullableHistoricalQB(unittest.TestCase):
    def test_null_passer_and_date_do_not_crash_or_apply_points(self):
        draft={"season":2026,"week":10,"games":[{"id":"game1","date":"2026-11-12T20:15:00-05:00","home":"Home","away":"Away","quarterbacks":{"home":{"reportedQuarterbacks":[{"name":"Starter","status":"out"}]}}}]}
        shadow={"games":[{"id":"game1","qbAdjustments":{"home":{"status":"NO_VERIFIED_QB"}}}]}
        history={"records":[{"team":"Home","primaryPasser":None,"gameDate":None},{"team":"Home","primaryPasser":"Starter","gameDate":"2026-11-01T20:00:00Z"}]}
        result=build(draft,shadow,history)
        self.assertEqual(result["reviewCount"],1)
        self.assertEqual(result["alerts"][0]["priorPrimaryPasserGames"]["Starter"],1)
        self.assertEqual(result["alerts"][0]["pointsAdjustment"],0)
        self.assertEqual(result["alerts"][0]["status"],"UNMODELED_HUMAN_REVIEW_REQUIRED")
if __name__=="__main__": unittest.main()
