#!/usr/bin/env python3
"""Isolated read-only official NFL QB evidence intake; never promotes starters."""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import ipaddress

# Exact host allowlist only. Team sites must be explicitly reviewed and added later.
ALLOWED_HOSTS=frozenset({"nfl.com","www.nfl.com"})
POSITIVE="CONFIRMED_STARTER"
NEGATIVE=frozenset({"RULED_OUT","INACTIVE","REPLACED"})
def parse_time(value):
    if not isinstance(value,str):raise ValueError("timestamp required")
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("timezone required")
    return t.astimezone(timezone.utc)
def official_url(value):
    if not isinstance(value,str):return False
    try:
        p=urlsplit(value)
        if p.scheme!="https" or p.username or p.password or p.port not in (None,443) or p.fragment:
            return False
        host=(p.hostname or "").lower().rstrip(".")
        if host not in ALLOWED_HOSTS or not p.path.startswith("/") or p.path=="/":return False
        if any(ord(c)<32 for c in value) or "\\" in value:return False
        return True
    except ValueError:return False
def review(game,candidate,records):
    """Evidence is review-only, even when validated; no network requests or writes."""
    try:
        kickoff=parse_time(game["kickoff"])
        cutoff=parse_time(game["featureCutoff"])
        if cutoff>kickoff or not game.get("gameId") or game.get("teamId")==game.get("opponentId"):
            return "INVALID_GAME"
        if not candidate or candidate.get("verification")!="DEPTH_CHART_CANDIDATE_ONLY":
            return "NO_CANDIDATE"
        if candidate.get("teamId")!=game["teamId"] or not candidate.get("athleteId"):
            return "NO_CANDIDATE"
        if not isinstance(records,list) or not records:return "NO_OFFICIAL_EVIDENCE"
        positive=False
        for record in records:
            if not isinstance(record,dict):return "INVALID_RECORD"
            if record.get("sourceType")!="NFL_OFFICIAL":return "SOURCE_NOT_ALLOWLISTED"
            if not official_url(record.get("sourceUrl")):return "INVALID_OFFICIAL_URL"
            if record.get("gameId")!=game["gameId"] or record.get("teamId")!=game["teamId"] or record.get("opponentId")!=game["opponentId"]:
                return "GAME_MISMATCH"
            if record.get("athleteId")!=candidate["athleteId"]:return "CONFLICTING_QB_IDENTITY"
            published=parse_time(record["publishedAt"])
            observed=parse_time(record["observedAt"])
            if published>observed or observed>cutoff or published>cutoff:return "FUTURE_OR_POST_CUTOFF"
            if published<kickoff-timedelta(days=7):return "STALE_EVIDENCE"
            # A URL alone is never proof that the article exists or contains the claim.
            if not record.get("reviewedBy") or record.get("reviewStatus")!="MANUALLY_VERIFIED" or not record.get("sourceExcerpt") or not record.get("retrievalDigest"):
                return "UNVERIFIED_CONTENT"
            status=record.get("status")
            if status in NEGATIVE:return "OFFICIAL_NEGATIVE_STATUS"
            if status!=POSITIVE:return "UNSUPPORTED_STATUS"
            positive=True
        return "MANUAL_REVIEW_ONLY_NO_AUTOMATIC_PROMOTION" if positive else "NO_OFFICIAL_EVIDENCE"
    except (KeyError,TypeError,ValueError,OverflowError):
        return "INVALID_RECORD"

def fixtures():
    game={"gameId":"g1","teamId":"6","opponentId":"9","kickoff":"2026-11-05T20:15:00-05:00","featureCutoff":"2026-11-05T18:00:00-05:00"}
    qb={"teamId":"6","athleteId":"123","verification":"DEPTH_CHART_CANDIDATE_ONLY"}
    e={"sourceType":"NFL_OFFICIAL","sourceUrl":"https://www.nfl.com/news/example","gameId":"g1","teamId":"6","opponentId":"9","athleteId":"123","publishedAt":"2026-11-05T16:00:00-05:00","observedAt":"2026-11-05T17:00:00-05:00","reviewedBy":"reviewer","reviewStatus":"MANUALLY_VERIFIED","sourceExcerpt":"fixture starter confirmation","retrievalDigest":"fixture-sha256","status":"CONFIRMED_STARTER"}
    def check(expected,**kw):
        actual=review(game,qb,[dict(e,**kw)])
        assert actual==expected,(expected,actual)
    check("MANUAL_REVIEW_ONLY_NO_AUTOMATIC_PROMOTION")
    for bad in ("http://www.nfl.com/news/x","https://nfl.com.evil.test/news/x","https://evil.test/nfl.com/news/x","https://user@nfl.com/news/x","https://nfl.com:8443/news/x","https://nfl.com/","https://nfl.com\\@evil.test/news/x"):
        check("INVALID_OFFICIAL_URL",sourceUrl=bad)
    check("UNVERIFIED_CONTENT",reviewStatus="PENDING")
    check("UNVERIFIED_CONTENT",sourceExcerpt="")
    check("UNVERIFIED_CONTENT",retrievalDigest="")
    check("GAME_MISMATCH",gameId="g2")
    check("GAME_MISMATCH",opponentId="8")
    check("CONFLICTING_QB_IDENTITY",athleteId="456")
    check("STALE_EVIDENCE",publishedAt="2026-10-20T16:00:00-04:00")
    check("FUTURE_OR_POST_CUTOFF",publishedAt="2026-11-05T19:00:00-05:00")
    check("OFFICIAL_NEGATIVE_STATUS",status="INACTIVE")
    check("SOURCE_NOT_ALLOWLISTED",sourceType="TEAM_OFFICIAL")
    check("INVALID_RECORD",publishedAt="not-a-time")
    assert review(game,qb,[e,dict(e,status="RULED_OUT")])=="OFFICIAL_NEGATIVE_STATUS"
    assert review(game,qb,[])=="NO_OFFICIAL_EVIDENCE"
    print("PASS: strict official URL, human review, game matching, timestamps, conflicts, fail-closed and no promotion")
if __name__=="__main__":
    fixtures()
    print("READ_ONLY: no source fetching, no starter promotion, no model or snapshot writes")
