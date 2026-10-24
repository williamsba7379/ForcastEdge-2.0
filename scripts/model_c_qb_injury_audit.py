#!/usr/bin/env python3
"""Audit severe QB availability mismatches without rewriting any frozen picks."""
import json
import pathlib
import datetime as dt

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
SEVERE={"injured reserve","ir","out","suspended","physically unable to perform","pup"}
def audit(draft,shadow):
    q={str(g["id"]):g for g in shadow["games"]}
    alerts=[]
    for game in draft["games"]:
        sh=q.get(str(game["id"]))
        if sh is None:raise ValueError("Missing shadow game "+str(game["id"]))
        for side in ("home","away"):
            team=game[side]
            qb=game.get("quarterbacks",{}).get(side,{})
            depth=qb.get("depthChartQB1Candidate")
            reported=qb.get("reportedQuarterbacks",[])
            unavailable=[{"name":p.get("name"),"status":p.get("status")} for p in reported if str(p.get("status","")).strip().casefold() in SEVERE]
            starter=qb.get("starter")
            adjustment=sh.get("qbAdjustments",{}).get(side,{})
            # Unavailability can be reliably flagged, but cannot identify a confirmed replacement.
            if unavailable and adjustment.get("status")!="EXPERIMENTAL_APPLIED":
                alerts.append({"gameId":str(game["id"]),"date":game["date"],"team":team,
                  "opponent":game["away" if side=="home" else "home"],
                  "severity":"CRITICAL_QB_AVAILABILITY_UNMODELED",
                  "reportedUnavailable":unavailable,
                  "depthChartCandidateUnverified":depth,
                  "verifiedStarter":starter,
                  "qbAdjustmentPoints":adjustment.get("points",0),
                  "requiresHumanReview":True,
                  "note":"Availability report is not starter confirmation. QB adjustment absent; pick is not injury-aware."})
    return {"season":draft["season"],"week":draft["week"],
      "status":"REVIEW_REQUIRED" if alerts else "NO_SEVERE_UNMODELED_QB_FLAGS",
      "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "criticalCount":len(alerts),"alerts":alerts,
      "policy":"Do not silently label picks injury-aware when a key QB is reported unavailable and no verified score adjustment was made. Preserve frozen picks."}

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    shadow=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    result=audit(draft,shadow)
    (DATA/"model-c-qb-injury-audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print("CRITICAL QB availability flags:",result["criticalCount"])
    for a in result["alerts"]:print(a["team"],a["gameId"],a["reportedUnavailable"])
if __name__=="__main__":main()
