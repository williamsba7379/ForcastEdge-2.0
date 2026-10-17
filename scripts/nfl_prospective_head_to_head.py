#!/usr/bin/env python3
"""Prospective NFL winner-only comparison. Freeze picks before games; grade without rewriting them."""
import datetime as dt
import json
import pathlib
import urllib.request
from zoneinfo import ZoneInfo
from nfl_team_strength import team_metrics, kickoff

ROOT=pathlib.Path("data/prospective-head-to-head")
ROOT.mkdir(parents=True,exist_ok=True)
BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
EASTERN=ZoneInfo("America/New_York")

def fetch(params):
    from urllib.parse import urlencode
    req=urllib.request.Request(BASE+"?"+urlencode(params),headers={"User-Agent":"ForecastEdge-prospective/1.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        return json.load(response)

def parse(board,season):
    out=[]
    for e in board.get("events",[]):
        try:
            comp=e["competitions"][0]["competitors"]
            home=next(x for x in comp if x["homeAway"]=="home")
            away=next(x for x in comp if x["homeAway"]=="away")
            completed=e.get("status",{}).get("type",{}).get("completed",False)
            hs=int(home["score"]) if completed else None
            aws=int(away["score"]) if completed else None
            out.append({"id":str(e["id"]),"season":season,"week":int(e.get("week",{}).get("number",board.get("week",{}).get("number",0))),
                        "date":e["date"],"home":home["team"]["displayName"],"away":away["team"]["displayName"],
                        "homeScore":hs,"awayScore":aws,"completed":completed,
                        "winner":home["team"]["displayName"] if completed and hs>aws else away["team"]["displayName"] if completed and aws>hs else "TIE" if completed else None})
        except (KeyError,TypeError,ValueError,StopIteration):
            continue
    return out

def historical(season):
    games={}
    for week in range(1,19):
        for g in parse(fetch({"dates":season,"seasontype":2,"week":week}),season):
            if g["completed"]: games[g["id"]]=g
    return sorted(games.values(),key=lambda g:(kickoff(g),g["id"]))

def snapshot(now):
    # Next Thursday through following Monday in US Eastern time.
    days=(3-now.weekday())%7
    thursday=(now+dt.timedelta(days=days)).date()
    monday=thursday+dt.timedelta(days=4)
    season=thursday.year
    file=ROOT/(thursday.isoformat()+".json")
    if file.exists():
        print("Existing frozen snapshot preserved:",file)
        return
    # ESPN scoreboard accepts a single YYYYMMDD date, not a hyphenated date range.
    # Query each calendar day separately and deduplicate by event ID.
    fixtures_by_id={}
    for offset in range(5):
        day=thursday+dt.timedelta(days=offset)
        board=fetch({"dates":day.strftime("%Y%m%d"),"limit":1000})
        for g in parse(board,season):
            if thursday<=kickoff(g).astimezone(EASTERN).date()<=monday:
                fixtures_by_id[g["id"]]=g
    fixtures=list(fixtures_by_id.values())
    if not fixtures:
        print("No games in upcoming Thursday-Monday window; no snapshot created")
        return
    if any(g["completed"] for g in fixtures):raise ValueError("Cannot freeze picks after kickoff")
    prior=historical(season)
    rows=[]
    for g in sorted(fixtures,key=lambda x:(kickoff(x),x["id"])):
        older=[p for p in prior if kickoff(p)<kickoff(g) and kickoff(p)<now.astimezone(dt.timezone.utc)]
        hm=team_metrics(older,g["home"])
        am=team_metrics(older,g["away"])
        if min(hm["games"],am["games"])<2:
            # Pool requires an outright pick for every game. Fallback is explicitly marked.
            b=c=g["home"]
            method="fallback_home_insufficient_inseason_data"
        else:
            def pick(w):
                edge=(1-w)*(hm["pointDifferential"]-am["pointDifferential"])+w*(hm["recentDifferential"]-am["recentDifferential"])+1.5
                return g["home"] if edge>=0 else g["away"]
            b,c=pick(0.3),pick(0.0)
            method="model"
        rows.append({"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
                     "week":g["week"],"baseline30Pick":b,"experimental0Pick":c,"method":method,
                     "winner":None,"baseline30Correct":None,"experimental0Correct":None})
    payload={"status":"frozen_pre_kickoff","frozenAt":now.isoformat(),"thursday":thursday.isoformat(),
             "season":season,"comparison":"30% recent three-game differential vs 0%; +1.5 home points",
             "note":"Experimental evaluation only. Neither model is automatically promoted; no wagers.",
             "games":rows}
    file.write_text(json.dumps(payload,indent=2)+"\n")
    print("Frozen",len(rows),"pregame picks in",file)

def grade(now):
    for file in sorted(ROOT.glob("*.json")):
        data=json.loads(file.read_text())
        if not data.get("games"):continue
        last=max(kickoff(g) for g in data["games"])
        if now.astimezone(dt.timezone.utc)<last+dt.timedelta(hours=4):continue
        weeks=sorted({g["week"] for g in data["games"] if g["week"]})
        results={}
        for week in weeks:
            for g in parse(fetch({"dates":data["season"],"seasontype":2,"week":week}),data["season"]):
                results[g["id"]]=g
        changed=False
        for row in data["games"]:
            actual=results.get(row["id"])
            if actual and actual["completed"] and actual["winner"]!="TIE" and row["winner"] is None:
                row["winner"]=actual["winner"]
                row["baseline30Correct"]=row["baseline30Pick"]==actual["winner"]
                row["experimental0Correct"]=row["experimental0Pick"]==actual["winner"]
                changed=True
        if changed:
            graded=[r for r in data["games"] if r["winner"] is not None]
            data["gradedAt"]=now.isoformat()
            data["status"]="graded" if len(graded)==len(data["games"]) else "partially_graded"
            data["results"]={"graded":len(graded),"baseline30Correct":sum(r["baseline30Correct"] for r in graded),
                             "experimental0Correct":sum(r["experimental0Correct"] for r in graded)}
            file.write_text(json.dumps(data,indent=2)+"\n")
            print("Graded",file,data["results"])

if __name__=="__main__":
    import sys
    now=dt.datetime.now(EASTERN)
    if sys.argv[1]=="freeze":snapshot(now)
    elif sys.argv[1]=="grade":grade(now)
    else:raise ValueError("Expected freeze or grade")
