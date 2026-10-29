#!/usr/bin/env python3
"""Grade frozen NFL four-model winner and totals research predictions separately."""
import json
from nfl_four_model_head_to_head import DATA,OUT,stamp
MODELS=("A","B","C","C-QB")

def grade(report,history):
    results={str(g["id"]):g for g in history.get("games",[])}
    summary={m:{"winnerWins":0,"winnerLosses":0,"totalsWins":0,"totalsLosses":0,
                "totalsPushes":0,"totalAbsoluteErrorSum":0.0,"totalErrorGames":0}
             for m in MODELS}
    for row in report["games"]:
        source=results.get(str(row["id"]))
        if not source or source.get("home")!=row["home"] or source.get("away")!=row["away"]:continue
        status=str(source.get("status","")).lower()
        final_flag=source.get("completed") is True or status in ("final","completed","post")
        verified_winner=source.get("winner") in (row["home"],row["away"])
        if not (final_flag or (not status and verified_winner)):continue
        try:
            home=float(source.get("scoreHome",source.get("homeScore")))
            away=float(source.get("scoreAway",source.get("awayScore")))
        except (TypeError,ValueError):continue
        if home<0 or away<0:continue
        total=home+away
        row["actualTotal"]=total
        row["actualWinner"]=row["home"] if home>away else row["away"] if away>home else None
        if verified_winner and source["winner"]!=row["actualWinner"]:continue
        for model in MODELS:
            winner_pick=row["models"][model].get("winnerPick")
            if row["actualWinner"] is not None and winner_pick in (row["home"],row["away"]):
                summary[model]["winnerWins" if winner_pick==row["actualWinner"] else "winnerLosses"]+=1
            pred=row["models"][model]
            projected=pred.get("projectedTotal")
            if projected is not None:
                error=round(abs(float(projected)-total),2)
                pred["totalAbsoluteError"]=error
                summary[model]["totalAbsoluteErrorSum"]+=error
                summary[model]["totalErrorGames"]+=1
            pick=pred.get("overUnderPick")
            line=pred.get("marketTotal")
            if pick not in ("OVER","UNDER") or type(line) not in (int,float):continue
            outcome="PUSH" if total==line else "OVER" if total>line else "UNDER"
            pred["actualOverUnder"]=outcome
            pred["totalCorrect"]=None if outcome=="PUSH" else pick==outcome
            key="totalsPushes" if outcome=="PUSH" else "totalsWins" if pick==outcome else "totalsLosses"
            summary[model][key]+=1
    for model,stats in summary.items():
        count=stats["totalsWins"]+stats["totalsLosses"]
        winner_count=stats["winnerWins"]+stats["winnerLosses"]
        stats["winnerAccuracyPct"]=round(100*stats["winnerWins"]/winner_count,2) if winner_count else None
        stats["totalsAccuracyPct"]=round(100*stats["totalsWins"]/count,2) if count else None
        stats["meanAbsoluteTotalError"]=round(stats["totalAbsoluteErrorSum"]/stats["totalErrorGames"],2) if stats["totalErrorGames"] else None
        del stats["totalAbsoluteErrorSum"]
    report["gradingSummary"]=summary
    report["gradingStatus"]="PARTIALLY_GRADED" if any(s["totalErrorGames"] for s in summary.values()) else "PENDING_RESULTS"
    return report

def main():
    files=sorted(OUT.glob("*-totals-market-comparison.json"))
    if not files:raise ValueError("No frozen totals market comparison available")
    path=files[-1]
    report=json.loads(path.read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    graded=grade(report,history)
    out=OUT/(str(report["season"])+"-week-"+str(report["week"])+"-totals-graded.json")
    out.write_text(json.dumps(graded,indent=2)+"\n")
    print(out,graded["gradingStatus"])
if __name__=="__main__":main()
