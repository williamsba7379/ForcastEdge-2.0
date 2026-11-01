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

def describe_depthchart_shape(payload):
    """Only bounded field names/types, never player values or records."""
    charts = payload.get("depthchart") if isinstance(payload, dict) else None
    if not isinstance(charts, list):
        return {"depthchartType": type(charts).__name__, "sampleCharts": []}
    samples = []
    for chart in charts[:2]:
        if not isinstance(chart, dict):
            samples.append({"type": type(chart).__name__})
            continue
        fields = {}
        for key in sorted(chart)[:8]:
            value = chart[key]
            info = {"type": type(value).__name__}
            if isinstance(value, dict):
                info["keys"] = sorted(value)[:8]
            elif isinstance(value, list):
                info["length"] = len(value)
                if value:
                    first = value[0]
                    info["firstType"] = type(first).__name__
                    if isinstance(first, dict):
                        info["firstKeys"] = sorted(first)[:8]
            fields[key] = info
        samples.append({"fields": fields})
    qb_shapes = []
    for chart in charts:
        positions = chart.get("positions") if isinstance(chart, dict) else None
        if not isinstance(positions, dict) or "qb" not in positions:
            continue
        record = positions["qb"]
        if not isinstance(record, dict):
            qb_shapes.append({"type": type(record).__name__})
            continue
        details = {"keys": sorted(record)[:12]}
        for field in ("athletes", "players", "entries"):
            value = record.get(field)
            if isinstance(value, list):
                details[field] = {"type": "list", "length": len(value)}
                if value:
                    details[field]["firstType"] = type(value[0]).__name__
                    if isinstance(value[0], dict):
                        details[field]["firstKeys"] = sorted(value[0])[:12]
        qb_shapes.append(details)
        if len(qb_shapes) >= 2:
            break
    return {"depthchartType": "list", "sampleCharts": samples, "qbShapes": qb_shapes}

def extract_qbs(payload):
    """Extract explicitly ranked QB1 only; never infer a starter from list order."""
    charts = payload.get("depthchart") or payload.get("depthcharts") or []
    if isinstance(charts, dict):
        charts = list(charts.values())
    candidates = []
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        positions = chart.get("positions") or {}
        if isinstance(positions, dict):
            positions = list(positions.items())
        elif isinstance(positions, list):
            positions = [(None, item) for item in positions]
        if not isinstance(positions, list):
            continue
        for position_key, position in positions:
            if not isinstance(position, dict):
                continue
            meta = position.get("position") or {}
            abbr = meta.get("abbreviation") if isinstance(meta, dict) else None
            abbr = abbr or position.get("abbreviation") or position.get("positionAbbreviation") or position_key
            if str(abbr).upper() != "QB":
                continue
            athletes = position.get("athletes") or []
            if not isinstance(athletes, list):
                continue
            for player in athletes:
                if not isinstance(player, dict):
                    continue
                athlete = player.get("athlete") or player
                rank = player.get("rank", player.get("depth", player.get("depthOrder")))
                name = athlete.get("displayName") if isinstance(athlete, dict) else None
                if name and str(rank) == "1":
                    candidates.append(name)
    return sorted(set(candidates))

def main():
    teams=fetch(BASE+"/teams?limit=40")
    entries=teams.get("sports",[{}])[0].get("leagues",[{}])[0].get("teams",[])
    if len(entries)<25:raise RuntimeError("Team list incomplete; no snapshot replaced")
    results={}
    failures=[]
    empty_shapes=[]
    for entry in entries:
        team=entry.get("team",entry)
        name=team.get("displayName")
        ident=team.get("id")
        if not name or not ident:continue
        url=BASE+"/teams/"+str(ident)+"/depthcharts"
        try:
            payload=fetch(url)
            candidates=extract_qbs(payload)
            if not candidates and len(empty_shapes)<3:
                empty_shapes.append({"team":name,"topLevelKeys":sorted(payload.keys()) if isinstance(payload,dict) else [type(payload).__name__],"shape":describe_depthchart_shape(payload)})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            if len(failures)<3:
                failures.append({"team":name,"errorType":type(exc).__name__,"error":str(exc)[:180]})
            candidates=[]
        results[name]={"qb1Candidate":candidates[0] if len(candidates)==1 else None,
          "candidateCount":len(candidates),"source":url,"verification":"DEPTH_CHART_ONLY_NOT_CONFIRMED",
          "note":"QB1 is a depth-chart listing, not a confirmed game starter."}
    if len(results)<25:raise RuntimeError("Insufficient team coverage; previous snapshot preserved")
    if not any(x["qb1Candidate"] for x in results.values()):
        print("QB retrieval diagnostic (no player data):",json.dumps({"sampleFailures":failures,"sampleEmptyPayloadShapes":empty_shapes}))
        raise RuntimeError("Zero QB1 candidates from all teams; refusing to replace prior snapshot")
    out={"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "status":"DEPTH_CHART_CANDIDATES_ONLY","teams":results}
    (DATA/"model-c-qb-depthcharts.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Depth chart candidate snapshot:",len(results),"teams;",sum(bool(x["qb1Candidate"]) for x in results.values()),"QB1 candidates")

if __name__=="__main__":main()
