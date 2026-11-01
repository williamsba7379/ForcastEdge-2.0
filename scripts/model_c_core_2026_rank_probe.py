#!/usr/bin/env python3
"""Read-only 2026 ESPN Core QB rank probe. Never promotes a starter or writes snapshots."""
import json
import sys
import urllib.request

URL="https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/6/depthcharts"
RANK_FIELDS=("rank","depth","depthOrder","order","slot")

def describe_core_items(payload):
    """Bounded shape-only inspection. No values, URLs, IDs, player names, or raw references."""
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {"itemsType": type(items).__name__, "sampleItems": []}
    samples = []
    for item in items[:3]:
        if not isinstance(item, dict):
            samples.append({"type": type(item).__name__})
            continue
        fields = {}
        for key in sorted(item)[:12]:
            value = item[key]
            detail = {"type": type(value).__name__}
            if isinstance(value, dict):
                detail["keys"] = sorted(value)[:12]
                detail["hasRef"] = "$ref" in value
            elif isinstance(value, list):
                detail["length"] = len(value)
                if value:
                    first = value[0]
                    detail["firstType"] = type(first).__name__
                    if isinstance(first, dict):
                        detail["firstKeys"] = sorted(first)[:12]
                        detail["firstHasRef"] = "$ref" in first
            fields[key] = detail
        samples.append({"fields": fields, "hasRef": "$ref" in item})
    return {"itemsType": "list", "itemCount": len(items), "sampleItems": samples}

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
        raw_positions=chart.get("positions")
        if isinstance(raw_positions,dict):
            entries=list(raw_positions.items())
        elif isinstance(raw_positions,list):
            entries=[(None,pos) for pos in raw_positions]
        else:
            entries=[]
        for key,pos in entries:
            if not isinstance(pos,dict): continue
            positions+=1
            meta=pos.get("position") or {}
            abbr=meta.get("abbreviation") if isinstance(meta,dict) else None
            abbr=abbr or pos.get("abbreviation") or key
            if str(abbr).upper()!="QB":continue
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
    keyed={"items":[{"positions":{"qb":{"athletes":[{"rank":1,"athlete":{"displayName":"Private QB"}},
          {"athlete":{"displayName":"Backup"}}]},"rb":{"athletes":[{"rank":1}]}}}]}
    keyed_result=summarize(keyed)
    assert keyed_result["positionsInspected"]==2 and keyed_result["qbPositions"]==1
    assert keyed_result["qbEntriesWithExplicitRank"]==1 and keyed_result["qbEntriesWithoutExplicitRank"]==1
    keyed["items"][0]["positions"]["qb"]["athletes"][0].pop("rank")
    assert summarize(keyed)["qbEntriesWithExplicitRank"]==0
    assert "Private QB" not in json.dumps(summarize(keyed))
    private="PRIVATE_PLAYER_SECRET_987"
    linked={"items":[{"$ref":"https://private.example/"+private},
                     {"positions":{"$ref":"https://private.example/"+private},
                      "athletes":[{"$ref":"https://private.example/"+private}]},
                     {"name":private,"positions":[{"athlete":{"displayName":private}}]},
                     {"name":"ignored-fourth"}]}
    diagnostic=describe_core_items(linked)
    assert diagnostic["itemCount"]==4 and len(diagnostic["sampleItems"])==3
    assert diagnostic["sampleItems"][0]["hasRef"] is True
    assert diagnostic["sampleItems"][1]["fields"]["positions"]["hasRef"] is True
    assert diagnostic["sampleItems"][1]["fields"]["athletes"]["firstHasRef"] is True
    assert private not in json.dumps(diagnostic)
    assert summarize(linked)["qbEntriesWithExplicitRank"]==0
    assert describe_core_items({"items":"not-a-list"})["sampleItems"]==[]
    print("PASS: Core rank fixtures, bounded three-record reference diagnostics, no player data, fail-closed")

def live():
    req=urllib.request.Request(URL,headers={"User-Agent":"ForecastEdge/2.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=18) as response: payload=json.load(response)
    report=summarize(payload)
    print("ESPN Core 2026 structure-only diagnostic:",json.dumps(report,sort_keys=True))
    print("ESPN Core 2026 item-shape diagnostic:",json.dumps(describe_core_items(payload),sort_keys=True))
    if report["status"]!="STRUCTURE_ONLY" or report["qbPositions"]<1 or report["qbEntriesWithExplicitRank"]<1:
        raise RuntimeError("Core 2026 explicit QB ranking not established; no starter promoted")
    print("PASS: explicit depth-chart rank exists; game-specific starter still unconfirmed")

if __name__=="__main__":
    test()
    if "--live" in sys.argv:live()
