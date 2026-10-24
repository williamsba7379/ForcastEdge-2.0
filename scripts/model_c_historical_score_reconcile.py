#!/usr/bin/env python3
"""Safely reconcile missing historical final scores from ESPN scoreboard.
Never overwrite existing scores; reject conflicting results and nonfinal games.
"""
import datetime as dt
import json
import pathlib
from model_c_qb_stats import BASE,fetch

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def reconcile(history, qb, boards):
    games=list(history.get("games",[]))
    existing={str(g["id"]):g for g in games}
    wanted={str(r["gameId"]) for r in qb.get("records",[])}
    missing=wanted-set(existing)
    added=[]
    unresolved=[]
    conflicts=[]
    for gid in sorted(missing):
        event=boards.get(gid)
        if not event or not event.get("status",{}).get("type",{}).get("completed"):
            unresolved.append(gid)
            continue
        comp=event.get("competitions",[{}])[0]
        sides=comp.get("competitors",[])
        home=next((s for s in sides if s.get("homeAway")=="home"),None)
        away=next((s for s in sides if s.get("homeAway")=="away"),None)
        try:
            if not home or not away:raise ValueError("missing team")
            hs=int(home["score"]);ascore=int(away["score"])
            home_name=home["team"]["displayName"];away_name=away["team"]["displayName"]
            date=event["date"]
            expected={r["team"] for r in qb["records"] if str(r["gameId"])==gid}
            dates={r["gameDate"] for r in qb["records"] if str(r["gameId"])==gid}
            if expected!={home_name,away_name} or dates!={date}:
                conflicts.append({"gameId":gid,"reason":"QB team/date mismatch"})
                continue
            if hs==ascore:winner=None
            else:winner=home_name if hs>ascore else away_name
            week=event.get("week",{}).get("number")
            if not week:
                week=next((g.get("week") for g in history.get("games",[]) if g.get("season")==qb.get("season") and g.get("date","")[:10]==date[:10]),None)
            if not week:
                conflicts.append({"gameId":gid,"reason":"week unavailable"})
                continue
            added.append({"season":qb["season"],"id":gid,"week":int(week),"date":date,
                          "home":home_name,"away":away_name,"homeScore":hs,"awayScore":ascore,"winner":winner})
        except (KeyError,ValueError,TypeError):
            conflicts.append({"gameId":gid,"reason":"incomplete final scoreboard"})
    if conflicts:
        return history,{"status":"BLOCKED_CONFLICTS","missingBefore":len(missing),"added":0,"unresolved":unresolved,"conflicts":conflicts}
    merged=dict(history)
    merged["games"]=games+added
    merged["updatedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
    return merged,{"status":"COMPLETE" if not unresolved else "PARTIAL","missingBefore":len(missing),
                   "added":len(added),"unresolved":unresolved,"conflicts":[]}

def main():
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    qb=json.loads((DATA/"model-c-historical-qb-games.json").read_text())
    season=qb["season"]
    boards={}
    for week in range(1,19):
        board=fetch(f"{BASE}/scoreboard?dates={season}&seasontype=2&week={week}")
        for event in board.get("events",[]):
            boards[str(event["id"])]=event
    updated,report=reconcile(history,qb,boards)
    (DATA/"model-c-historical-score-reconciliation.json").write_text(json.dumps(report,indent=2)+"\n")
    if report["status"]=="BLOCKED_CONFLICTS":
        raise RuntimeError("Score reconciliation blocked; existing history preserved")
    if report["added"]:
        (DATA/"nfl-historical-results.json").write_text(json.dumps(updated,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
