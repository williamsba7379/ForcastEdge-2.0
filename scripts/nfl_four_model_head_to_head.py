#!/usr/bin/env python3
"""Freeze and grade A/B/C/C-QB on identical games. Never revise frozen picks."""
import datetime as dt
import json
import pathlib
from model_c_engine import extract_history,team_form

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
OUT=DATA/"four-model-head-to-head"
OUT.mkdir(parents=True,exist_ok=True)

def stamp(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))

def freeze(draft,shadow,history,now):
    if (draft["season"],draft["week"])!=(shadow["season"],shadow["week"]):
        raise ValueError("Week mismatch")
    if shadow.get("status")!="EXPERIMENTAL_SHADOW_ONLY":raise ValueError("Shadow not experimental")
    if stamp(draft["generatedAt"])>now or stamp(shadow["generatedAt"])>now:
        raise ValueError("Draft timestamps in future")
    original={str(g["id"]):g for g in draft["games"]}
    adjusted={str(g["id"]):g for g in shadow["games"]}
    if len(original)!=len(adjusted) or original.keys()!=adjusted.keys():
        raise ValueError("Models must cover identical games")
    rows=[]
    for key,g in original.items():
        s=adjusted[key]
        kickoff=stamp(g["date"])
        if not (now<kickoff and stamp(draft["generatedAt"])<kickoff and stamp(shadow["generatedAt"])<kickoff):
            raise ValueError("All four predictions must exist before kickoff: "+key)
        if s["originalPick"]!=g["pick"] or s["originalHomeEdgePoints"]!=g["homeEdgePoints"]:
            raise ValueError("Model C baseline differs: "+key)
        if any(a.get("status")=="EXPERIMENTAL_APPLIED" and not a.get("sources") for a in s["qbAdjustments"].values()):
            raise ValueError("Unsourced QB adjustment")
        older=extract_history(history,min(now,kickoff),draft["season"])
        def diffs(team):
            values=[(h-a if home==team else a-h) for _,away,home,a,h in older if team in (away,home)]
            return values
        h=diffs(g["home"]);a=diffs(g["away"])
        def pick(recent_weight):
            if min(len(h),len(a))<2:return g["home"]
            hs=(1-recent_weight)*sum(h)/len(h)+recent_weight*sum(h[-3:])/min(3,len(h))
            aw=(1-recent_weight)*sum(a)/len(a)+recent_weight*sum(a[-3:])/min(3,len(a))
            return g["home"] if hs-aw+1.5>=0 else g["away"]
        picks={"A":pick(.3),"B":pick(0),"C":g["pick"],"C-QB":s["experimentalPick"]}
        if any(p not in (g["home"],g["away"]) for p in picks.values()):raise ValueError("Invalid pick")
        rows.append({"id":key,"date":g["date"],"home":g["home"],"away":g["away"],
                     "picks":picks,"qbHomeEdgeAdjustment":s["qbHomeEdgeAdjustment"],
                     "qbAdjustments":s["qbAdjustments"],"winner":None,"correct":None})
    return {"season":draft["season"],"week":draft["week"],"status":"FROZEN_PREKICKOFF",
            "frozenAt":now.isoformat(),"modelCGeneratedAt":draft["generatedAt"],
            "modelCQBGeneratedAt":shadow["generatedAt"],
            "models":{"A":"30% recent differential","B":"0% recent differential",
                      "C":"existing Model C automated review draft","C-QB":"experimental QB shadow"},
            "warning":"Winner-only experimental head-to-head; C/C-QB review-only, no calibrated bets.",
            "games":rows}

def grade(frozen,history):
    lookup={str(g.get("id")):g for g in (history.get("games",[]) if isinstance(history,dict) else history)}
    for row in frozen["games"]:
        if row["winner"] is not None:continue
        game=lookup.get(row["id"])
        if not game:continue
        # Historical results may omit status but include a verified final winner.
        status = str(game.get("status", "")).strip().upper()
        final_flag = game.get("isFinal") is True or status in ("FINAL", "STATUS_FINAL", "COMPLETED")
        verified_winner = game.get("winner") in (row["home"], row["away"])
        if not (final_flag or (not status and verified_winner)):
            continue
        try:
            home=float(game.get("scoreHome",game.get("homeScore")))
            away=float(game.get("scoreAway",game.get("awayScore")))
        except (TypeError,ValueError):continue
        if home==away:continue
        winner=row["home"] if home>away else row["away"]
        if verified_winner and game["winner"] != winner:continue
        if game.get("home")!=row["home"] or game.get("away")!=row["away"]:continue
        row["winner"]=winner
        row["correct"]={m:(p==winner) for m,p in row["picks"].items()}
    summary={}
    for m in ("A","B","C","C-QB"):
        results=[r["correct"][m] for r in frozen["games"] if r["correct"] is not None]
        wins=sum(results)
        summary[m]={"wins":wins,"losses":len(results)-wins,"pending":len(frozen["games"])-len(results),
                    "accuracyPct":round(100*wins/len(results),2) if results else None}
    frozen["summary"]=summary
    frozen["status"]="GRADED" if all(r["winner"] for r in frozen["games"]) else "PARTIALLY_GRADED" if any(r["winner"] for r in frozen["games"]) else "FROZEN_PREKICKOFF"
    return frozen

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    shadow=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    path=OUT/(str(draft["season"])+"-week-"+str(draft["week"])+".json")
    now=dt.datetime.now(dt.timezone.utc)
    if path.exists():
        frozen=json.loads(path.read_text())
        # Only results are updated, never picks or original frozen timestamps.
        frozen=grade(frozen,history)
    else:
        frozen=freeze(draft,shadow,history,now)
        frozen=grade(frozen,history)
    path.write_text(json.dumps(frozen,indent=2)+"\n")
    print("Four-model comparison",path,frozen["status"],frozen["summary"])

if __name__=="__main__":main()
