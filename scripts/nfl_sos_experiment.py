#!/usr/bin/env python3
"""Exploratory walk-forward strength-of-schedule (SOS) experiment.
Only games earlier than each kickoff may influence a prediction.
Does not change production model or existing picks.
"""
import json
from pathlib import Path
from nfl_team_strength import kickoff, team_metrics, strength

source = json.loads(Path("data/nfl-historical-results.json").read_text())
games = sorted(source["games"], key=lambda g: (kickoff(g), g["id"]))
def sos(prior, team):
    opponents = []
    for g in prior:
        if g["home"] == team:
            opponents.append(g["away"])
        elif g["away"] == team:
            opponents.append(g["home"])
    if not opponents:
        return None
    # Average opponents' pregame-available season-to-date records, with repeats
    # reflecting schedule frequency. No current or future games are included.
    values = [team_metrics(prior, opponent)["winPct"] for opponent in opponents]
    return sum(v for v in values if v is not None) / len(values)

coefficients = (0.0, 2.0, 4.0, 8.0)
records = {str(k): [] for k in coefficients}
for game in games:
    season = game.get("season", source["season"])
    prior = [g for g in games if g.get("season", source["season"]) == season and kickoff(g) < kickoff(game)]
    home, away = team_metrics(prior, game["home"]), team_metrics(prior, game["away"])
    if min(home["games"], away["games"]) < 2 or game["winner"] == "TIE":
        continue
    home_sos, away_sos = sos(prior, game["home"]), sos(prior, game["away"])
    if home_sos is None or away_sos is None:
        continue
    baseline_edge = strength(home) - strength(away) + 1.5
    for k in coefficients:
        edge = baseline_edge + k * (home_sos - away_sos)
        predicted = game["home"] if edge >= 0 else game["away"]
        records[str(k)].append({"season": season, "week": game["week"],
                                "correct": predicted == game["winner"],
                                "pick": predicted})
baseline = records["0.0"]
n = len(baseline)
if n < 700:
    raise ValueError(f"Expected at least 700 eligible games, got {n}")
result = {
    "status": "Exploratory retrospective coefficient comparison; NOT independent validation",
    "method": "Strength of schedule is the average current season win percentage of prior opponents, evaluated using only games strictly before kickoff; no prior-season carryover.",
    "caution": "Opponent records are measured at prediction time, not when opponents originally played. Coefficients were compared on the same historical games; any winner requires an untouched holdout.",
    "eligibleGames": n, "coefficients": {},
    "productionModelChanged": False
}
for k in coefficients:
    rows = records[str(k)]
    correct = sum(x["correct"] for x in rows)
    baseline_correct = sum(x["correct"] for x in baseline)
    result["coefficients"][str(k)] = {
        "correct": correct, "accuracy": round(correct/n, 4),
        "netVsBaseline": correct - baseline_correct,
        "changedPicks": sum(x["pick"] != y["pick"] for x, y in zip(rows, baseline)),
        "bySeason": {str(s): {"games": sum(x["season"] == s for x in rows),
                             "correct": sum(x["season"] == s and x["correct"] for x in rows)}
                     for s in sorted(set(x["season"] for x in rows))}
    }
out = Path("data/nfl-sos-experiment.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"games": n, "coefficients": {k: {"accuracy": v["accuracy"], "netVsBaseline": v["netVsBaseline"]} for k,v in result["coefficients"].items()}}, indent=2))
