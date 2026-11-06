"""Research-only raw NFL schedule capture and auditable normalization.

No automatic publication or retroactive freeze. A reviewer supplies normalized
games only after examining the captured official NFL HTML; each game must have
a verbatim matching source snippet. This is not a live HTML parser.
"""
import base64
import datetime as dt
import hashlib
import json
import urllib.parse
import urllib.request
from scripts.nfl_ab_archive_adapter import parse_time

MAX_BYTES=8_000_000

def official_url(season,week):
    if not isinstance(season,int) or not 2000<=season<=2100 or not isinstance(week,int) or not 1<=week<=18:
        raise ValueError("INVALID_SEASON_WEEK")
    return "https://www.nfl.com/schedules/%d/by-week/week-%d"%(season,week)

def fetch_official_html(season,week,cutoff):
    url=official_url(season,week)
    request=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-research-schedule-audit/1.0","Accept":"text/html"})
    with urllib.request.urlopen(request,timeout=30) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError("UNVERIFIED_OFFICIAL_HTTP_RESPONSE")
        if "html" not in response.headers.get("Content-Type","").lower():
            raise ValueError("OFFICIAL_RESPONSE_NOT_HTML")
        raw=response.read(MAX_BYTES+1)
        retrieved=dt.datetime.now(dt.timezone.utc).isoformat()
    if len(raw)>MAX_BYTES or not raw:
        raise ValueError("INVALID_OFFICIAL_RESPONSE_SIZE")
    if parse_time(retrieved)>parse_time(cutoff):
        raise ValueError("OFFICIAL_RESPONSE_AFTER_CUTOFF")
    return {"schemaVersion":1,"kind":"RAW_NFL_HTML_CAPTURE",
            "sourceUrl":url,"retrievedAt":retrieved,
            "responseSha256":hashlib.sha256(raw).hexdigest(),
            "rawBodyBase64":base64.b64encode(raw).decode("ascii"),
            "normalized":False,"publishable":False}

def verify_reviewed_normalization(capture, reviewed_games, cutoff):
    if not isinstance(capture,dict) or capture.get("kind")!="RAW_NFL_HTML_CAPTURE":
        raise ValueError("MISSING_OFFICIAL_RAW_CAPTURE")
    url=capture.get("sourceUrl")
    parsed=urllib.parse.urlsplit(url or "")
    if parsed.scheme!="https" or parsed.hostname!="www.nfl.com" or not parsed.path.startswith("/schedules/") or parsed.query or parsed.fragment:
        raise ValueError("UNTRUSTED_OFFICIAL_URL")
    if parse_time(capture["retrievedAt"])>parse_time(cutoff):
        raise ValueError("OFFICIAL_RESPONSE_AFTER_CUTOFF")
    raw=base64.b64decode(capture["rawBodyBase64"],validate=True)
    if hashlib.sha256(raw).hexdigest()!=capture.get("responseSha256"):
        raise ValueError("OFFICIAL_RAW_HASH_MISMATCH")
    page=raw.decode("utf-8",errors="strict")
    if not isinstance(reviewed_games,list) or not reviewed_games:
        raise ValueError("MISSING_REVIEWED_GAMES")
    keys=set()
    for game in reviewed_games:
        if not all(isinstance(game.get(k),str) and game[k] for k in ("date","home","away","sourceSnippet")):
            raise ValueError("INCOMPLETE_REVIEWED_GAME")
        parse_time(game["date"])
        if game["sourceSnippet"] not in page:
            raise ValueError("REVIEW_SNIPPET_NOT_IN_RAW_HTML")
        key=(game["date"],game["home"],game["away"])
        if key in keys:
            raise ValueError("DUPLICATE_REVIEWED_GAME")
        keys.add(key)
    return {"schemaVersion":1,"kind":"REVIEWED_NFL_SCHEDULE_MANIFEST",
            "sourceUrl":url,"retrievedAt":capture["retrievedAt"],
            "responseSha256":capture["responseSha256"],
            "rawBodyBase64":capture["rawBodyBase64"],
            "games":[{k:g[k] for k in ("date","home","away")} for g in reviewed_games],
            "normalizationMethod":"HUMAN_REVIEW_WITH_VERBATIM_RAW_HTML_SNIPPETS",
            "reviewEvidence":[g["sourceSnippet"] for g in reviewed_games],
            "publishable":False}
