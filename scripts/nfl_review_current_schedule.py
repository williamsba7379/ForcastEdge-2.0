#!/usr/bin/env python3
"""Fetch the next complete NFL regular-season slate for the weekly review."""
import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
WEEKS = range(1, 19)


def fetch_board(season, week):
    query = urlencode({"dates": season, "seasontype": 2, "week": week})
    request = Request(f"{URL}?{query}", headers={"User-Agent": "ForecastEdge-Review"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def upcoming_schedule(now, fetch=fetch_board):
    season = now.year - int(now.month < 3)
    weeks = []
    completed = {}
    seen = set()
    for week in WEEKS:
        board = fetch(season, week)
        events = board["events"]
        if not events:
            continue
        if (board.get("season", {}).get("year") != season
                or board.get("season", {}).get("type") != 2
                or board.get("week", {}).get("number") != week):
            raise ValueError(f"ESPN returned the wrong season or week for {season} week {week}")
        games = []
        for event in events:
            game_id = str(event["id"])
            if not game_id.isdigit() or game_id in seen:
                raise ValueError(f"Invalid or duplicate ESPN game ID {game_id}")
            seen.add(game_id)
            date = event["date"]
            kickoff = dt.datetime.fromisoformat(date)
            if kickoff.tzinfo is None:
                raise ValueError(f"Kickoff has no timezone for game {game_id}")
            competition, = event["competitions"]
            teams = {c["homeAway"]: c["team"]["displayName"] for c in competition["competitors"]}
            if len(competition["competitors"]) != 2 or set(teams) != {"home", "away"} or not all(teams.values()):
                raise ValueError(f"Incomplete matchup for game {game_id}")
            games.append((kickoff, {"id": game_id, "date": date, **teams}))
            if event["status"]["type"]["completed"] is True:
                completed[game_id] = {
                    c["homeAway"]: int(c["score"]) for c in competition["competitors"]
                }
        games.sort(key=lambda entry: entry[0])
        weeks.append((games[0][0], games[-1][0], week, games))

    # Keep the current slate in consideration until its last game has kicked off.
    candidates = [entry for entry in weeks if entry[1] > now]
    if not candidates:
        return None
    first, _, week, games = min(candidates, key=lambda entry: entry[0])
    if first <= now:
        raise ValueError(f"Week {week} has already started")
    if first > now + dt.timedelta(days=7):
        return None
    return {"season": season, "source": URL, "completedScores": completed,
            "weeks": [{"week": week, "games": [game for _, game in games]}]}


def verify_history(schedule, history):
    expected = schedule["completedScores"]
    actual = {}
    for game in history["games"]:
        if game["season"] != schedule["season"]:
            continue
        game_id = str(game["id"])
        if game_id in actual:
            raise ValueError(f"Duplicate historical result for game {game_id}")
        actual[game_id] = (game["awayScore"], game["homeScore"])
    mismatched = sorted(game_id for game_id, scores in expected.items()
                        if actual.get(game_id) != (scores["away"], scores["home"]))
    if mismatched:
        raise ValueError("Missing or conflicting final scores for " + ", ".join(mismatched))
    print(f"Verified {len(expected)} current-season final scores")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--verify-history", nargs=2, type=Path, metavar=("SCHEDULE", "HISTORY"))
    args = parser.parse_args()
    if args.verify_history:
        verify_history(*(json.loads(path.read_text()) for path in args.verify_history))
        return
    if args.output is None or args.github_output is None:
        parser.error("--output and --github-output are required when fetching a schedule")
    schedule = upcoming_schedule(dt.datetime.now(dt.timezone.utc))
    if schedule is not None:
        schedule["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        args.output.write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
        week = schedule["weeks"][0]
        print(f'ESPN schedule: {schedule["season"]} week {week["week"]}, {len(week["games"])} games')
    else:
        print("No upcoming regular-season slate within seven days")
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f'has_slate={"true" if schedule is not None else "false"}\n')


if __name__ == "__main__":
    main()
