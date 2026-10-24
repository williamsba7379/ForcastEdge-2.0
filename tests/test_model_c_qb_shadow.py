#!/usr/bin/env python3
"""Offline shadow-QB guardrail tests."""
import datetime as dt
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_qb_shadow import adjustment,build,pregame_aya

kickoff="2026-10-25T17:00:00Z"
now=dt.datetime.fromisoformat("2026-10-24T12:00:00+00:00")
game={"id":"123","date":kickoff,"home":"Home Team","away":"Away Team","pick":"Home Team","homeEdgePoints":1.0}
def row(team,name,day,attempts,yards):
    return {"team":team,"gameDate":day,"passers":[{"player":name,"attempts":attempts,"passYards":yards,"passTD":0,"interceptions":0}]}
history=[row("Home Team","Old QB","2026-10-01T17:00:00Z",100,700),
         row("Home Team","New QB","2026-10-05T17:00:00Z",100,400),
         row("Home Team","New QB","2026-10-26T17:00:00Z",100,10000)]
declaration={"team":"Home Team","gameId":"123","status":"CONFIRMED_STARTER","sourceType":"TEAM_ANNOUNCEMENT",
             "reviewed":True,"evidenceText":"Official team announcement confirms New QB starting.",
             "starter":"New QB","source":"https://example.org/confirmed","asOf":"2026-10-24T11:00:00Z",
             "baselineStarter":"Old QB","baselineSource":"https://example.org/baseline",
             "baselineReviewed":True,"baselineAsOf":"2026-10-23T10:00:00Z"}
assert pregame_aya(history,"Home Team","New QB",dt.datetime.fromisoformat(kickoff.replace("Z","+00:00")))["aya"]==4
result=adjustment(game,"home",{"Home Team":declaration},history,now)
assert result["status"]=="EXPERIMENTAL_APPLIED" and result["points"]==-1.05,result
assert adjustment(game,"home",{},history,now)["points"]==0
assert adjustment(game,"home",{"Home Team":{**declaration,"reviewed":False}},history,now)["points"]==0
assert adjustment(game,"home",{"Home Team":{**declaration,"baselineReviewed":False}},history,now)["points"]==0
assert adjustment(game,"home",{"Home Team":{**declaration,"asOf":"2026-10-26T12:00:00Z"}},history,now)["points"]==0
assert adjustment(game,"home",{"Home Team":declaration},history[:1],now)["points"]==0
draft={"season":2026,"week":8,"games":[game]}
original=dict(game)
out=build(draft,history,{"Home Team":declaration},now)
assert out["games"][0]["originalHomeEdgePoints"]==1.0
assert out["games"][0]["experimentalHomeEdgePoints"]==-0.05
assert game==original
print("Model C-QB shadow guardrails passed")
