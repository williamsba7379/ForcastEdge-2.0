"""Isolated A/B historical ESPN input capture. Does not write production predictions.

observedFinalAt is the timestamp *this collector observed* ESPN's completed flag,
NOT an asserted official game-finalization time. Only fresh first-observation records
may be used to establish availability. Never backdate from a later retrieval.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
from scripts.nfl_ab_strict_replay import canonical
from scripts.nfl_ab_archive_adapter import parse_time

BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def capture(fetch,season,cutoff,observed_at):
    cutoff=parse_time(cutoff)
    seen=parse_time(observed_at)
    if seen>cutoff:
        raise ValueError("CAPTURE_AFTER_CUTOFF")
    observations=[]
    ids=set()
    for week in range(1,19):
        url=BASE+"?"+urllib.parse.urlencode({"dates":season,"seasontype":2,"week":week})
        response=fetch(url)
        payload=response["payload"] if isinstance(response,dict) and "payload" in response else response
        response_hash=response.get("responseSha256") if isinstance(response,dict) else None
        if not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
            raise ValueError("INVALID_ESPN_SCOREBOARD")
        for event in payload["events"]:
            if not event.get("status",{}).get("type",{}).get("completed") is True:
                continue
            comps=event.get("competitions",[])
            if len(comps)!=1:
                raise ValueError("INVALID_COMPETITION")
            competitors=comps[0].get("competitors",[])
            home=next((x for x in competitors if x.get("homeAway")=="home"),None)
            away=next((x for x in competitors if x.get("homeAway")=="away"),None)
            if not home or not away:
                raise ValueError("MISSING_TEAM")
            game={"id":str(event["id"]),"date":event["date"],"season":season,
                  "home":home["team"]["displayName"],"away":away["team"]["displayName"],
                  "homeScore":int(home["score"]),"awayScore":int(away["score"]),"completed":True}
            if parse_time(game["date"])>=seen:
                raise ValueError("FUTURE_GAME_MARKED_FINAL")
            if game["id"] in ids:
                raise ValueError("DUPLICATE_ESPN_ID")
            ids.add(game["id"])
            observations.append({"game":game,"sourceUrl":url,"retrievedAt":observed_at,
                 "observedFinalAt":observed_at,"finalObservationType":"FIRST_OBSERVED_BY_COLLECTOR",
                 "sha256":hashlib.sha256(canonical(game)).hexdigest(),
                 "responseSha256":response_hash})
    observations.sort(key=lambda x:(x["game"]["date"],x["game"]["id"]))
    return {"schemaVersion":1,"season":season,"capturedAt":observed_at,
            "cutoff":cutoff.isoformat(),"observationCaveat":"Final first observed at capture; not official final timestamp",
            "observations":observations}

def fetch_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-AB-audit/1.0"})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=200:raise ValueError("ESPN_HTTP_FAILURE")
        body=response.read(8_000_001)
        if len(body)>8_000_000:raise ValueError("ESPN_RESPONSE_TOO_LARGE")
        return {"payload":json.loads(body),"responseSha256":hashlib.sha256(body).hexdigest()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--season",type=int,required=True)
    p.add_argument("--cutoff",required=True,help="UTC or offset-aware ISO timestamp")
    p.add_argument("--output",type=pathlib.Path,required=True)
    args=p.parse_args()
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    result=capture(fetch_json,args.season,args.cutoff,now)
    if args.output.exists():raise ValueError("REFUSE_OVERWRITE_CAPTURE")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("Captured",len(result["observations"]),"observed finals in",args.output)
if __name__=="__main__":main()
