#!/usr/bin/env python3
"""Collect QB passing totals from ESPN final-game box scores (passing only).
No starter or backup designation inferred. Never uses nonfinal games.
"""
import datetime as dt
import json
import pathlib
import urllib.request

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge/2.0"})
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.load(response)

def main():
    schedule=json.loads((DATA/"nfl-schedule.json").read_text())
    season=schedule["season"]
    now=dt.datetime.now(dt.timezone.utc)
    # ESPN season scoreboard events by week, from season start through current week.
    upcoming=[w["week"] for w in schedule["weeks"]]
    last_week=min(upcoming) if upcoming else 18
    records={}
    games_count=0
    for week in range(1,last_week+1):
        board=fetch(f"{BASE}/scoreboard?dates={season}&seasontype=2&week={week}")
        for event in board.get("events",[]):
            when=dt.datetime.fromisoformat(event["date"].replace("Z","+00:00"))
            if when>=now or not event.get("status",{}).get("type",{}).get("completed"):
                continue
            detail=fetch(f"{BASE}/summary?event={event['id']}")
            games_count+=1
            for team_entry in detail.get("boxscore",{}).get("players",[]):
                team=team_entry.get("team",{}).get("displayName")
                if not team:continue
                for category in team_entry.get("statistics",[]):
                    if category.get("name")!="passing":continue
                    labels=[str(x).lower() for x in category.get("labels",[])]
                    for athlete in category.get("athletes",[]):
                        if athlete.get("didNotPlay"):continue
                        player=athlete.get("athlete",{}).get("displayName")
                        vals=athlete.get("stats",[])
                        if not player or len(vals)!=len(labels):continue
                        line=dict(zip(labels,vals))
                        try:
                            comp,attempts=map(int,line["c/att"].split("/"))
                            yards=int(line["yds"].replace(",",""))
                            tds=int(line["td"])
                            ints=int(line["int"])
                        except (ValueError,KeyError,AttributeError):
                            continue
                        item=records.setdefault(team,{}).setdefault(player,{"passYards":0,"passTD":0,"interceptions":0,"passAttempts":0,"games":0,"source":BASE+"/summary"})
                        item["passYards"]+=yards
                        item["passTD"]+=tds
                        item["interceptions"]+=ints
                        item["passAttempts"]+=attempts
                        item["games"]+=1
    if not records:raise RuntimeError("No usable final-game passing lines; previous data preserved")
    timestamp=now.isoformat()
    for team in records.values():
        for item in team.values():item["asOf"]=timestamp
    out={"season":season,"asOf":timestamp,"metric":"adjusted yards per pass attempt (AYA), not ANY/A; sack data unavailable",
         "source":BASE+"/summary","gamesProcessed":games_count,"teams":records}
    (DATA/"model-c-qb-performance.json").write_text(json.dumps(out,indent=2)+"\n")
    print(f"QB passing totals collected for {sum(map(len,records.values()))} players in {games_count} completed games.")

if __name__=="__main__":main()
