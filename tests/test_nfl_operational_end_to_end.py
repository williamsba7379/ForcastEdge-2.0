"""Isolated, in-memory Wednesday rehearsal of actual ForecastEdge freeze, market, grading code."""
import datetime as dt
import json
import pathlib
import sys
import unittest
from copy import deepcopy

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"research"))
from nfl_four_model_head_to_head import freeze,grade as grade_winners
from nfl_market_totals_compare import compare
from nfl_four_model_totals_grade import grade as grade_totals
from nfl_operational_readiness import audit, rehearse_handoff

NOW=dt.datetime.fromisoformat("2026-11-04T16:00:00+00:00")
def fixture():
    # Archived Week 9 schedule, loaded but never modified.
    schedule=json.loads((ROOT/"data/nfl-schedule.json").read_text())
    week=next(w for w in schedule["weeks"] if w["week"]==9)
    games=week["games"]
    def game(g):
        return {"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
                "pick":g["home"],"homeEdgePoints":1.5}
    draft={"season":2026,"week":9,"generatedAt":"2026-11-04T15:59:00Z",
           "games":[game(g) for g in games]}
    shadow={"season":2026,"week":9,"generatedAt":"2026-11-04T15:59:30Z",
            "status":"EXPERIMENTAL_SHADOW_ONLY","games":[{
                "id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
                "originalPick":g["home"],"originalHomeEdgePoints":1.5,
                "experimentalPick":g["home"],"qbHomeEdgeAdjustment":0,
                "qbAdjustments":{"home":{"status":"UNCONFIRMED"},"away":{"status":"UNCONFIRMED"}}
            } for g in games]}
    return {"season":2026,"week":9,"games":games},draft,shadow

