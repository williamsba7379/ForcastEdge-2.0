#!/usr/bin/env python3
"""Offline checks for the Wednesday schedule and historical coverage."""
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfl_review_current_schedule import upcoming_schedule, verify_history

NOW = dt.datetime.fromisoformat("2026-12-02T11:00:00-05:00")


def event(game_id, date, completed=False):
    return {"id": game_id, "date": date, "status": {"type": {"completed": completed}},
            "competitions": [{"competitors": [
                {"homeAway": "away", "team": {"displayName": "Away"}, "score": "17"},
                {"homeAway": "home", "team": {"displayName": "Home"}, "score": "21"}]}]}


class CurrentSlateTests(unittest.TestCase):
    def setUp(self):
        self.events = {
            12: [event("1201", "2026-11-26T01:00:00Z", completed=True)],
            13: [event("1302", "2026-12-07T20:00:00-05:00"),
                 event("1301", "2026-12-03T20:00:00-05:00")],
            14: [event("1401", "2026-12-10T20:00:00-05:00")],
        }

    def fetch(self, season, week):
        return {"season": {"year": season, "type": 2},
                "week": {"number": week}, "events": self.events.get(week, [])}

    def test_select_next_complete_slate_by_kickoff(self):
        slate = upcoming_schedule(NOW, self.fetch)
        week, = slate["weeks"]
        self.assertEqual(week["week"], 13)
        self.assertEqual([g["id"] for g in week["games"]], ["1301", "1302"])
        self.assertEqual(slate["completedScores"], {"1201": {"away": 17, "home": 21}})

    def test_current_week_already_started_fails_closed(self):
        now = dt.datetime.fromisoformat("2026-12-04T00:00:00-05:00")
        with self.assertRaisesRegex(ValueError, "Week 13 has already started"):
            upcoming_schedule(now, self.fetch)

    def test_outside_horizon_has_no_slate(self):
        self.events.pop(13)
        self.assertIsNone(upcoming_schedule(NOW, self.fetch))

    def test_week_redirect_fails_closed(self):
        def redirect(season, week):
            return self.fetch(season, 13 if week == 12 else week)
        with self.assertRaisesRegex(ValueError, "wrong season or week"):
            upcoming_schedule(NOW, redirect)

    def test_duplicate_game_id_fails_closed(self):
        self.events[14][0]["id"] = "1301"
        with self.assertRaisesRegex(ValueError, "duplicate ESPN game ID"):
            upcoming_schedule(NOW, self.fetch)

    def test_incomplete_matchup_fails_closed(self):
        self.events[13][1]["competitions"][0]["competitors"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete matchup"):
            upcoming_schedule(NOW, self.fetch)

    def test_history_accepts_same_run_scores(self):
        slate = upcoming_schedule(NOW, self.fetch)
        history = {"games": [{"id": "1201", "season": 2026, "awayScore": 17, "homeScore": 21}]}
        verify_history(slate, history)

    def test_history_rejects_missing_or_conflicting_finals(self):
        slate = upcoming_schedule(NOW, self.fetch)
        for games in ([], [{"id": "1201", "season": 2026, "awayScore": 17, "homeScore": 24}]):
            with self.subTest(games=games):
                with self.assertRaisesRegex(ValueError, "Missing or conflicting final scores for 1201"):
                    verify_history(slate, {"games": games})


if __name__ == "__main__":
    unittest.main()
