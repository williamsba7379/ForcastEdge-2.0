#!/usr/bin/env python3
"""Experimental early-season NFL winner picks. Does NOT modify the production model.
Uses only games before each kickoff. 2022 is excluded from development reporting
because the 2022 holdout has already been inspected.
"""
import json
import pathlib
import urllib.request
from datetime import datetime
from nfl_team_strength import team_metrics, strength

BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
def when(g):
    return datetime.fromisoformat(g["date"].replace("Z","+00:00"))
def season_games(year):
    result=[]
    for week in range(1,19):
        req=urllib.request.Request(f"{BASE}?dates={year}&seasontype=2&week={week}",headers={"User-Agent":"ForecastEdge-experiment/1.0"})
        with urllib.request.urlopen(req,timeout=30) as resp:
            data=json.load(resp)
        for event in data.get("events",[]):
            if not event.get("status",{}).get("type",{}).get("completed"): continue
            sides=event.get("competitions",[{}])[0].get("competitors",[])
            h=next((s for s in sides if s.get("homeAway")=="home"),None)
            a=next((s for s in sides if s.get("homeAway")=="away"),None)
            if not h or not a: continue
            try: hs,aws=int(h["score"]),int(a["score"])
            except (KeyError,ValueError,TypeError): continue
            result.append({"id":event["id"],"date":event["date"],"week":week,"home":h["team"]["displayName"],"away":a["team"]["displayName"],"homeScore":hs,"awayScore":aws,"winner":h["team"]["displayName"] if hs>aws else a["team"]["displayName"] if aws>hs else "TIE"})
    return sorted(result,key=lambda g:(when(g),g["id"]))

def score(prior,team):
    return strength(team_metrics(prior,team))
def run():
    # Prior season only: no knowledge of current-season future games.
    seasons={year:season_games(year) for year in (2022,2023,2024,2025)}
    results={}
    for year in (2023,2024,2025):
        current=seasons[year]
        previous=seasons[year-1]
        if len(current)<250 or len(previous)<250: raise ValueError("Incomplete ESPN season")
        rows=[]
        for g in current:
            if g["winner"]=="TIE":continue
            prior=[p for p in current if when(p)<when(g)]
            hm=team_metrics(prior,g["home"])
            am=team_metrics(prior,g["away"])
            if hm["games"]>=2 and am["games"]>=2:
                edge=score(prior,g["home"])-score(prior,g["away"])+1.5
                mode="existing"
            else:
                # Fixed exploratory choice; prior-year regular season strength
                # serves as an early-season prior, not a calibrated probability.
                edge=score(previous,g["home"])-score(previous,g["away"])+1.5
                mode="early_prior"
            pick=g["home"] if edge>=0 else g["away"]
            rows.append({"week":g["week"],"mode":mode,"correct":pick==g["winner"],"homeCorrect":g["home"]==g["winner"]})
        def stats(subset):
            n=len(subset)
            return {"games":n,"correct":sum(x["correct"] for x in subset),"accuracy":round(sum(x["correct"] for x in subset)/n,4) if n else None,"homeBaselineCorrect":sum(x["homeCorrect"] for x in subset),"homeBaselineAccuracy":round(sum(x["homeCorrect"] for x in subset)/n,4) if n else None}
        results[str(year)]={"allGames":stats(rows),"earlyPrior":stats([x for x in rows if x["mode"]=="early_prior"]),"existing":stats([x for x in rows if x["mode"]=="existing"])}
    out={"status":"Exploratory retrospective comparison; not a fresh independent holdout or future accuracy guarantee","developmentSeasons":[2023,2024,2025],"excludedFromDevelopment":"2022 previously inspected holdout","earlyMethod":"For teams with fewer than 2 earlier current-season games, compare previous regular-season point-differential strength; otherwise retain existing frozen method. Add 1.5 home points.","limitations":"Prior-season-only baseline ignores roster changes, injuries, betting markets and offseason moves; no calibrated probabilities.","results":results}
    dest=pathlib.Path("data/nfl-early-season-experiment.json")
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(results,indent=2))
if __name__=="__main__":run()
