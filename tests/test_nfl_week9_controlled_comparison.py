import copy
import unittest
from scripts.nfl_week9_controlled_comparison import compare

def fixture():
    history={"games":[]}
    candidate={"games":[]}
    frozen={"frozenAt":"2026-11-04T17:18:26+00:00","games":[{"id":str(i),"date":"2026-11-08T18:00Z","home":"H"+str(i),"away":"A"+str(i),"qbHomeEdgeAdjustment":0,"picks":{"A":"H"+str(i),"B":"H"+str(i),"C":"H"+str(i),"C-QB":"H"+str(i)}} for i in range(15)]}
    return history,candidate,frozen
class Tests(unittest.TestCase):
    def test_fifteen_rows_zero_change(self):
        h,c,f=fixture();x=compare(h,c,f,{"teams":{}},{"games":{}})
        self.assertEqual(x["gameCount"],15);self.assertEqual(x["changedGameCount"],0)
        self.assertFalse(x["promotionAuthorized"])
    def test_nonzero_qb_blocks(self):
        h,c,f=fixture();f["games"][0]["qbHomeEdgeAdjustment"]=2
        with self.assertRaises(ValueError):compare(h,c,f,{"teams":{}},{"games":{}})
    def test_verified_qb_blocks(self):
        h,c,f=fixture()
        with self.assertRaises(ValueError):compare(h,c,f,{"teams":{"H0":{"starter":"X"}}},{"games":{}})
    def test_verified_adjustment_feed_blocks(self):
        h,c,f=fixture()
        with self.assertRaises(ValueError):compare(h,c,f,{"teams":{}},{"games":{"0":{"home":{"points":2}}}})
    def test_baseline_mismatch_blocks(self):
        h,c,f=fixture();f["games"][0]["picks"]["C"]="A0"
        with self.assertRaises(ValueError):compare(h,c,f,{"teams":{}},{"games":{}})
    def test_duplicate_game_blocks(self):
        h,c,f=fixture();f["games"][1]["id"]="0"
        with self.assertRaises(ValueError):compare(h,c,f,{"teams":{}},{"games":{}})
    def test_no_mutation(self):
        h,c,f=fixture();orig=copy.deepcopy(f)
        compare(h,c,f,{"teams":{}},{"games":{}})
        self.assertEqual(f,orig)
if __name__=="__main__":unittest.main()
