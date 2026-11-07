"""Offline, read-only fixture tests; no network or grade publication."""
import unittest
from copy import deepcopy
from nfl_week7_grading_gate import inspect

def fixtures():
    games=[];pilots=[];history=[]
    for i in range(14):
        game={"id":str(400000000+i),"week":7,"date":"2026-10-25T17:00Z",
              "home":"Home"+str(i),"away":"Away"+str(i),
              "baseline30Pick":"Home"+str(i),"experimental0Pick":"Away"+str(i)}
        games.append(game)
        pilots.append({k:game[k] for k in ("id","date","home","away")}|{"pick":game["home"]})
        history.append({k:game[k] for k in ("id","date","home","away","week")}|{
            "season":2026,"homeScore":21,"awayScore":17,"winner":game["home"]})
    return ({"season":2026,"frozenAt":"2026-10-22T10:00Z","games":games},
            {"season":2026,"week":7,"createdAt":"2026-10-21","games":pilots},
            {"games":history})

class GateTests(unittest.TestCase):
    def test_candidate_not_certified_without_independent_provenance(self):
        r=inspect(*fixtures());self.assertEqual(r["eligibleCandidates"],14)
        self.assertFalse(r["certified"])
        self.assertIn("INDEPENDENT_FINAL_PROVENANCE_NOT_VERIFIED",r["failures"])
    def test_verified_fixture_passes(self):
        self.assertTrue(inspect(*fixtures(),verified_snapshot=True)["certified"])
    def test_wrong_id(self):
        a,b,h=fixtures();h["games"][0]["id"]="other"
        self.assertFalse(inspect(a,b,h,verified_snapshot=True)["certified"])
    def test_wrong_team(self):
        a,b,h=fixtures();h["games"][0]["home"]="Wrong"
        self.assertIn("GAME_ID_TEAM_DATE_MISMATCH:"+a["games"][0]["id"],inspect(a,b,h)["failures"])
    def test_wrong_week(self):
        a,b,h=fixtures();b["week"]=9
        self.assertIn("SEASON_WEEK_MISMATCH",inspect(a,b,h)["failures"])
    def test_after_kickoff(self):
        a,b,h=fixtures();a["frozenAt"]="2026-10-26T00:00Z"
        self.assertFalse(inspect(a,b,h,verified_snapshot=True)["certified"])
    def test_wrong_final_winner(self):
        a,b,h=fixtures();h["games"][0]["winner"]="Away0"
        self.assertFalse(inspect(a,b,h,verified_snapshot=True)["certified"])
    def test_invalid_pick(self):
        a,b,h=fixtures();b["games"][0]["pick"]="Other"
        self.assertFalse(inspect(a,b,h,verified_snapshot=True)["certified"])
    def test_no_grade_output(self):
        self.assertFalse(inspect(*fixtures())["gradesPublished"])
if __name__=="__main__":unittest.main()
