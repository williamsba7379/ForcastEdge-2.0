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
                candidate=str(depth or "").strip().casefold()
                recent=str(qb.get("recentPrimaryPasser") or "").strip().casefold()
                flagged={str(x["name"] or "").strip().casefold() for x in unavailable}
                # Neither depth charts nor last-game passers establish an official starter.
                # Their agreement provides triage evidence only.
                matches_candidate=bool(candidate and candidate in flagged)
                matches_recent=bool(recent and recent in flagged)
                if matches_candidate or matches_recent:
                    priority="P1_POSSIBLE_STARTER_ABSENCE"
                    rationale="Unavailable QB matches depth-chart QB1 candidate or recent primary passer; not verified as current starter."
                elif candidate and recent and candidate==recent and candidate not in flagged:
                    priority="P3_LIKELY_RESERVE_ABSENCE"
                    rationale="Depth-chart QB1 candidate and recent primary passer agree on a different QB; backup status not officially verified."
                else:
                    priority="P2_ROLE_UNCERTAIN"
                    rationale="Insufficient independent role indicators to establish starter or reserve status."
                alerts.append({"gameId":str(game["id"]),"date":game["date"],"team":team,
                  "opponent":game["away" if side=="home" else "home"],
                  "severity":"QB_AVAILABILITY_UNMODELED",
                  "priority":priority,"priorityRationale":rationale,
                  "roleEvidence":"UNVERIFIED_TRIAGE_ONLY",
                  "recentPrimaryPasserUnverified":qb.get("recentPrimaryPasser"),
                  "reportedUnavailable":unavailable,
                  "depthChartCandidateUnverified":depth,
                  "verifiedStarter":starter,
                  "qbAdjustmentPoints":adjustment.get("points",0),
                  "requiresHumanReview":True,
                  "note":"Availability report is not starter confirmation. QB adjustment absent; pick is not injury-aware."})
    return {"season":draft["season"],"week":draft["week"],
      "status":"REVIEW_REQUIRED" if alerts else "NO_SEVERE_UNMODELED_QB_FLAGS",
      "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "criticalCount":sum(a["priority"]=="P1_POSSIBLE_STARTER_ABSENCE" for a in alerts),
      "reviewCount":len(alerts),
      "priorityCounts":{p:sum(a["priority"]==p for a in alerts) for p in ("P1_POSSIBLE_STARTER_ABSENCE","P2_ROLE_UNCERTAIN","P3_LIKELY_RESERVE_ABSENCE")},
      "alerts":alerts,
      "policy":"Priorities are triage signals, not verified starter identities or numerical adjustments. Preserve frozen picks."}

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    shadow=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    result=audit(draft,shadow)
    (DATA/"model-c-qb-injury-audit.json").write_text(json.dumps(result,indent=2)+"
")
    print("QB availability review flags:",result["reviewCount"],"possible starter:",result["criticalCount"])
    for a in result["alerts"]:print(a["team"],a["gameId"],a["priority"],a["reportedUnavailable"])
if __name__=="__main__":main()
