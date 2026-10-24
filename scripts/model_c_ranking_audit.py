#!/usr/bin/env python3
"""Audit Week 8 QB news ranking coverage; never infer starter declarations."""
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def audit(ranked):
    items=ranked["items"]
    eligible=[(x,y) for x in items for y in x["rankedLinks"] if y.get("pregameShortlistEligible")]
    undated=[(x,y) for x in items for y in x["rankedLinks"] if "DATE_UNVERIFIED" in y.get("reasons",[])]
    return {
        "status":"REVIEW_COVERAGE_AUDIT_ONLY",
        "season":ranked.get("season"),"week":ranked.get("week"),
        "teamGameEntries":len(items),
        "totalRankedLinks":sum(len(x["rankedLinks"]) for x in items),
        "eligiblePregameLinks":len(eligible),
        "teamsWithEligibleLinks":len(set(x["team"] for x,y in eligible)),
        "undatedLinks":len(undated),
        "noEligibleLinkTeams":[x["team"] for x in items if not any(y.get("pregameShortlistEligible") for y in x["rankedLinks"])],
        "automaticConfirmations":0,
        "interpretation":"Zero eligible links means no dated, own-team QB status leads were found in the available index headlines. It does not mean no QB news exists.",
        "reviewRequired":True
    }

def main():
    ranked=json.loads((DATA/"model-c-qb-ranked-news.json").read_text())
    result=audit(ranked)
    (DATA/"model-c-qb-ranking-audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print("QB news audit:",result["eligiblePregameLinks"],"eligible links for",result["teamGameEntries"],"team-game entries")

if __name__=="__main__":main()
