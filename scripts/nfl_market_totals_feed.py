#!/usr/bin/env python3
"""Read public NFL scoreboard totals; do not invent missing lines."""
import argparse
import datetime as dt
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlencode
from nfl_four_model_head_to_head import stamp

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def collect(card):
    query = urlencode({"dates": card["season"], "seasontype": 2, "week": card["week"]})
    source = f"{URL}?{query}"
    games={str(g["id"]):g for g in card["games"]}
    req=urllib.request.Request(source,headers={"User-Agent":"ForecastEdge-Research"})
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
                                  "source":source,"capturedAt":now.isoformat()})
    return {"season":card["season"],"week":card["week"],"games":lines}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(json.loads(args.draft.read_text()))
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
    print("Market lines collected:", len(result["games"]))
if __name__=="__main__":main()
