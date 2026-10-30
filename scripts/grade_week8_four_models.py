#!/usr/bin/env python3
"""Grade immutable Week 8 pregame picks independently of QB model validation."""
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/four-model-head-to-head/2026-week-8-refresh-20261029T083609Z.json"
DEST = ROOT / "data/four-model-head-to-head/2026-week-8-results-report.json"
MODELS = ("A", "B", "C", "C-QB")
URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=8"

def main():
    snapshot = json.loads(SOURCE.read_text())
    assert snapshot["season"] == 2026 and snapshot["week"] == 8
    assert len(snapshot["games"]) == 14
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "ForecastEdge-results/1.0"}), timeout=25) as response:
        scoreboard = json.load(response)
    events = {str(e["id"]): e for e in scoreboard.get("events", [])}
    results = []
    for game in snapshot["games"]:
        event = events.get(str(game["id"]))
        if not event:
            continue
        comp = event.get("competitions", [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed", False) and not event.get("status", {}).get("type", {}).get("completed", False):
            continue
        teams = {c["homeAway"]: c for c in comp.get("competitors", [])}
        if set(teams) != {"home", "away"}:
            continue
        home, away = teams["home"], teams["away"]
        if home["team"]["displayName"] != game["home"] or away["team"]["displayName"] != game["away"]:
            raise ValueError("Scoreboard team mismatch for game " + str(game["id"]))
        hs, aws = int(home["score"]), int(away["score"])
        winner = game["home"] if hs > aws else game["away"] if aws > hs else None
        model_results = {}
        for model in MODELS:
            pick = game["picks"][model]
            model_results[model] = {
                "pregameWinner": pick,
                "winnerCorrect": None if winner is None else pick == winner,
                "overUnder": "NOT_GRADED_MISSING_LOCKED_LINE",
                "totalPointsError": "NOT_GRADED_MISSING_LOCKED_PREDICTION",
            }
        results.append({
            "gameId": str(game["id"]), "date": game["date"],
            "away": game["away"], "home": game["home"],
            "awayScore": aws, "homeScore": hs, "winner": winner,
            "totalPoints": hs + aws, "models": model_results,
            "scoreSource": URL,
        })
    results.sort(key=lambda r: r["date"])
    summary = {}
    for model in MODELS:
        graded = [r["models"][model]["winnerCorrect"] for r in results if r["models"][model]["winnerCorrect"] is not None]
        wins = sum(graded)
        summary[model] = {"winnerWins": wins, "winnerLosses": len(graded) - wins,
                          "winnerAccuracy": round(wins / len(graded), 4) if graded else None,
                          "totalsGraded": 0}
    report = {
        "season": 2026, "week": 8, "reportType": "independent_four_model_results",
        "predictionSource": str(SOURCE.relative_to(ROOT)),
        "predictionFrozenAt": snapshot["frozenAt"],
        "status": "COMPLETE" if len(results) == len(snapshot["games"]) else "PARTIAL_RESULTS",
        "gamesCompleted": len(results), "gamesRemaining": len(snapshot["games"]) - len(results),
        "results": results, "summary": summary,
        "rules": [
            "Grade only immutable pre-kickoff winner picks from the specified snapshot",
            "Do not use revised post-kickoff predictions",
            "Missing pregame totals and betting lines remain ungraded, never losses",
            "QB source validation and model grading are separate",
            "Only completed ESPN scoreboard games are graded",
        ],
    }
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if not DEST.exists() or DEST.read_text() != output:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(output)
        print("Updated results:", len(results), "of", len(snapshot["games"]))
    else:
        print("No new results")

if __name__ == "__main__":
    main()
