import unittest
from scripts.nfl_publisher_readiness import inspect

class PublisherReadinessTests(unittest.TestCase):
    def test_missing_card_fails(self):
        self.assertIn("FOUR_MODEL_CARD_NOT_FOUND",inspect(None,["1"]))
    def test_missing_game_fails(self):
        self.assertTrue(any("SCHEDULE_COVERAGE_MISMATCH" in x for x in inspect({"games":[]},["1"])))
    def test_missing_each_model_fails(self):
        card={"games":[{"id":"1","home":"H","away":"A","picks":{"A":"H"}}]}
        issues=inspect(card,["1"])
        for model in ("B","C","C-QB"):
            self.assertTrue(any(model+" MISSING_MODEL_WINNER" in x for x in issues))
    def test_valid_winners_pass(self):
        card={"games":[{"id":"1","home":"H","away":"A","picks":{m:"H" for m in ("A","B","C","C-QB")}}]}
        self.assertEqual(inspect(card,["1"]),[])
    def test_duplicate_games_fail(self):
        g={"id":"1","home":"H","away":"A","picks":{m:"H" for m in ("A","B","C","C-QB")}}
        self.assertIn("DUPLICATE_GAME_IDS",inspect({"games":[g,g]},["1"]))
if __name__=="__main__":
    unittest.main()
