"""Offline-only ESPN capture validation. Never makes HTTP calls or writes files."""
import hashlib
import json
from datetime import timedelta
from urllib.parse import urlsplit,parse_qs
from scripts.nfl_future_history_sync_gate import time

HOST="site.api.espn.com"
PATH="/apis/site/v2/sports/football/nfl/scoreboard"
MAX_BYTES=2_000_000
def inspect_response(url,raw,retrieved_at,cutoff,season,week,expected_ids):
    failures=[]
    try:
        u=urlsplit(url)
        q=parse_qs(u.query,keep_blank_values=True)
        if u.scheme!="https" or u.hostname!=HOST or u.port not in (None,443) or u.username or u.password or u.path!=PATH or u.fragment or q!={"dates":[str(season)],"seasontype":["2"],"week":[str(week)]}:
            failures.append("UNTRUSTED_ESPN_URL")
    except (ValueError,TypeError,AttributeError):
        failures.append("UNTRUSTED_ESPN_URL")
    try:
        capture=time(retrieved_at);deadline=time(cutoff)
        if capture>deadline or capture>deadline+timedelta(0):failures.append("LATE_RETRIEVAL")
    except (ValueError,TypeError,AttributeError):
        failures.append("INVALID_CAPTURE_TIME")
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        failures.append("INVALID_RAW_RESPONSE")
        raw=b""
    digest=hashlib.sha256(raw).hexdigest()
    try:
        data=json.loads(raw)
        events=data["events"]
        ids=[str(g["id"]) for g in events]
        expected=[str(i) for i in expected_ids]
        if not expected or len(set(expected))!=len(expected) or len(ids)!=len(set(ids)) or set(ids)!=set(expected):
            failures.append("INCOMPLETE_OR_DUPLICATE_EVENTS")
        results=[]
        for g in events:
            status=g["status"]["type"]
            if status.get("completed") is not True or status.get("name") not in ("STATUS_FINAL","STATUS_FINAL_OVERTIME"):
                failures.append("NOT_FINAL")
            competition=g["competitions"][0]
            competitors=competition["competitors"]
            home=[x for x in competitors if x["homeAway"]=="home"]
            away=[x for x in competitors if x["homeAway"]=="away"]
            if len(home)!=1 or len(away)!=1:raise ValueError("TEAM_SIDES")
            home,away=home[0],away[0]
            hs,ascore=int(home["score"]),int(away["score"])
            if hs<0 or ascore<0 or hs==ascore:raise ValueError("SCORE")
            if not str(home["score"]).isdigit() or not str(away["score"]).isdigit():raise ValueError("SCORE")
            ht,at=home["team"]["displayName"],away["team"]["displayName"]
            if not ht or not at or ht==at:raise ValueError("TEAM")
            if time(g["date"])>=time(cutoff):failures.append("GAME_AFTER_CUTOFF")
            results.append({"gameId":str(g["id"]),"date":g["date"],"home":ht,"away":at,
                            "homeScore":hs,"awayScore":ascore,"winner":ht if hs>ascore else at,"scoreSource":url})
    except (KeyError,ValueError,TypeError,IndexError,AttributeError,UnicodeDecodeError):
        failures.append("MALFORMED_ESPN_RESPONSE")
        results=[]
    return {"status":"CAPTURE_VALIDATED_OFFLINE" if not failures else "BLOCKED",
            "promotionAuthorized":False,"liveCapturePerformed":False,"sourceUrl":url,
            "retrievedAt":retrieved_at,"rawResponseSha256":digest,"byteLength":len(raw),
            "results":results if not failures else [],"failures":sorted(set(failures)),
            "archiveInstruction":"Archive exact raw bytes in an immutable Git commit, then independently verify commit and blob before use"}
