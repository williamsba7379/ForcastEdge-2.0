#!/usr/bin/env python3
"""Retrieve ESPN's current league-wide NFL injury listings, preserving provenance.
Informational feed ONLY: statuses do not automatically establish starting QBs or point values.
"""
import datetime as dt
import json
import pathlib
import urllib.request

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"ForecastEdge/2.0 (injury monitoring)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=35) as response:
        raw=json.load(response)
    groups=raw.get("injuries")
    if not isinstance(groups,list) or not groups:
        raise RuntimeError("ESPN injury response empty or unexpected; preserving previous snapshot")
    teams=[]
    for group in groups:
        team=group.get("team") or {}
        entries=group.get("injuries") or []
        if not isinstance(entries,list):continue
        players=[]
        for item in entries:
            athlete=item.get("athlete") or {}
            position=athlete.get("position") or {}
            status=item.get("status") or item.get("type") or "Unspecified"
            if isinstance(status,dict):status=status.get("description") or status.get("name") or "Unspecified"
            name=athlete.get("displayName") or athlete.get("fullName")
            if not name:continue
            players.append({"name":name,"position":position.get("abbreviation") or position.get("name") or "",
              "status":str(status),"description":str(item.get("details") or item.get("description") or "")[:350]})
        if players:
            teams.append({"team":team.get("displayName") or team.get("name") or "",
              "abbreviation":team.get("abbreviation") or "","teamId":team.get("id"),"players":players})
    if not teams:raise RuntimeError("No recognizable injury entries; preserving previous snapshot")
    out={"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"source":URL,
      "status":"UNVERIFIED_REPORTING_FEED","caution":"Reported injuries only. Not confirmed starting lineups, expected workload, or calibrated point adjustments.",
      "teams":teams}
    (DATA/"model-c-injury-snapshot.json").write_text(json.dumps(out,indent=2)+"\n")
    print(f"Saved {sum(len(t['players']) for t in teams)} injury listings across {len(teams)} teams.")

if __name__=="__main__":main()
