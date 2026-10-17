#!/usr/bin/env python3
"""Transparent NFL team-strength baseline and chronological walk-forward evaluation.

Only completed games are used. Every prediction is computed from games
strictly earlier than its kickoff, avoiding look-ahead leakage.
Not a trained or calibrated probability model.
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE = Path("data/nfl-historical-results.json")
OUTPUT = Path("data/nfl-team-strength.json")


def kickoff(game):
    return datetime.fromisoformat(game["date"].replace("Z", "+00:00"))


def team_metrics(prior_games, team):
    rows = []
    for game in prior_games:
        if game["home"] == team:
            rows.append((game["homeScore"], game["awayScore"]))
        elif game["away"] == team:
            rows.append((game["awayScore"], game["homeScore"]))
    n = len(rows)
    if not n:
        return {"games": 0, "pointsFor": None, "pointsAgainst": None,
                "pointDifferential": None, "recentDifferential": None, "winPct": None}
    wins = sum(a > b for a, b in rows)
    ties = sum(a == b for a, b in rows)
    recent = rows[-3:]
    return {
        "games": n,
        "pointsFor": round(sum(a for a, _ in rows) / n, 2),
        "pointsAgainst": round(sum(b for _, b in rows) / n, 2),
        "pointDifferential": round(sum(a - b for a, b in rows) / n, 2),
        "recentDifferential": round(sum(a - b for a, b in recent) / len(recent), 2),
        "winPct": round((wins + 0.5 * ties) / n, 4),
    }


def strength(metrics):
    if metrics["games"] == 0:
        return 0.0
    # A deliberately simple baseline score, NOT a win probability.
    return 0.7 * metrics["pointDifferential"] + 0.3 * metrics["recentDifferential"]


def main():
    dataset = json.loads(SOURCE.read_text())
    games = sorted(dataset["games"], key=lambda g: (kickoff(g), g["id"]))
    teams = sorted({g[side] for g in games for side in ("home", "away")})
    graded = []
    skipped = 0
    for game in games:
        # Strictly earlier kickoff prevents same-time games from leaking.
        prior = [g for g in games if g.get("season", dataset["season"]) == game.get("season", dataset["season"]) and kickoff(g) < kickoff(game)]
        home = team_metrics(prior, game["home"])
        away = team_metrics(prior, game["away"])
        if home["games"] < 2 or away["games"] < 2 or game["winner"] == "TIE":
            skipped += 1
            continue
        home_edge = strength(home) - strength(away) + 1.5  # points, assumed HFA
        predicted = game["home"] if home_edge >= 0 else game["away"]
        graded.append({"season": game.get("season", dataset["season"]), "id": game["id"], "week": game["week"],
                       "predictedWinner": predicted, "actualWinner": game["winner"],
                       "correct": predicted == game["winner"],
                       "homeEdgePoints": round(home_edge, 2)})
    wins = sum(r["correct"] for r in graded)
    home_wins = sum(r["actualWinner"] == next(g["home"] for g in games if g["id"] == r["id"]) for r in graded)
    by_season = {}
    for season in sorted({r["season"] for r in graded}):
        rows = [r for r in graded if r["season"] == season]
        by_season[str(season)] = {"graded": len(rows), "modelCorrect": sum(r["correct"] for r in rows), "homeBaselineCorrect": sum(r["actualWinner"] == next(g["home"] for g in games if g["id"] == r["id"]) for r in rows)}
    latest = [g for g in games if g.get("season", dataset["season"]) == dataset["season"]]
    table = [{"team": team, **team_metrics(latest, team),
              "strengthScore": round(strength(team_metrics(latest, team)), 2)}
             for team in teams]
    output = {
        "season": dataset["season"],
        "source": "Completed NFL final scores only; no injuries, odds, or advanced statistics",
        "method": "70% season average point differential + 30% last-three differential; +1.5 home points",
        "caution": "Exploratory in-season walk-forward baseline, not out-of-sample validation; scores are not probabilities.",
        "gamesAvailable": len(games),
        "walkForward": {"graded": len(graded), "correct": wins,
                        "incorrect": len(graded) - wins, "skipped": skipped,
                        "accuracy": round(wins / len(graded), 4) if graded else None,
                        "homeBaselineCorrect": home_wins,
                        "homeBaselineAccuracy": round(home_wins / len(graded), 4) if graded else None,
                        "bySeason": by_season,
                        "predictions": graded},
        "teams": table,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Saved {len(table)} teams; walk-forward {wins}/{len(graded)} correct, {skipped} skipped")


if __name__ == "__main__":
    main()
