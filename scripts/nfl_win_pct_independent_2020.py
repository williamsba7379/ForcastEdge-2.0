#!/usr/bin/env python3
"""Pre-specified win-percentage factor evaluation on untouched 2020 NFL season.
The +4.0 coefficient was chosen using 2023-26 data. Do not tune on this test.
"""
import datetime
import json
import pathlib
import urllib.request
from nfl_team_strength import kickoff, team_metrics, strength

YEAR = 2020
BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
games = []
for week in range(1, 18):
    req = urllib.request.Request(f"{BASE}?dates={YEAR}&seasontype=2&week={week}",
                                 headers={"User-Agent": "ForecastEdge/2.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        board = json.load(response)
    for event in board.get("events", []):
        if not event.get("status", {}).get("type", {}).get("completed"):
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
        games.append({"id": event["id"], "week": week, "date": event["date"],
                      "home": home["team"]["displayName"],
                      "away": away["team"]["displayName"],
                      "homeScore": hs, "awayScore": aws,
                      "winner": home["team"]["displayName"] if hs > aws else
                                away["team"]["displayName"] if aws > hs else "TIE"})
games.sort(key=lambda g: (kickoff(g), g["id"]))
if len(games) < 250:
    raise ValueError(f"Incomplete 2020 season: only {len(games)} games")
rows = []
for game in games:
    prior = [g for g in games if kickoff(g) < kickoff(game)]
    h = team_metrics(prior, game["home"])
    a = team_metrics(prior, game["away"])
    if min(h["games"], a["games"]) < 2 or game["winner"] == "TIE":
        continue
    edge = strength(h) - strength(a) + 1.5
    candidate_edge = edge + 4.0 * (h["winPct"] - a["winPct"])
    baseline = game["home"] if edge >= 0 else game["away"]
    candidate = game["home"] if candidate_edge >= 0 else game["away"]
    rows.append({"id": game["id"], "week": game["week"],
                 "baselineCorrect": baseline == game["winner"],
                 "candidateCorrect": candidate == game["winner"],
                 "changedPick": baseline != candidate})
n = len(rows)
if n < 200:
    raise ValueError(f"Insufficient eligible games: {n}")
b = sum(x["baselineCorrect"] for x in rows)
c = sum(x["candidateCorrect"] for x in rows)
output = {
    "status": "One-time pre-specified historical holdout; not prospective validation",
    "holdoutSeason": YEAR, "eligibleGames": n, "gamesAvailable": len(games),
    "baselineCorrect": b, "baselineAccuracy": round(b/n, 4),
    "candidateCorrect": c, "candidateAccuracy": round(c/n, 4),
    "netAdditionalCorrect": c-b, "changedPicks": sum(x["changedPick"] for x in rows),
    "differencePercentagePoints": round(100*(c-b)/n, 2),
    "formula": "baseline: 0.7 season differential + 0.3 recent differential + 1.5 home; candidate adds 4.0*(home winPct - away winPct)",
    "limitation": "2020 was selected after examining 2023-2026 exploratory data; coefficient fixed before 2020 test. Results do not establish statistical significance or betting profitability.",
    "byWeek": [{"week": w, "games": sum(x["week"] == w for x in rows),
                "baselineCorrect": sum(x["week"] == w and x["baselineCorrect"] for x in rows),
                "candidateCorrect": sum(x["week"] == w and x["candidateCorrect"] for x in rows)}
               for w in range(1,18)],
    "evaluatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
dest = pathlib.Path("data/nfl-win-pct-independent-2020.json")
dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(output, indent=2)+"\n")
print(f"2020 independent test: baseline {b}/{n} ({b/n:.2%}), candidate {c}/{n} ({c/n:.2%}); net {c-b}; changed {output['changedPicks']}")
