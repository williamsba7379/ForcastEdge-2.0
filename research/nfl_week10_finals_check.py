"""Check a saved Week 10 slate against two independently captured results feeds.

Run as a module with a schedule snapshot and two normalized result JSON files.
Each results file has a games array with id, date, away, home, status, awayScore,
and homeScore. An incomplete or conflicting check exits 1 and emits no game rows.
This checker prints to stdout and does not write history.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Kickoff timestamp must include a time zone")
    return result


def index_games(games, label):
    indexed = {}
    for game in games:
        game_id = str(game["id"])
        if not game_id.isdecimal() or game_id in indexed:
            raise ValueError(f"{label}: invalid or duplicate game ID {game_id}")
        indexed[game_id] = game
    return indexed


def verify(schedule, primary, crosscheck):
    if schedule["season"] != 2026:
        raise ValueError("Expected the 2026 schedule")
    weeks = [week for week in schedule["weeks"] if week["week"] == 10]
    if len(weeks) != 1 or len(weeks[0]["games"]) != 14:
        raise ValueError("Expected one 14-game Week 10 slate")
    expected = index_games(weeks[0]["games"], "schedule")
    feeds = (
        index_games(primary["games"], "primary"),
        index_games(crosscheck["games"], "crosscheck"),
    )
    issues = []
    games = []
    for label, feed in zip(("primary", "crosscheck"), feeds):
        for game_id in sorted(feed.keys() - expected.keys()):
            issues.append(f"{label}: unexpected game {game_id}")
    for game_id, game in expected.items():
        a, b = (feed.get(game_id) for feed in feeds)
        if any(row is None or row.get("status") != "STATUS_FINAL" for row in (a, b)):
            issues.append(f"{game_id}: final pending or missing")
            continue
        for label, row in zip(("primary", "crosscheck"), (a, b)):
            if (
                (row["away"], row["home"]) != (game["away"], game["home"])
                or timestamp(row["date"]) != timestamp(game["date"])
            ):
                issues.append(f"{game_id}: {label} matchup or kickoff mismatch")
        scores = [(row.get("awayScore"), row.get("homeScore")) for row in (a, b)]
        if any(type(score) is not int or score < 0 for pair in scores for score in pair):
            issues.append(f"{game_id}: invalid final score")
            continue
        if scores[0] != scores[1]:
            issues.append(f"{game_id}: final scores disagree")
            continue
        away_score, home_score = scores[0]
        winner = "Tie"
        if away_score != home_score:
            winner = game["away"] if away_score > home_score else game["home"]
        games.append({
            "season": 2026, "week": 10, "id": game_id, "date": game["date"],
            "away": game["away"], "home": game["home"], "awayScore": away_score,
            "homeScore": home_score, "winner": winner,
        })
    if issues:
        return {"status": "BLOCKED", "expectedGames": 14, "issues": issues}
    return {"status": "DRAFT_REHEARSAL_RESULTS_ONLY", "games": games}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("schedule", "primary", "crosscheck"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        result = verify(*(json.loads(path.read_text(encoding="utf-8"))
                          for path in (args.schedule, args.primary, args.crosscheck)))
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        result = {"status": "BLOCKED", "issues": [str(error)]}
    print(json.dumps(result, indent=2))
    return int(result["status"] == "BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
