#!/usr/bin/env python3
"""Read-only 2026 ESPN Core NFL team QB depth-chart coverage diagnostic."""
import json
import sys
import urllib.request
from urllib.error import HTTPError, URLError
from model_c_core_2026_rank_probe import summarize

TEAMS_URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=40"
CORE="https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/{team_id}/depthcharts"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge/2.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=18) as response:
        return json.load(response)

def team_ids(payload):
    entries=payload.get("sports",[{}])[0].get("leagues",[{}])[0].get("teams",[])
    ids=[str((x.get("team") or x).get("id")) for x in entries if isinstance(x,dict) and (x.get("team") or x).get("id")]
    if len(ids)!=32 or len(set(ids))!=32:
        raise RuntimeError("NFL team coverage not exactly 32; no coverage result accepted")
    return sorted(ids,key=int)

def classify(payload):
    report=summarize(payload)
    if report.get("status")!="STRUCTURE_ONLY":return "UNSUPPORTED_STRUCTURE",report
    if report["qbPositions"]==0:return "NO_QB_POSITION",report
    if report["qbEntriesWithExplicitRank"]==0:return "NO_EXPLICIT_QB_RANK",report
    return "EXPLICIT_QB_RANK_PRESENT",report

def fixtures():
    teams={"sports":[{"leagues":[{"teams":[{"team":{"id":str(i)}} for i in range(1,33)]}]}]}
    assert len(team_ids(teams))==32
    for bad in (teams["sports"][0]["leagues"][0]["teams"][:31],
                teams["sports"][0]["leagues"][0]["teams"][:31]+[{"team":{"id":"1"}}]):
        broken={"sports":[{"leagues":[{"teams":bad}]}]}
        try:team_ids(broken)
        except RuntimeError:pass
        else:raise AssertionError("Incomplete or duplicate team list accepted")
    ranked={"items":[{"positions":{"qb":{"athletes":[{"rank":1,"athlete":{"displayName":"SECRET"}}]}}}]}
    unranked={"items":[{"positions":{"qb":{"athletes":[{"athlete":{"displayName":"SECRET"}}]}}}]}
    assert classify(ranked)[0]=="EXPLICIT_QB_RANK_PRESENT"
    assert classify(unranked)[0]=="NO_EXPLICIT_QB_RANK"
    assert classify({"items":[{"positions":{"rb":{"athletes":[]}}}]})[0]=="NO_QB_POSITION"
    assert classify({"unexpected":[]})[0]=="UNSUPPORTED_STRUCTURE"
    assert "SECRET" not in json.dumps(classify(ranked))
    print("PASS: 32 unique teams, missing/duplicate coverage fail closed, QB ranking classifications, no player data")

def live():
    ids=team_ids(fetch(TEAMS_URL))
    counts={}
    failures=[]
    for team_id in ids:
        try:
            status,report=classify(fetch(CORE.format(team_id=team_id)))
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError) as exc:
            status="FETCH_ERROR"
            if len(failures)<5:failures.append({"teamId":team_id,"errorType":type(exc).__name__})
        counts[status]=counts.get(status,0)+1
    print("2026 Core 32-team QB rank coverage:",json.dumps({"teamsChecked":len(ids),"counts":counts,"sampleFailures":failures},sort_keys=True))
    assert sum(counts.values())==32
    if counts.get("EXPLICIT_QB_RANK_PRESENT",0)==0:
        raise RuntimeError("No explicit QB ranks across 32 teams; no starter promoted")
    print("PASS: at least one explicit QB depth-chart rank; never confirmed game starter")

if __name__=="__main__":
    fixtures()
    if "--live" in sys.argv:live()
