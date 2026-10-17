#!/usr/bin/env python3
"""One-time chronological 2022 holdout check of the FROZEN ForecastEdge baseline.
Do not tune the formula after seeing holdout outcomes and call it independent.
"""
import datetime
import json
import pathlib
import urllib.request
from nfl_team_strength import kickoff, team_metrics, strength

SEASON = 2022
BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
games = []
for week in range(1, 19):
    req = urllib.request.Request(
        f"{BASE}?dates={SEASON}&seasontype=2&week={week}",
        headers={"User-Agent": "ForecastEdge/2.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        board = json.load(response)
    for event in board.get("events", []):
        if event.get("status", {}).get("type", {}).get("completed") is not True:
            continue
        sides = event.get("competitions", [{}])[0].get("competitors", [])
        home = next((x for x in sides if x.get("homeAway") == "home"), None)
        away = next((x for x in sides if x.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        try:
            hs, aws = int(home["score"]), int(away["score"])
        except (KeyError, ValueError, TypeError):
            continue
        games.append({
            "id": event["id"], "week": week, "date": event["date"],
            "home": home["team"]["displayName"],
            "away": away["team"]["displayName"],
            "homeScore": hs, "awayScore": aws,
            "winner": home["team"]["displayName"] if hs > aws else
                      away["team"]["displayName"] if aws > hs else "TIE",
        })
games.sort(key=lambda g: (kickoff(g), g["id"]))
if len(games) < 250:
    raise ValueError(f"Only {len(games)} 2022 games returned; refusing incomplete evaluation")

graded = []
skipped = 0
for game in games:
    prior = [g for g in games if kickoff(g) < kickoff(game)]
    home = team_metrics(prior, game["home"])
    away = team_metrics(prior, game["away"])
    if home["games"] < 2 or away["games"] < 2 or game["winner"] == "TIE":
        skipped += 1
        continue
    edge = strength(home) - strength(away) + 1.5
    predicted = game["home"] if edge >= 0 else game["away"]
    graded.append({
        "week": game["week"], "id": game["id"],
        "predictedWinner": predicted, "actualWinner": game["winner"],
        "modelCorrect": predicted == game["winner"],
        "homeBaselineCorrect": game["home"] == game["winner"],
    })
n = len(graded)
if not n:
    raise ValueError("No eligible holdout games")
correct = sum(g["modelCorrect"] for g in graded)
home_correct = sum(g["homeBaselineCorrect"] for g in graded)
by_week = []
for week in range(1, 19):
    rows = [g for g in graded if g["week"] == week]
    by_week.append({
        "week": week, "graded": len(rows),
        "modelCorrect": sum(g["modelCorrect"] for g in rows),
        "homeBaselineCorrect": sum(g["homeBaselineCorrect"] for g in rows),
    })
out = {
    "holdoutSeason": SEASON,
    "status": "Single historical holdout evaluation of frozen formula; not a live prospective test",
    "method": "70% season average point differential + 30% last-three differential; +1.5 home points; at least 2 prior games per team",
    "leakageControl": "For each kickoff, use only completed games with earlier kickoff times from the same season",
    "note": "This 2022 season was not used in the previously reported 2023-2026 analysis. Results must not be used to tune and then re-label this same holdout as independent.",
    "gamesAvailable": len(games), "graded": n, "skipped": skipped,
    "modelCorrect": correct, "modelAccuracy": round(correct / n, 4),
    "homeBaselineCorrect": home_correct,
    "homeBaselineAccuracy": round(home_correct / n, 4),
    "differencePercentagePoints": round(100 * (correct - home_correct) / n, 2),
    "byWeek": by_week, "predictions": graded,
    "evaluatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
dest = pathlib.Path("data/nfl-holdout-2022.json")
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(out, indent=2) + "\n")
print(f"2022 holdout: {correct}/{n} ({correct/n:.1%}); home {home_correct}/{n} ({home_correct/n:.1%}); skipped {skipped}")
