#!/usr/bin/env python3
"""Experimental opponent-adjusted challenger; never overwrites baseline picks.

Evaluate 2023-26 only. 2022 holdout remains a previously inspected test
and is NOT reused to choose parameters. All features use earlier kickoffs.
"""
import json
from collections import defaultdict
from pathlib import Path
from nfl_team_strength import kickoff, team_metrics, strength

src=json.loads(Path("data/nfl-historical-results.json").read_text())
games=sorted(src["games"],key=lambda g:(kickoff(g),g["id"]))
baseline=json.loads(Path("data/nfl-team-strength.json").read_text())
base_by_id={(str(x["season"]),str(x["id"])):x for x in baseline["walkForward"]["predictions"]}
records=[]
for game in games:
    season=game.get("season",src["season"])
    prior=[g for g in games if g.get("season",src["season"])==season and kickoff(g)<kickoff(game)]
    hm=team_metrics(prior,game["home"])
    am=team_metrics(prior,game["away"])
    if min(hm["games"],am["games"])<2 or game["winner"]=="TIE":
        continue
    # Iterative SRS-style adjustment. Each game's margin is explained by
    # own rating minus opponent rating. Shrink to stabilize small samples.
    ratings=defaultdict(float)
    counts=defaultdict(int)
    for g in prior:
        counts[g["home"]]+=1
        counts[g["away"]]+=1
    for _ in range(6):
        totals=defaultdict(float)
        weights=defaultdict(float)
        for g in prior:
            margin=max(-28,min(28,g["homeScore"]-g["awayScore"]))
            # Slightly emphasize recent games, without using future results.
            age=(kickoff(game)-kickoff(g)).days
            w=1.0 if age<=28 else 0.7
            totals[g["home"]]+=w*(margin-1.5+ratings[g["away"]])
            totals[g["away"]]+=w*(-margin+1.5+ratings[g["home"]])
            weights[g["home"]]+=w
            weights[g["away"]]+=w
        ratings={team:totals[team]/(weights[team]+4.0) for team in counts}
    # Predefined blend: 65% adjusted rating + 35% original recent-form
    # rating. Challenger formula fixed before comparing results.
    adjusted=ratings.get(game["home"],0)-ratings.get(game["away"],0)
    raw=strength(hm)-strength(am)
    edge=0.65*adjusted+0.35*raw+1.5
    prediction=game["home"] if edge>=0 else game["away"]
    base=base_by_id.get((str(season),str(game["id"])))
    if base is None:
        raise ValueError(f"Baseline missing {season}/{game['id']}; cannot make matched comparison")
    records.append({"season":season,"week":game["week"],"id":game["id"],
                    "challengerWinner":prediction,"baselineWinner":base["predictedWinner"],
                    "actualWinner":game["winner"],
                    "challengerCorrect":prediction==game["winner"],
                    "baselineCorrect":base["predictedWinner"]==game["winner"],
                    "homeCorrect":game["home"]==game["winner"]})
if not records:
    raise ValueError("No eligible games")
def metrics(rows):
    n=len(rows)
    return {"graded":n,"challengerCorrect":sum(x["challengerCorrect"] for x in rows),
            "baselineCorrect":sum(x["baselineCorrect"] for x in rows),
            "homeCorrect":sum(x["homeCorrect"] for x in rows),
            "challengerAccuracy":round(sum(x["challengerCorrect"] for x in rows)/n,4),
            "baselineAccuracy":round(sum(x["baselineCorrect"] for x in rows)/n,4)}
output={"status":"EXPERIMENTAL: review only; not deployed for pool picks",
        "method":"Six iterative opponent adjustments on capped margins; 4-game shrinkage; 28-day recency weighting; 65% opponent-adjusted plus 35% frozen baseline, 1.5 home points",
        "validation":"Chronological 2023-2026 in-season retrospective, same games as baseline; 2022 previously viewed holdout deliberately excluded",
        "overall":metrics(records),
        "bySeason":{str(s):metrics([x for x in records if x["season"]==s]) for s in sorted({x["season"] for x in records})},
        "predictions":records}
p=Path("data/nfl-challenger-comparison.json")
p.write_text(json.dumps(output,indent=2)+"\n")
print(json.dumps(output["overall"],indent=2))
