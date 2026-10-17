#!/usr/bin/env python3
"""Research-only: test whether win percentage adds value to point-differential strength.
Uses same eligible games for all variants, strictly prior kickoffs, no production changes.
Exploratory retrospective comparisons only; results are not a fresh holdout.
"""
import json
from pathlib import Path
from nfl_team_strength import kickoff, team_metrics, strength

data=json.loads(Path("data/nfl-historical-results.json").read_text())
games=sorted(data["games"],key=lambda g:(kickoff(g),g["id"]))
rows=[]
for g in games:
    if g["winner"]=="TIE": continue
    season=g["season"]
    prior=[p for p in games if p["season"]==season and kickoff(p)<kickoff(g)]
    h=team_metrics(prior,g["home"])
    a=team_metrics(prior,g["away"])
    if min(h["games"],a["games"])<2:continue
    # Fixed candidate factor: 4 points per full win-percentage difference.
    # 4 is an experimental coefficient, not fitted or proven.
    base=strength(h)-strength(a)+1.5
    added=base+4.0*(h["winPct"]-a["winPct"])
    rows.append({"season":season,"week":g["week"],"baselineCorrect":(g["home"] if base>=0 else g["away"])==g["winner"],
                 "candidateCorrect":(g["home"] if added>=0 else g["away"])==g["winner"],
                 "differentPick":(base>=0)!=(added>=0)})
def stats(items):
    n=len(items)
    b=sum(x["baselineCorrect"] for x in items)
    c=sum(x["candidateCorrect"] for x in items)
    return {"games":n,"baselineCorrect":b,"baselineAccuracy":round(b/n,4) if n else None,
            "candidateCorrect":c,"candidateAccuracy":round(c/n,4) if n else None,
            "changedPicks":sum(x["differentPick"] for x in items),"netAdditionalCorrect":c-b}
out={"status":"Exploratory retrospective feature comparison; NOT a new independent test",
     "feature":"Add 4.0 * (home winPct - away winPct) to existing 70/30 point differential edge plus 1.5 home advantage",
     "limitations":["All candidates are evaluated on the same eligible games, using only earlier games in the same season.",
                    "Coefficient 4.0 is a research choice, not optimized; testing it here uses previously inspected historical seasons.",
                    "No market odds, injuries, schedules, or calibrated probabilities are included.",
                    "No production or weekly pool picks are modified."],
     "overall":stats(rows),
     "bySeason":{str(y):stats([r for r in rows if r["season"]==y]) for y in sorted(set(r["season"] for r in rows))},
     "earlyWeeks":stats([r for r in rows if r["week"]<=4]),
     "laterWeeks":stats([r for r in rows if r["week"]>4])}
Path("data/nfl-win-pct-factor-experiment.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
