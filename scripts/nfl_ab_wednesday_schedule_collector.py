"""Isolated, read-only Wednesday ESPN schedule collection.

No cron, prediction freeze, production writes, or retrospective evidence.
Caller chooses season/week and supplies a cutoff. Response timestamp is taken
immediately after the actual HTTP read, not shared with historical responses.
"""
import argparse
import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_schedule_provenance import ESPN_SCHEDULE_URL, capture_schedule_response, verify_schedule_evidence

MAX_BYTES=8_000_000

def fetch_schedule(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-AB-schedule-audit/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=200:
            raise ValueError("SCHEDULE_HTTP_FAILURE")
        if response.geturl()!=url:
            raise ValueError("SCHEDULE_REDIRECT_REJECTED")
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("SCHEDULE_RESPONSE_TOO_LARGE")
        retrieved=dt.datetime.now(dt.timezone.utc).isoformat()
    return raw,retrieved

def collect_wednesday_schedule(season,week,cutoff,fetch=fetch_schedule):
    if not isinstance(season,int) or season<2000 or not isinstance(week,int) or not 1<=week<=18:
        raise ValueError("INVALID_SEASON_WEEK")
    cutoff_time=parse_time(cutoff)
    url=ESPN_SCHEDULE_URL+"?"+urllib.parse.urlencode({"dates":season,"seasontype":2,"week":week})
    raw,retrieved_at=fetch(url)
    if parse_time(retrieved_at)>cutoff_time:
        raise ValueError("SCHEDULE_AFTER_CUTOFF")
    proof=capture_schedule_response(raw,retrieved_at,url)
    payload=json.loads(raw)
    expected=[]
    for e in payload["events"]:
        try:
            competitors=e["competitions"][0]["competitors"]
            home=next(x for x in competitors if x["homeAway"]=="home")
            away=next(x for x in competitors if x["homeAway"]=="away")
            expected.append({"id":str(e["id"]),"date":e["date"],
                "home":home["team"]["displayName"],"away":away["team"]["displayName"],
                "season":season})
        except (KeyError,IndexError,StopIteration,TypeError) as exc:
            raise ValueError("INVALID_SCHEDULE_EVENT") from exc
    if not expected:
        raise ValueError("EMPTY_WEEK_SCHEDULE")
    verify_schedule_evidence(proof,cutoff_time.isoformat(),expected)
    return {"schemaVersion":1,"kind":"ISOLATED_WEDNESDAY_SCHEDULE_EVIDENCE",
            "season":season,"week":week,"cutoff":cutoff_time.isoformat(),
            "expectedSchedule":expected,"scheduleEvidence":proof,
            "readOnly":True,"officialFrozen":False,"publishable":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--season",type=int,required=True)
    p.add_argument("--week",type=int,required=True)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--output",type=pathlib.Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError("REFUSE_OVERWRITE_SCHEDULE_EVIDENCE")
    result=collect_wednesday_schedule(args.season,args.week,args.cutoff)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("Read-only schedule evidence:",len(result["expectedSchedule"]),"games")
if __name__=="__main__":
    main()
