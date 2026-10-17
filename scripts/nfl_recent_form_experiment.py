#!/usr/bin/env python3
"""Exploratory walk-forward test of last-three-game form weights.
No future games or cross-season information; production model unchanged.
"""
import json
from pathlib import Path
from nfl_team_strength import kickoff, team_metrics

source=json.loads(Path("data/nfl-historical-results.json").read_text())
games=sorted(source["games"],key=lambda g:(kickoff(g),g["id"]))
weights=(0.0,0.3,0.5,0.7,1.0)
records={str(w):[] for w in weights}
for game in games:
    season=game.get("season",source["season"])
    prior=[g for g in games if g.get("season",source["season"])==season and kickoff(g)<kickoff(game)]
    home=team_metrics(prior,game["home"])
    away=team_metrics(prior,game["away"])
    if min(home["games"],away["games"])<2 or game["winner"]=="TIE":
        continue
    for w in weights:
        hs=(1-w)*home["pointDifferential"]+w*home["recentDifferential"]
        aw=(1-w)*away["pointDifferential"]+w*away["recentDifferential"]
        pick=game["home"] if hs-aw+1.5>=0 else game["away"]
        records[str(w)].append({"season":season,"pick":pick,"correct":pick==game["winner"]})
n=len(records["0.3"])
if n<700:raise ValueError(f"Expected at least 700 games; got {n}")
base=records["0.3"]
result={
 "status":"Exploratory retrospective comparison; NOT independent validation",
 "method":"Walk-forward: full-season average point differential blended with most recent three games, using only completed games before kickoff; 1.5-point home advantage.",
 "baselineWeight":0.3,
 "eligibleGames":n,
 "weights":{},
 "caution":"The baseline already uses 30% last-three-game form. Selecting a weight on these same games risks overfitting; validate any candidate on untouched seasons.",
 "productionModelChanged":False
}
for w in weights:
    rows=records[str(w)]
    correct=sum(x["correct"] for x in rows)
    result["weights"][str(w)]={
      "correct":correct,"accuracy":round(correct/n,4),
      "netVsBaseline":correct-sum(x["correct"] for x in base),
      "changedPicks":sum(a["pick"]!=b["pick"] for a,b in zip(rows,base)),
      "bySeason":{str(s):{"games":sum(x["season"]==s for x in rows),"correct":sum(x["season"]==s and x["correct"] for x in rows)} for s in sorted({x["season"] for x in rows})}
    }
out=Path("data/nfl-recent-form-experiment.json")
out.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"games":n,"weights":{k:{"accuracy":v["accuracy"],"netVsBaseline":v["netVsBaseline"]} for k,v in result["weights"].items()}},indent=2))
