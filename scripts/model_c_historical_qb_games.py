#!/usr/bin/env python3
"""Collect historical game-by-game primary passers, not confirmed starters.
Research only; final-game boxscores cannot prove who took the first snap.
"""
import datetime as dt
import json
import pathlib
from model_c_qb_stats import BASE,fetch

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def extract_game(event, detail, season):
    records=[]
    for entry in detail.get("boxscore",{}).get("players",[]):
        team=entry.get("team",{}).get("displayName")
        if not team:continue
        passers=[]
        for category in entry.get("statistics",[]):
            if category.get("name")!="passing":continue
            labels=[str(x).lower() for x in category.get("labels",[])]
            for row in category.get("athletes",[]):
                if row.get("didNotPlay"):continue
                name=row.get("athlete",{}).get("displayName")
                line=dict(zip(labels,row.get("stats",[])))
                try:
                    attempts=int(line["c/att"].split("/")[1])
                    yards=int(str(line["yds"]).replace(",",""))
                    touchdowns=int(line["td"])
                    interceptions=int(line["int"])
                except (KeyError,ValueError,TypeError,IndexError,AttributeError):
                    continue
                if name and attempts>=0:
                    passers.append({"player":name,"attempts":attempts,"passYards":yards,"passTD":touchdowns,"interceptions":interceptions})
        if passers:
            passers.sort(key=lambda x:(-x["attempts"],x["player"]))
            leader=passers[0]
            tied=len(passers)>1 and passers[1]["attempts"]==leader["attempts"]
            records.append({"season":season,"gameId":str(event["id"]),"gameDate":event["date"],"team":team,
                            "primaryPasser":None if tied else leader["player"],"passers":passers,
                            "starterConfirmed":False,"identityType":"FINAL_GAME_PRIMARY_PASSER_NOT_STARTER",
                            "source":BASE+"/summary?event="+str(event["id"])})
    return records

def main():
    schedule=json.loads((DATA/"nfl-schedule.json").read_text())
    now=dt.datetime.now(dt.timezone.utc)
    # Initial bounded collection: current season only; older seasons require separate verification.
    season=int(schedule["season"])
    weeks=sorted({int(w["week"]) for w in schedule.get("weeks",[]) if int(w["week"])<=18})
    if not weeks:raise RuntimeError("No weeks in schedule")
    rows=[]
    seen=set()
    for week in range(1,max(weeks)+1):
        board=fetch(f"{BASE}/scoreboard?dates={season}&seasontype=2&week={week}")
        for event in board.get("events",[]):
            if not event.get("status",{}).get("type",{}).get("completed"):continue
            try:when=dt.datetime.fromisoformat(event["date"].replace("Z","+00:00"))
            except (KeyError,ValueError):continue
            if when>=now or str(event["id"]) in seen:continue
            seen.add(str(event["id"]))
            detail=fetch(BASE+"/summary?event="+str(event["id"]))
            rows.extend(extract_game(event,detail,season))
    if not rows:raise RuntimeError("No completed games parsed; existing snapshot preserved")
    out={"generatedAt":now.isoformat(),"season":season,"status":"RESEARCH_ONLY_PRIMARY_PASSERS_NOT_STARTERS",
         "teamGameRecords":len(rows),"gameCount":len(seen),"records":rows,
         "warning":"Primary passer is not necessarily the starting QB; no confirmed starter timeline or QB impact calibration."}
    (DATA/"model-c-historical-qb-games.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Collected",len(rows),"team-game primary passer records from",len(seen),"completed games")

if __name__=="__main__":main()
