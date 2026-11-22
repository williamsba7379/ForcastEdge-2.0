import unittest
from scripts.nfl_ab_archive_adapter import inspect_ab_archive,adapt

def archive():
    return {"status":"frozen_pre_kickoff","frozenAt":"2026-11-04T11:46:43-05:00","games":[
        {"id":"1","date":"2026-11-06T01:15:00Z","home":"Home","away":"Away",
         "baseline30Pick":"Home","experimental0Pick":"Home","method":"model"}]}
class ABArchiveTests(unittest.TestCase):
    def test_valid_archive(self):
        self.assertEqual(inspect_ab_archive(archive(),["1"]),[])
    def test_same_winner_kept_twice(self):
        self.assertEqual(adapt(archive())[0]["picks"],{"A":"Home","B":"Home"})
    def test_postkickoff_freeze_rejected(self):
        a=archive();a["frozenAt"]="2026-11-06T02:00:00Z"
        self.assertTrue(any("AFTER_KICKOFF" in i for i in inspect_ab_archive(a)))
    def test_missing_model_b_rejected(self):
        a=archive();del a["games"][0]["experimental0Pick"]
        self.assertTrue(any("B MISSING" in i for i in inspect_ab_archive(a)))
    def test_schedule_mismatch_rejected(self):
        self.assertIn("AB_SCHEDULE_MISMATCH",inspect_ab_archive(archive(),["2"]))
    def test_non_model_method_rejected(self):
        a=archive();a["games"][0]["method"]="fallback"
        self.assertTrue(any("UNVERIFIED_MODEL_METHOD" in i for i in inspect_ab_archive(a)))
if __name__=="__main__":
    unittest.main()
