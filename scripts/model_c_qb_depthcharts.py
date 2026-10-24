#!/usr/bin/env python3
"""Collect ESPN depth-chart QB1 candidates. Depth chart != confirmed game starter."""
import datetime as dt
import json
import pathlib
import urllib.request

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge/2.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=18) as response:
        return json.load(response)

def extract_qbs(payload):
    """Handle site API's depthchart sections conservatively, with no inferred ordering."""
    candidates=[]
    charts=payload.get("depthchart") or payload.get("depthcharts") or []
    if isinstance(charts,dict):
        charts=list(charts.values())
    for chart in charts:
        if not isinstance(chart,dict):
            continue
        positions=chart.get("positions") or {}
        if isinstance(positions,dict):
            positions=list(positions.values())
        for position in positions:
            if not isinstance(position,dict):
                continue
            meta=position.get("position",{})
            if isinstance(meta,str):meta={"abbreviation":meta}
            if str(meta.get("abbreviation","")).upper()!="QB":continue
            for player in position.get("athletes",[]):
                athlete=player.get("athlete",player)
                rank=player.get("rank",player.get("depth",player.get("slot")))
                name=athlete.get("displayName")
                if name and str(rank)=="1":candidates.append(name)
    return sorted(set(candidates))

def main():
    teams=fetch(BASE+"/teams?limit=40")
    entries=teams.get("sports",[{}])[0].get("leagues",[{}])[0].get("teams",[])
    if len(entries)<25:raise RuntimeError("Team list incomplete; no snapshot replaced")
    results={}
    for entry in entries:
        team=entry.get("team",entry)
        name=team.get("displayName")
        ident=team.get("id")
        if not name or not ident:continue
        url=BASE+"/teams/"+str(ident)+"/depthcharts"
        try:
            candidates=extract_qbs(fetch(url))
        except (OSError,ValueError,KeyError,TypeError):
            candidates=[]
        results[name]={"qb1Candidate":candidates[0] if len(candidates)==1 else None,
          "candidateCount":len(candidates),"source":url,"verification":"DEPTH_CHART_ONLY_NOT_CONFIRMED",
          "note":"QB1 is a depth-chart listing, not a confirmed game starter."}
    if len(results)<25:raise RuntimeError("Insufficient team coverage; previous snapshot preserved")
    if not any(x["qb1Candidate"] for x in results.values()):
        raise RuntimeError("No QB1 candidates parsed from ESPN depth charts; preserve previous snapshot rather than publish empty results")
    out={"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "status":"DEPTH_CHART_CANDIDATES_ONLY","teams":results}
    (DATA/"model-c-qb-depthcharts.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Depth chart candidate snapshot:",len(results),"teams;",sum(bool(x["qb1Candidate"]) for x in results.values()),"QB1 candidates")

if __name__=="__main__":main()
