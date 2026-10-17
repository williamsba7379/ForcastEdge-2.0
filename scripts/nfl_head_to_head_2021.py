#!/usr/bin/env python3
"""Audit 2.0 versus 2.1 on identical 2021 games without modifying production.
2.0 abstains until both teams have two prior same-season games.
2.1 uses the frozen previous-season fallback only for those early games.
This is a retrospective diagnostic on an already inspected season, NOT a new holdout.
"""
import json
from pathlib import Path
from nfl_early_season_experiment import season_games, when, score
from nfl_team_strength import team_metrics

previous=season_games(2020)
current=season_games(2021)
if len(previous)<250 or len(current)<250:
    raise RuntimeError("Incomplete data; cannot compare")
rows=[]
for g in current:
    if g["winner"]=="TIE": continue
    prior=[p for p in current if when(p)<when(g)]
    home=team_metrics(prior,g["home"])
    away=team_metrics(prior,g["away"])
    eligible=home["games"]>=2 and away["games"]>=2
    def predict(source):
        return g["home"] if score(source,g["home"])-score(source,g["away"])+1.5>=0 else g["away"]
    original=predict(prior) if eligible else None
    revised=original if eligible else predict(previous)
    rows.append({"id":g["id"],"week":g["week"],"actual":g["winner"],
                 "originalPick":original,"revisedPick":revised,
                 "originalCorrect":original==g["winner"] if eligible else None,
                 "revisedCorrect":revised==g["winner"],"earlyFallback":not eligible})
def stats(items):
    n=len(items)
    return {"games":n,"originalGraded":sum(x["originalPick"] is not None for x in items),
            "originalCorrect":sum(x["originalCorrect"] is True for x in items),
            "originalAccuracyOnEligible":round(sum(x["originalCorrect"] is True for x in items)/sum(x["originalPick"] is not None for x in items),4) if any(x["originalPick"] is not None for x in items) else None,
            "revisedCorrect":sum(x["revisedCorrect"] for x in items),
            "revisedAccuracy":round(sum(x["revisedCorrect"] for x in items)/n,4) if n else None}
early=[x for x in rows if x["earlyFallback"]]
common=[x for x in rows if not x["earlyFallback"]]
out={"status":"Retrospective head-to-head audit on previously inspected 2021 results, not independent validation",
     "comparison":"2.0 abstains on games with fewer than two prior games for either team; 2.1 supplies previous-season fallback. Both methods use the same prediction on shared eligible games.",
     "all":stats(rows),"commonGames":stats(common),"earlyCoverage":stats(early),
     "identicalOnCommonGames":all(x["originalPick"]==x["revisedPick"] for x in common),
     "notes":["Different coverage makes all-games accuracy versus eligible-games accuracy not directly comparable.",
              "2021 results have already been viewed; do not call this a fresh holdout.",
              "Neither model is a calibrated probability model."],
     "games":rows}
path=Path("data/nfl-head-to-head-2021.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps({k:v for k,v in out.items() if k!="games"},indent=2))
