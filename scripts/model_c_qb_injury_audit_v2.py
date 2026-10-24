#!/usr/bin/env python3
"""Independent QB absence triage. Historical primary passers are NOT verified starters."""
import json
from pathlib import Path
from datetime import datetime,timezone
DATA=Path(__file__).resolve().parents[1]/"data"
OUT={"out","ir","injured reserve","suspended","pup","physically unable to perform"}
def build(draft,shadow,history):
    byid={str(g["id"]):g for g in shadow["games"]}
    alerts=[]
    for game in draft["games"]:
        sid=str(game["id"])
        if sid not in byid: raise ValueError("Missing QB shadow matchup: "+sid)
        for side in ("home","away"):
            team=game[side]
            qb=game.get("quarterbacks",{}).get(side,{})
            injured=[p for p in qb.get("reportedQuarterbacks",[]) if str(p.get("status","")).lower().strip() in OUT]
            adj=byid[sid].get("qbAdjustments",{}).get(side,{})
            if not injured or adj.get("status")=="EXPERIMENTAL_APPLIED":continue
            counts={}
            for p in injured:
                name=p.get("name","")
                counts[name]=sum(r.get("team")==team and r.get("primaryPasser","").casefold()==name.casefold() and r.get("gameDate","")<game["date"] for r in history.get("records",[]))
            candidate=str(qb.get("depthChartQB1Candidate") or "").casefold()
            recent=str(qb.get("recentPrimaryPasser") or "").casefold()
            names={p.get("name","").casefold() for p in injured}
            if max(counts.values(),default=0)>=2:
                priority="P1_ESTABLISHED_PRIMARY_PASSER_ABSENT"
            elif candidate in names or recent in names:
                priority="P1_CURRENT_QB_CANDIDATE_ABSENT"
            else:
                priority="P2_ROLE_REVIEW_REQUIRED"
            alerts.append({"gameId":sid,"team":team,"opponent":game["away" if side=="home" else "home"],
              "priority":priority,"reportedUnavailable":[{"name":p.get("name"),"status":p.get("status")} for p in injured],
              "priorPrimaryPasserGames":counts,"currentQB1CandidateUnverified":qb.get("depthChartQB1Candidate"),
              "recentPrimaryPasserUnverified":qb.get("recentPrimaryPasser"),"pointsAdjustment":0,
              "status":"UNMODELED_HUMAN_REVIEW_REQUIRED",
              "note":"Historical primary passer is not proof of a start. No score penalty without verified pregame evidence."})
    return {"season":draft["season"],"week":draft["week"],"generatedAt":datetime.now(timezone.utc).isoformat(),
      "reviewCount":len(alerts),"urgentCount":sum(a["priority"].startswith("P1") for a in alerts),
      "status":"REVIEW_REQUIRED" if alerts else "NO_FLAGS","alerts":alerts,
      "policy":"Never rewrite frozen predictions. Injury feeds and depth charts are not official starter verification."}
def main():
    d=json.loads((DATA/"model-c-automated-draft.json").read_text())
    s=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    h=json.loads((DATA/"model-c-historical-qb-games.json").read_text())
    result=build(d,s,h)
    (DATA/"model-c-qb-injury-audit-v2.json").write_text(json.dumps(result,indent=2)+chr(10))
    print("QB review:",result["reviewCount"],"urgent:",result["urgentCount"])
if __name__=="__main__":main()
