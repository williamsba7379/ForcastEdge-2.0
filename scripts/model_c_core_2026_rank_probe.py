#!/usr/bin/env python3
"""Read-only 2026 ESPN Core QB rank probe. Never promotes a starter or writes snapshots."""
import json
import sys
import urllib.request

URL="https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/6/depthcharts"
RANK_FIELDS=("rank","depth","depthOrder","order","slot")

def summarize(payload):
    if not isinstance(payload,dict):
        return {"status":"UNSUPPORTED_PAYLOAD","type":type(payload).__name__}
    items=payload.get("items")
    if not isinstance(items,list):
        return {"status":"UNSUPPORTED_PAYLOAD","topLevelKeys":sorted(payload)[:15]}
    positions=0
    qb_positions=0
    ranked=0
    unranked=0
    for chart in items[:20]:
        if not isinstance(chart,dict): continue
        for pos in chart.get("positions",[]) if isinstance(chart.get("positions"),list) else []:
            if not isinstance(pos,dict): continue
            positions+=1
            meta=pos.get("position") or {}
            if not isinstance(meta,dict) or str(meta.get("abbreviation","")).upper()!="QB":continue
            qb_positions+=1
            for athlete in pos.get("athletes",[]) if isinstance(pos.get("athletes"),list) else []:
                if not isinstance(athlete,dict):continue
                if any(athlete.get(k) is not None for k in RANK_FIELDS):ranked+=1
                else:unranked+=1
    return {"status":"STRUCTURE_ONLY","chartCount":len(items),"positionsInspected":positions,
            "qbPositions":qb_positions,"qbEntriesWithExplicitRank":ranked,
            "qbEntriesWithoutExplicitRank":unranked,
            "note":"Ranks are depth-chart evidence only, never confirmed game starters."}

def test():
    sample={"items":[{"positions":[{"position":{"abbreviation":"QB"},"athletes":[
        {"athlete":{"$ref":"PRIVATE_REF"},"rank":1},{"athlete":{"$ref":"PRIVATE_REF2"}}]},
        {"position":{"abbreviation":"RB"},"athletes":[{"rank":1}]}]}]}
    result=summarize(sample)
    assert result["qbPositions"]==1 and result["qbEntriesWithExplicitRank"]==1
    assert result["qbEntriesWithoutExplicitRank"]==1
    assert "PRIVATE" not in json.dumps(result)
    assert summarize({"items":[{"positions":[{"position":{"abbreviation":"QB"},"athletes":[{"athlete":{"displayName":"Never infer"}}]}]}]})["qbEntriesWithExplicitRank"]==0
    assert summarize({"depthchart":[]})["status"]=="UNSUPPORTED_PAYLOAD"
    print("PASS: Core structure-only probe fixtures, explicit rank, fail-closed unranked, no player data")

def live():
    req=urllib.request.Request(URL,headers={"User-Agent":"ForecastEdge/2.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=18) as response: payload=json.load(response)
    report=summarize(payload)
    print("ESPN Core 2026 structure-only diagnostic:",json.dumps(report,sort_keys=True))
    if report["status"]!="STRUCTURE_ONLY" or report["qbPositions"]<1 or report["qbEntriesWithExplicitRank"]<1:
        raise RuntimeError("Core 2026 explicit QB ranking not established; no starter promoted")
    print("PASS: explicit depth-chart rank exists; game-specific starter still unconfirmed")

if __name__=="__main__":
    test()
    if "--live" in sys.argv:live()
