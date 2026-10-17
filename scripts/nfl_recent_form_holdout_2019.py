#!/usr/bin/env python3
"""Prespecified 2019 holdout comparison: 0% vs 30% last-three-game form.
2019 is separate from the 2023-2026 exploratory sample. Do not tune on these results.
"""
import datetime
import json
import pathlib
import urllib.request
from nfl_team_strength import kickoff, team_metrics

SEASON=2019
BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
games=[]
for week in range(1,18):
    request=urllib.request.Request(f"{BASE}?dates={SEASON}&seasontype=2&week={week}",headers={"User-Agent":"ForecastEdge/2.1"})
    with urllib.request.urlopen(request,timeout=30) as response:
        board=json.load(response)
    for event in board.get("events",[]):
        if event.get("status",{}).get("type",{}).get("completed") is not True:continue
        sides=event.get("competitions",[{}])[0].get("competitors",[])
        home=next((x for x in sides if x.get("homeAway")=="home"),None)
        away=next((x for x in sides if x.get("homeAway")=="away"),None)
        if not home or not away:continue
        try:hs,aws=int(home["score"]),int(away["score"])
        except (KeyError,ValueError,TypeError):continue
        games.append({"id":event["id"],"week":week,"date":event["date"],
          "home":home["team"]["displayName"],"away":away["team"]["displayName"],
          "homeScore":hs,"awayScore":aws,
          "winner":home["team"]["displayName"] if hs>aws else away["team"]["displayName"] if aws>hs else "TIE"})
games.sort(key=lambda g:(kickoff(g),g["id"]))
if len(games)<250:raise ValueError(f"Incomplete 2019 regular season: {len(games)} games")
rows=[]
for game in games:
    prior=[g for g in games if kickoff(g)<kickoff(game)]
    home=team_metrics(prior,game["home"])
    away=team_metrics(prior,game["away"])
    if min(home["games"],away["games"])<2 or game["winner"]=="TIE":continue
    def pick(weight):
        h=(1-weight)*home["pointDifferential"]+weight*home["recentDifferential"]
        a=(1-weight)*away["pointDifferential"]+weight*away["recentDifferential"]
        return game["home"] if h-a+1.5>=0 else game["away"]
    rows.append({"week":game["week"],"id":game["id"],"winner":game["winner"],
                 "baselinePick":pick(0.3),"candidatePick":pick(0.0),
                 "baselineCorrect":pick(0.3)==game["winner"],
                 "candidateCorrect":pick(0.0)==game["winner"]})
n=len(rows)
if n<200:raise ValueError(f"Too few graded games: {n}")
b=sum(r["baselineCorrect"] for r in rows)
c=sum(r["candidateCorrect"] for r in rows)
out={"season":SEASON,"status":"One-time historical holdout; not prospective validation",
 "prespecifiedComparison":"Existing 30% recent differential versus 0% recent differential; 1.5-point home advantage; minimum two earlier games per team",
 "leakageControl":"Only earlier kickoffs within the 2019 season; no future games",
 "caution":"Do not tune weights on 2019 and call subsequent 2019 results independent.",
 "gamesAvailable":len(games),"graded":n,"skipped":len(games)-n,
 "baseline30":{"correct":b,"accuracy":round(b/n,4)},
 "candidate0":{"correct":c,"accuracy":round(c/n,4)},
 "netCandidateCorrect":c-b,"differencePercentagePoints":round(100*(c-b)/n,2),
 "changedPicks":sum(r["baselinePick"]!=r["candidatePick"] for r in rows),
 "byWeek":[{"week":w,"graded":sum(r["week"]==w for r in rows),
 "baselineCorrect":sum(r["week"]==w and r["baselineCorrect"] for r in rows),
 "candidateCorrect":sum(r["week"]==w and r["candidateCorrect"] for r in rows)} for w in range(1,18)],
 "predictions":rows,"productionModelChanged":False,
 "evaluatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat()}
path=pathlib.Path("data/nfl-recent-form-holdout-2019.json")
path.write_text(json.dumps(out,indent=2)+"\n")
print(f"2019 holdout: 30% {b}/{n} ({b/n:.1%}), 0% {c}/{n} ({c/n:.1%}); difference {c-b:+d} picks; skipped {len(games)-n}")
