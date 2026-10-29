#!/usr/bin/env python3
"""Read public NFL scoreboard totals; do not invent missing lines."""
import datetime as dt
import json
import urllib.request
from nfl_four_model_head_to_head import DATA,OUT,stamp

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def main():
    files=sorted(OUT.glob("*-refresh-*.json"))
    if not files:raise ValueError("Missing comparison")
    card=json.loads(files[-1].read_text())
    games={str(g["id"]):g for g in card["games"]}
    req=urllib.request.Request(URL,headers={"User-Agent":"ForecastEdge-Research"})
    with urllib.request.urlopen(req,timeout=20) as response:
        payload=json.load(response)
    now=dt.datetime.now(dt.timezone.utc)
    lines=[]
    for event in payload.get("events",[]):
        key=str(event.get("id",""))
        if key not in games or now>=stamp(games[key]["date"]):continue
        for competition in event.get("competitions",[])[:1]:
            for odd in competition.get("odds",[])[:1]:
                total=odd.get("overUnder")
                provider=(odd.get("provider") or {}).get("name")
                if type(total) in (float,int) and 10<=total<=100 and provider:
                    lines.append({"id":key,"total":float(total),"provider":provider,
                                  "source":URL,"capturedAt":now.isoformat()})
    result={"season":card["season"],"week":card["week"],"games":lines}
    (DATA/"nfl-market-totals.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Market lines collected:",len(lines))
if __name__=="__main__":main()
