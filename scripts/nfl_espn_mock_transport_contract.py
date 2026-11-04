"""Offline-only trusted transport contract. No socket, HTTP client or network calls."""
import hashlib
import json
import re
from urllib.parse import urlsplit,parse_qs
from scripts.nfl_future_history_sync_gate import time,sha
from scripts.nfl_espn_trusted_capture_offline import inspect_response,MAX_BYTES,HOST,PATH

def endpoint(url,season,week):
    try:
        u=urlsplit(url)
        return (u.scheme=="https" and u.hostname==HOST and u.port in (None,443)
                and not u.username and not u.password and u.path==PATH and not u.fragment
                and parse_qs(u.query,keep_blank_values=True)=={"dates":[str(season)],"seasontype":["2"],"week":[str(week)]})
    except (ValueError,TypeError,AttributeError):
        return False

def schedule(manifest,season,week,cutoff):
    problems=[]
    if manifest.get("season")!=season or manifest.get("week")!=week:problems.append("SCHEDULE_SCOPE")
    if manifest.get("provider")!="INDEPENDENT_APPROVED_SCHEDULE":problems.append("SCHEDULE_PROVENANCE")
    if not re.fullmatch(r"[0-9a-f]{64}",str(manifest.get("scheduleSha256",""))):problems.append("SCHEDULE_HASH")
    if manifest.get("scheduleSha256")!=sha(manifest.get("games")):problems.append("SCHEDULE_HASH_MISMATCH")
    try:
        if time(manifest["observedAt"])>time(cutoff):problems.append("SCHEDULE_AFTER_CUTOFF")
    except (ValueError,TypeError,KeyError,AttributeError):problems.append("SCHEDULE_TIMESTAMP")
    games=manifest.get("games")
    if not isinstance(games,list) or not games: return ["EMPTY_SCHEDULE"]+problems,[]
    ids=[]
    for g in games:
        if not isinstance(g,dict) or not re.fullmatch(r"[0-9]+",str(g.get("id",""))):
            problems.append("SCHEDULE_ID");continue
        ids.append(str(g["id"]))
        try:
            if time(g["kickoff"])>time(cutoff):problems.append("SCHEDULE_GAME_AFTER_CUTOFF")
        except (ValueError,TypeError,KeyError,AttributeError):problems.append("SCHEDULE_GAME_TIMESTAMP")
    if len(ids)!=len(games) or len(ids)!=len(set(ids)):problems.append("SCHEDULE_DUPLICATE")
    return sorted(set(problems)),ids

def evaluate(response,manifest,season,week,cutoff):
    """response is a mocked capture envelope, never retrieved by this module."""
    failures,ids=schedule(manifest,season,week,cutoff)
    url=response.get("url","")
    if not endpoint(url,season,week):failures.append("UNTRUSTED_URL")
    if response.get("tlsVerified") is not True or response.get("hostnameVerified") is not True:
        failures.append("TLS_NOT_VERIFIED")
    if response.get("redirectCount")!=0 or response.get("status")!=200:
        failures.append("REDIRECT_OR_HTTP_STATUS")
    if response.get("timeoutSeconds",999)>10 or response.get("timeoutSeconds",0)<=0:
        failures.append("TIMEOUT_POLICY")
    raw=response.get("raw")
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:failures.append("RESPONSE_SIZE")
    if response.get("contentLength") is not None and response.get("contentLength")!=len(raw if isinstance(raw,bytes) else b""):
        failures.append("CONTENT_LENGTH_MISMATCH")
    try:
        start=time(response["startedAt"]);end=time(response["completedAt"])
        if start>end or end>time(cutoff) or (end-start).total_seconds()>10:failures.append("CAPTURE_TIME_INVALID")
    except (ValueError,KeyError,TypeError,AttributeError):
        failures.append("CAPTURE_TIME_INVALID")
    if failures:
        return {"status":"BLOCKED","failures":sorted(set(failures)),"promotionAuthorized":False,"liveRequestMade":False}
    checked=inspect_response(url,raw,response["completedAt"],cutoff,season,week,ids)
    return {"status":"OFFLINE_TRANSPORT_VALIDATED" if checked["status"]=="CAPTURE_VALIDATED_OFFLINE" else "BLOCKED",
            "failures":checked["failures"],"promotionAuthorized":False,"liveRequestMade":False,
            "rawResponseSha256":hashlib.sha256(raw).hexdigest(),
            "scheduleSha256":manifest["scheduleSha256"],"expectedGameIds":ids}
