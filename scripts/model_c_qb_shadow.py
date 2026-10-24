#!/usr/bin/env python3
"""Experimental Model C-QB shadow predictions; never changes Model C picks.
Only reviewed game-specific confirmed starters and dated pre-kickoff QB history.
Point conversion is a conservative uncalibrated hypothesis, NOT betting advice.
"""
import datetime as dt
import json
import pathlib
from model_c_engine import official_starter_valid

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
MIN_ATTEMPTS=80
POINTS_PER_AYA=0.35
MAX_ABS_POINTS=3.0

def timestamp(value):
    try:
        t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        return t if t.tzinfo else None
    except (TypeError,ValueError,AttributeError):
        return None

def pregame_aya(records,team,player,kickoff):
    eligible=[]
    for row in records:
        date=timestamp(row.get("gameDate"))
        if row.get("team")!=team or date is None or date>=kickoff:continue
        for p in row.get("passers",[]):
            if p.get("player","").casefold()!=player.casefold():continue
            if not all(type(p.get(k))==int and p[k]>=0 for k in ("attempts","passYards","passTD","interceptions")):continue
            eligible.append(p)
    attempts=sum(p["attempts"] for p in eligible)
    if attempts<MIN_ATTEMPTS:return None
    return {"aya":(sum(p["passYards"]+20*p["passTD"]-45*p["interceptions"] for p in eligible)/attempts),
            "attempts":attempts,"games":len(eligible)}

def adjustment(game,side,declarations,history,asof):
    team=game[side]
    kickoff=timestamp(game["date"])
    dec=declarations.get(team,{})
    if kickoff is None or asof>=kickoff or not official_starter_valid(dec,game,team,asof):
        return {"status":"NO_ADJUSTMENT","reason":"No reviewed, game-specific confirmed starter available before kickoff","points":0.0}
    replacement=dec["starter"]
    baseline=dec.get("baselineStarter")
    if not isinstance(baseline,str) or not baseline.strip() or baseline.casefold()==replacement.casefold():
        return {"status":"NO_ADJUSTMENT","reason":"No separately documented different baseline starter","points":0.0}
    if not dec.get("baselineSource","").startswith("https://") or not dec.get("baselineReviewed"):
        return {"status":"NO_ADJUSTMENT","reason":"Baseline QB identity not independently reviewed and sourced","points":0.0}
    baseline_asof=timestamp(dec.get("baselineAsOf"))
    if baseline_asof is None or baseline_asof>asof or baseline_asof>=kickoff:
        return {"status":"NO_ADJUSTMENT","reason":"Baseline QB evidence unavailable pregame","points":0.0}
    old=pregame_aya(history,team,baseline,kickoff)
    new=pregame_aya(history,team,replacement,kickoff)
    if not old or not new:
        return {"status":"NO_ADJUSTMENT","reason":"Fewer than 80 pregame passing attempts for one or both QBs","points":0.0}
    points=round(max(-MAX_ABS_POINTS,min(MAX_ABS_POINTS,POINTS_PER_AYA*(new["aya"]-old["aya"]))),2)
    return {"status":"EXPERIMENTAL_APPLIED","points":points,"baselineStarter":baseline,
            "confirmedStarter":replacement,"baselineAYA":round(old["aya"],2),
            "replacementAYA":round(new["aya"],2),"sampleAttempts":{"baseline":old["attempts"],"replacement":new["attempts"]},
            "sources":{"confirmed":dec["source"],"baseline":dec["baselineSource"]},
            "warning":"Uncalibrated AYA-to-points conversion; ignores rushing, sacks and opponent strength."}

def build(draft,history,declarations,now):
    games=[]
    for g in draft["games"]:
        sides={side:adjustment(g,side,declarations,history,now) for side in ("home","away")}
        delta=round(sides["home"]["points"]-sides["away"]["points"],2)
        edge=round(g["homeEdgePoints"]+delta,2)
        games.append({"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
                      "originalPick":g["pick"],"originalHomeEdgePoints":g["homeEdgePoints"],
                      "qbHomeEdgeAdjustment":delta,"experimentalHomeEdgePoints":edge,
                      "experimentalPick":g["home"] if edge>=0 else g["away"],
                      "qbAdjustments":sides,"rating":"NO BET","confidence":"UNVALIDATED"})
    return {"title":"Model C-QB — Experimental Shadow Test","season":draft["season"],"week":draft["week"],
            "generatedAt":now.isoformat(),"status":"EXPERIMENTAL_SHADOW_ONLY",
            "method":"Pre-kickoff game-level AYA differential * 0.35, capped at +/-3 points per team; not calibrated.",
            "eligibleAdjustments":sum(s["status"]=="EXPERIMENTAL_APPLIED" for g in games for s in g["qbAdjustments"].values()),
            "warning":"No retrospective grading against information published after kickoff. Original Model C predictions remain unchanged.",
            "games":games}

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    qb=json.loads((DATA/"model-c-historical-qb-games.json").read_text())
    declarations=json.loads((DATA/"model-c-qb-starters.json").read_text()).get("teams",{})
    now=dt.datetime.now(dt.timezone.utc)
    out=build(draft,qb["records"],declarations,now)
    (DATA/"model-c-qb-shadow.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Model C-QB shadow:",len(out["games"]),"games;",out["eligibleAdjustments"],"eligible team adjustments")

if __name__=="__main__":main()
