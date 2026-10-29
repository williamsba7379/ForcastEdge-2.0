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

def recent_team_games(history, team, season, before):
    games=[g for g in history if int(g.get("season",-1))==season and
           stamp(g["date"])<before and team in (g["home"],g["away"])]
    return sorted(games,key=lambda g:g["date"])[-3:]

def tempo_adjustment(history, home, away, season, before):
    """C research: recent combined scoring environment relative to season baseline.
    Independent of the A/B offense-defense total formula; bounded to avoid overfit.
    """
    adjustments=[]
    for team in (home,away):
        recent=recent_team_games(history,team,season,before)
        season_games=[g for g in history if int(g.get("season",-1))==season and
                      stamp(g["date"])<before and team in (g["home"],g["away"])]
        if len(recent)<3 or len(season_games)<3:return None
        game_total=lambda g:float(g["homeScore"])+float(g["awayScore"])
        adjustments.append(mean([game_total(g) for g in recent])-mean([game_total(g) for g in season_games]))
    return max(-4.0,min(4.0,0.25*mean(adjustments)))

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
                tempo=tempo_adjustment(history,game["home"],game["away"],card["season"],now)
                if tempo is None:
                    models[model]={"status":"INSUFFICIENT_HISTORY","projectedTotal":None,
                                   "overUnderPick":None,"spreadPick":None}
                    continue
                # C changes the combined total using recent game scoring environment.
                homepts+=tempo/2
                awaypts+=tempo/2
                # C-QB changes the combined total only with reviewed QB-specific
                # scoring impact; a home-edge change alone affects margin, not total.
                if model=="C-QB":
                    qb_total=game.get("verifiedQbTotalAdjustment")
                    if type(qb_total) in (int,float):
                        qb_total=max(-6.0,min(6.0,float(qb_total)))
                        homepts+=qb_total/2
                        awaypts+=qb_total/2

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
                "totalMethod":{"A":"RECENCY_WEIGHTED_OFFENSE_DEFENSE","B":"SEASON_OFFENSE_DEFENSE",
                               "C":"RECENCY_PLUS_SCORING_ENVIRONMENT",
                               "C-QB":"SCORING_ENVIRONMENT_PLUS_VERIFIED_QB_TOTAL_ONLY"}[model],
                "note":"Experimental, uncalibrated. C-QB total equals C without verified QB total impact; no sportsbook pick without sourced market line."}
        for model in models:
            models[model]["winnerPick"]=game["picks"][model]
        out.append({"id":game["id"],"date":game["date"],"home":game["home"],"away":game["away"],"models":models})
    return {"season":card["season"],"week":card["week"],"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceComparisonFrozenAt":card["frozenAt"],"status":"RESEARCH_ONLY_NO_MARKET_LINES",
        "warning":"Experimental uncalibrated totals: C uses recent scoring environment; C-QB differs only with verified QB-specific total impact. No sportsbook lines, no O/U or ATS picks.",
        "games":out}

def main():
    files=sorted(OUT.glob("*-refresh-*.json"))
    if not files:raise ValueError("No refreshed comparison")
    card=json.loads(files[-1].read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())["games"]
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    edges={str(g["id"]):g["homeEdgePoints"] for g in draft["games"]}
    for game in card["games"]:
        game["modelCHomeEdgePoints"]=edges.get(str(game["id"]))
    result=build(card,history)
    path=OUT/(str(card["season"])+"-week-"+str(card["week"])+"-totals-research.json")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(path,len(result["games"]),"games")
if __name__=="__main__":main()
