#!/usr/bin/env python3
"""Promote human-reviewed official team QB announcements to game-specific declarations.
Never infer starters from news snippets, injuries, depth charts or last-game passers.
"""
import datetime as dt
import json
import pathlib
from model_c_engine import official_starter_valid

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def build(schedule,reviewed,now):
    games={str(g["id"]):(g,team) for w in schedule["weeks"] for g in w["games"] for team in ()}
    games={}
    for week in schedule["weeks"]:
        for g in week["games"]:
            for team in (g["home"],g["away"]):
                games[(str(g["id"]),team)]=g
    accepted={}
    rejected=[]
    for row in reviewed.get("entries",[]):
        team=row.get("team")
        key=(str(row.get("gameId","")),team)
        game=games.get(key)
        if not game or not official_starter_valid(row,game,team,now):
            rejected.append({"team":team,"gameId":row.get("gameId"),"reason":"Missing or invalid reviewed official game-specific starter evidence"})
            continue
        if key in accepted:
            rejected.append({"team":team,"gameId":row["gameId"],"reason":"Duplicate declaration; no automatic conflict resolution"})
            accepted.pop(key,None)
            continue
        accepted[key]=row
    teams={}
    for (gid,team),row in accepted.items():
        if team in teams:
            rejected.append({"team":team,"gameId":gid,"reason":"Multiple game declarations for team; requires manual resolution"})
            teams.pop(team,None)
            continue
        teams[team]=row
    return {"season":schedule["season"],"status":"VERIFIED_DECLARATIONS_ONLY" if teams else "NO_CONFIRMED_STARTERS_YET",
            "teams":teams,"rejected":rejected,
            "note":"Only explicitly human-reviewed official team announcements are promoted. Baseline QB evidence is separately required for shadow score adjustments."}

def main():
    schedule=json.loads((DATA/"nfl-schedule.json").read_text())
    reviewed=json.loads((DATA/"model-c-qb-reviewed-announcements.json").read_text())
    out=build(schedule,reviewed,dt.datetime.now(dt.timezone.utc))
    if out["rejected"]:
        raise RuntimeError("QB review intake contains invalid/duplicate declarations; refusing to overwrite verified starter file: "+str(out["rejected"]))
    (DATA/"model-c-qb-starters.json").write_text(json.dumps(out,indent=2)+"\n")
    print("Verified official QB declarations:",len(out["teams"]))

if __name__=="__main__":main()
