import unittest
from scripts.nfl_four_model_completeness import validate

class CompletenessTests(unittest.TestCase):
    def test_missing_models_and_fields_fail(self):
        card={"frozenAt":"2026-11-04T16:00:00Z","games":[{"id":"1","date":"2026-11-05T20:00:00Z","home":"H","away":"A","picks":{"A":"H"}}]}
        issues=validate(card,1)
        self.assertTrue(any("C-QB MISSING_OR_INVALID_WINNER" in x for x in issues))
        self.assertTrue(any("A MISSING_POINT_FORECAST" in x for x in issues))
    def test_wrong_coverage_fails(self):
        card={"frozenAt":"2026-11-04T16:00:00Z","games":[{"id":"1","date":"2026-11-05T20:00:00Z","home":"H","away":"A","picks":{}}]}
        self.assertTrue(any("GAME_COVERAGE" in x for x in validate(card,15)))
    def test_post_kickoff_freeze_fails(self):
        card={"frozenAt":"2026-11-06T16:00:00Z","games":[{"id":"1","date":"2026-11-05T20:00:00Z","home":"H","away":"A","picks":{}}]}
        self.assertTrue(any("POST_KICKOFF_FREEZE" in x for x in validate(card)))
    def test_independent_schedule_identity_mismatch_fails(self):
        card={"frozenAt":"2026-11-04T16:00:00Z","games":[{"id":"1","date":"2026-11-05T20:00:00Z","home":"H","away":"A","picks":{}}]}
        source={"games":[{"id":"2","date":"2026-11-05T20:00:00Z"}]}
        self.assertTrue(any("SCHEDULE_ID_MISMATCH" in issue for issue in validate(card,1,source)))
    def test_empty_card_fails(self):
        self.assertEqual(validate({"games":[]}),["MISSING_GAMES"])

if __name__=="__main__":
    unittest.main()