class Rehearsal(unittest.TestCase):
    def test_archived_schedule_and_real_freeze(self):
        schedule,draft,shadow=fixture()
        self.assertEqual(len(schedule["games"]),15)
        card=freeze(draft,shadow,{"games":[]},NOW)
        self.assertEqual(len(card["games"]),15)
        self.assertEqual(set(card["games"][0]["picks"]),{"A","B","C","C-QB"})
        self.assertEqual({g["id"] for g in card["games"]},{str(g["id"]) for g in schedule["games"]})
        self.assertEqual(card["status"],"FROZEN_PREKICKOFF")
        self.assertTrue(all(g["qbAdjustments"]["home"]["status"]=="UNCONFIRMED" for g in card["games"]))
        readiness=audit(schedule,draft,shadow,card,NOW.isoformat(),official_qb_evidence=False)
        self.assertIn("QB_VERIFICATION_MISSING",readiness["reasons"])
        self.assertFalse(readiness["productionReady"])
    def test_same_slate_outputs_pass_directly_to_four_model_handoff(self):
        schedule, draft, shadow = fixture()
        archived = {"season": schedule["season"], "weeks": [schedule]}
        card = rehearse_handoff(archived, draft, shadow, {"games": []}, NOW.isoformat())
        self.assertEqual(card["status"], "RESEARCH_REHEARSAL_ONLY")
        self.assertEqual({g["id"] for g in card["games"]}, {g["id"] for g in schedule["games"]})
        self.assertTrue(all(set(g["picks"]) == {"A", "B", "C", "C-QB"} for g in card["games"]))

    def test_handoff_rejects_stale_mismatched_and_late_outputs(self):
        for field, value, error in (
            ("week", 8, "week mismatch"),
            ("generatedAt", "2026-11-03T23:00:00Z", "timestamp outside"),
            ("generatedAt", "2026-11-04T15:58:00Z", "timestamp outside"),
            ("generatedAt", "2026-11-04T16:00:01Z", "timestamp outside"),
        ):
            with self.subTest(field=field, value=value):
                schedule, draft, shadow = fixture()
                shadow[field] = value
                archived = {"season": schedule["season"], "weeks": [schedule]}
                with self.assertRaisesRegex(ValueError, error):
                    rehearse_handoff(archived, draft, shadow, {"games": []}, NOW.isoformat())
        schedule, draft, shadow = fixture()
        shadow["games"][0]["date"] = "2026-11-06T02:00:00Z"
        archived = {"season": schedule["season"], "weeks": [schedule]}
        with self.assertRaisesRegex(ValueError, "schedule mismatch"):
            rehearse_handoff(archived, draft, shadow, {"games": []}, NOW.isoformat())

    def test_market_missing_is_no_bet(self):
        schedule,draft,shadow=fixture()
        g=schedule["games"][0]
        research={"season":2026,"week":9,"sourceComparisonFrozenAt":NOW.isoformat(),
                  "games":[{"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
                  "models":{n:{"projectedTotal":40,"winnerPick":g["home"]} for n in ("A","B","C","C-QB")}}]}
        result=compare(research,{"season":2026,"week":9,"games":[]})
        self.assertEqual(result["marketLinesAvailable"],0)
        self.assertEqual(result["status"],"NO_SOURCED_MARKET_LINES")
        self.assertTrue(all("overUnderPick" not in m for m in result["games"][0]["models"].values()))
    def test_market_week_mismatch_fails_closed(self):
        schedule,draft,shadow=fixture()
        research={"season":2026,"week":9,"sourceComparisonFrozenAt":NOW.isoformat(),"games":[]}
        with self.assertRaisesRegex(ValueError,"Market week mismatch"):
            compare(research,{"season":2026,"week":8,"games":[]})
    def test_next_day_winner_grading_and_pending(self):
        schedule,draft,shadow=fixture()
        card=freeze(draft,shadow,{"games":[]},NOW)
        first=card["games"][0]
        original=deepcopy(card)
        final={"id":first["id"],"home":first["home"],"away":first["away"],
               "scoreHome":21,"scoreAway":14,"status":"FINAL","winner":first["home"]}
        graded=grade_winners(card,{"games":[final]})
        self.assertEqual(graded["summary"]["A"]["wins"],1)
        self.assertEqual(graded["summary"]["B"]["wins"],1)
        self.assertEqual(graded["summary"]["C"]["wins"],1)
        self.assertEqual(graded["summary"]["C-QB"]["wins"],1)
        self.assertEqual(graded["summary"]["A"]["pending"],14)
        self.assertIsNone(original["games"][0]["winner"])
        self.assertEqual(graded["games"][0]["picks"],original["games"][0]["picks"])
    def test_totals_grading_no_line_no_bet(self):
        schedule,draft,shadow=fixture()
        g=schedule["games"][0]
        report={"games":[{"id":g["id"],"home":g["home"],"away":g["away"],
            "models":{n:{"winnerPick":g["home"],"projectedTotal":42} for n in ("A","B","C","C-QB")}}]}
        final={"games":[{"id":g["id"],"home":g["home"],"away":g["away"],
                        "scoreHome":21,"scoreAway":14,"status":"FINAL","winner":g["home"]}]}
        result=grade_totals(report,final)
        for n in ("A","B","C","C-QB"):
            self.assertEqual(result["gradingSummary"][n]["winnerWins"],1)
            self.assertEqual(result["gradingSummary"][n]["totalsWins"],0)
            self.assertEqual(result["gradingSummary"][n]["totalsLosses"],0)
            self.assertEqual(result["gradingSummary"][n]["meanAbsoluteTotalError"],7)
    def test_post_cutoff_qb_rejected(self):
        schedule,draft,shadow=fixture()
        card=freeze(draft,shadow,{"games":[]},NOW)
        draft["generatedAt"]="2026-11-04T16:49:00Z"
        readiness=audit(schedule,draft,shadow,card,NOW.isoformat())
        self.assertIn("POST_CUTOFF_C",readiness["reasons"])
    def test_week8_rejected(self):
        schedule,draft,shadow=fixture()
        shadow["week"]=8
        with self.assertRaisesRegex(ValueError,"Week mismatch"):
            freeze(draft,shadow,{"games":[]},NOW)
if __name__=="__main__":unittest.main()
