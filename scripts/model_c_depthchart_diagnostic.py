#!/usr/bin/env python3
"""Diagnose live ESPN QB1 depth-chart coverage without inferring starters."""
import datetime as dt
import json
import pathlib
from model_c_qb_depthcharts import BASE, fetch, extract_qbs

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
report={"checkedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "status":"DIAGNOSTIC_ONLY_NOT_STARTER_CONFIRMATION",
        "teamsChecked":0,"teamsWithQB1":0,"teamsWithoutQB1":0,
        "requestErrors":0,"samples":[]}
try:
    listing=fetch(BASE+"/teams?limit=40")
    entries=listing.get("sports",[{}])[0].get("leagues",[{}])[0].get("teams",[])
    for entry in entries:
        team=entry.get("team",entry)
        name=team.get("displayName")
        ident=team.get("id")
        if not name or not ident:
            continue
        report["teamsChecked"]+=1
        url=BASE+"/teams/"+str(ident)+"/depthcharts"
        sample={"team":name,"endpoint":url}
        try:
            payload=fetch(url)
            qbs=extract_qbs(payload)
            sample["qb1Candidates"]=qbs
            sample["topLevelKeys"]=list(payload.keys())[:15]
            charts=payload.get("depthchart") or payload.get("depthcharts")
            sample["depthChartContainerType"]=type(charts).__name__
            if qbs:
                report["teamsWithQB1"]+=1
            else:
                report["teamsWithoutQB1"]+=1
        except Exception as exc:
            report["requestErrors"]+=1
            sample["errorType"]=type(exc).__name__
            sample["errorMessage"]=str(exc)[:150]
        if len(report["samples"])<8 or sample.get("errorType"):
            report["samples"].append(sample)
except Exception as exc:
    report["listingError"]=type(exc).__name__+": "+str(exc)[:200]
report["coveragePercent"]=round(100*report["teamsWithQB1"]/report["teamsChecked"],1) if report["teamsChecked"] else 0
(DATA/"model-c-depthchart-diagnostic.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="samples"},indent=2))
