#!/usr/bin/env python3
"""Experimental projected scores for A/B/C/C-QB; no invented sportsbook lines.
Uses only completed same-season games before the snapshot, never post-kickoff.
This is a research-only companion to the immutable winner cards.
"""
import datetime as dt
import json
from pathlib import Path
from nfl_four_model_head_to_head import DATA, OUT, stamp

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def projection(history, team, before, recent_weight):
    games=[g for g in history if int(g.get("season",-1))==before["season"] and
           stamp(g["date"])<before["time"] and team in (g["home"],g["away"])]
    games.sort(key=lambda g:g["date"])
    if len(games)<3:return None
    scored=[float(g["homeScore"] if g["home"]==team else g["awayScore"]) for g in games]
    allowed=[float(g["awayScore"] if g["home"]==team else g["homeScore"]) for g in games]
    return tuple((1-recent_weight)*mean(vals)+recent_weight*mean(vals[-3:]) for vals in (scored,allowed))

def build(card,history):
    now=stamp(card["frozenAt"])
    out=[]
    for game in card["games"]:
        when={"season":card["season"],"time":now}
        if now>=stamp(game["date"]):raise ValueError("Not pregame: "+game["id"])
        models={}
        for model,weight in (("A",.3),("B",0),("C",.3),("C-QB",.3)):
            away=projection(history,game["away"],when,weight)
            home=projection(history,game["home"],when,weight)
            if away is None or home is None:
                models[model]={"status":"INSUFFICIENT_HISTORY","projectedTotal":None,
                               "overUnderPick":None,"spreadPick":None}
                continue
            homepts=(home[0]+away[1])/2+0.75
            awaypts=(away[0]+home[1])/2-0.75
            if model in ("C","C-QB"):
                # Preserve the corresponding model's independently computed home-edge
                # while using a historical offense/defense total estimate.
                draft_edge=game.get("modelCHomeEdgePoints")
                if model=="C-QB" and draft_edge is not None:
                    draft_edge+=game.get("qbHomeEdgeAdjustment",0)
                if draft_edge is not None:
                    total=homepts+awaypts
                    homepts=(total+draft_edge)/2
                    awaypts=(total-draft_edge)/2
            models[model]={"status":"EXPERIMENTAL_UNCALIBRATED","projectedHome":round(max(0,homepts),1),
                "projectedAway":round(max(0,awaypts),1),"projectedTotal":round(max(0,homepts)+max(0,awaypts),1),
                "overUnderPick":None,"spreadPick":None,
                "note":"Market total/spread not supplied: no over/under or ATS selection."}
        out.append({"id":game["id"],"home":game["home"],"away":game["away"],"models":models})
    return {"season":card["season"],"week":card["week"],"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceComparisonFrozenAt":card["frozenAt"],"status":"RESEARCH_ONLY_NO_MARKET_LINES",
        "warning":"Experimental point projections, NOT validated or independent C/C-QB total models. No sportsbook lines, no O/U or ATS picks.",
        "games":out}

def main():
    files=sorted(OUT.glob("*-refresh-*.json"))
    if not files:raise ValueError("No refreshed comparison")
    card=json.loads(files[-1].read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())["games"]
    result=build(card,history)
    path=OUT/(str(card["season"])+"-week-"+str(card["week"])+"-totals-research.json")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(path,len(result["games"]),"games")
if __name__=="__main__":main()
