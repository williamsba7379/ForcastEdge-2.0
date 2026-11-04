import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_market_totals_compare import compare

def research():
    return {"season":2026,"week":9,"sourceComparisonFrozenAt":"2026-11-04T16:00:00Z",
            "games":[{"id":"1","date":"2026-11-08T18:00:00Z","models":{"A":{"projectedTotal":42}}}]}

class MarketWeekIsolationTests(unittest.TestCase):
    def test_stale_empty_quote_feed_does_not_block_research(self):
        out=compare(research(),{"season":2026,"week":8,"games":[]})
        self.assertEqual(out["status"],"NO_SOURCED_MARKET_LINES")
        self.assertEqual(out["marketLinesAvailable"],0)
        self.assertNotIn("overUnderPick",out["games"][0]["models"]["A"])
    def test_nonempty_mismatched_week_rejected(self):
        with self.assertRaisesRegex(ValueError,"Market week mismatch"):
            compare(research(),{"season":2026,"week":8,"games":[{"id":"1","total":42}]})
    def test_matching_empty_week(self):
        self.assertEqual(compare(research(),{"season":2026,"week":9,"games":[]})["marketLinesAvailable"],0)
if __name__=="__main__":unittest.main()
