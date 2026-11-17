"""Read-only ESPN NFL Thursday-Monday schedule snapshot; fail closed on network/schema errors."""
import argparse
import datetime as dt
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

def schedule(now=None, fetch=None):
    now = now or dt.datetime.now(ZoneInfo("America/New_York"))
    local = now.astimezone(ZoneInfo("America/New_York"))
    # Wednesday -> Thursday to Monday, inclusive.
    thursday = local.date() + dt.timedelta(days=(3-local.weekday()) % 7)
    monday = thursday + dt.timedelta(days=4)
    url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
           "?dates=%s-%s&limit=100" % (thursday.strftime("%Y%m%d"), monday.strftime("%Y%m%d")))
    if fetch is None:
        def fetch(url):
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"ForecastEdge-ReadOnly-Audit/1.0"}),timeout=20) as response:
                return json.load(response)
    data = fetch(url)
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("Invalid ESPN schedule response")
    games = []
    for event in data["events"]:
        if not isinstance(event, dict) or not event.get("id") or not event.get("date"):
            raise ValueError("Missing ESPN game identity/time")
        kickoff = dt.datetime.fromisoformat(event["date"].replace("Z","+00:00")).astimezone(ZoneInfo("America/New_York")).date()
        if thursday <= kickoff <= monday:
            games.append({"id":str(event["id"]),"date":event["date"]})
    if not games:
        raise ValueError("No verified NFL games; cannot assert off-week without independent evidence")
    ids = [g["id"] for g in games]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ESPN schedule game IDs")
    return {"source_url":url,"captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"start_date":str(thursday),"end_date":str(monday),"games":games}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("nfl-schedule-audit.json"))
    args=parser.parse_args()
    result=schedule()
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("Verified ESPN NFL schedule: %d games" % len(result["games"]))

if __name__=="__main__":
    main()
