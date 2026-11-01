#!/usr/bin/env python3
"""Read-only, fail-closed NFL QB source review record validation."""
import datetime as dt
import re
from model_c_official_qb_source_intake import official_url

HEX64=re.compile(r"^[a-f0-9]{64}$")
def when(value):
    if not isinstance(value,str):raise ValueError("timestamp")
    t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("timezone")
    return t.astimezone(dt.timezone.utc)

def review(game,candidate,records):
    try:
        if not isinstance(records,list) or not records:return "NO_EVIDENCE"
        kickoff=when(game["kickoff"]);cutoff=when(game["featureCutoff"])
        if cutoff>kickoff or not game.get("gameId") or not game.get("teamId") or not game.get("opponentId") or game["teamId"]==game["opponentId"]:
            return "INVALID_GAME"
        if candidate.get("teamId")!=game["teamId"] or not candidate.get("athleteId") or candidate.get("verification")!="DEPTH_CHART_CANDIDATE_ONLY":
            return "INVALID_CANDIDATE"
        positives=0
        for e in records:
            if not isinstance(e,dict):return "INVALID_RECORD"
            if e.get("gameId")!=game["gameId"] or e.get("teamId")!=game["teamId"] or e.get("opponentId")!=game["opponentId"]:
                return "GAME_MISMATCH"
            if e.get("athleteId")!=candidate["athleteId"]:return "QB_IDENTITY_CONFLICT"
            if e.get("sourceType")!="NFL_OFFICIAL" or not official_url(e.get("sourceUrl")):
                return "UNTRUSTED_PROVENANCE"
            if not isinstance(e.get("sha256"),str) or not HEX64.fullmatch(e["sha256"]):
                return "INVALID_RETRIEVAL_DIGEST"
            if e.get("retrievalStatus")!="FETCHED_REVIEW_REQUIRED" or not e.get("reviewedBy") or e.get("reviewStatus")!="MANUALLY_VERIFIED":
                return "UNVERIFIED_SOURCE_CONTENT"
            if not e.get("sourceExcerpt") or not e.get("reviewedClaimMatchesSource"):
                return "UNVERIFIED_SOURCE_CONTENT"
            published=when(e["publishedAt"]);observed=when(e["observedAt"]);reviewed=when(e["reviewedAt"])
            if published>observed or observed>reviewed or reviewed>cutoff:return "FUTURE_OR_POST_CUTOFF"
            if published<kickoff-dt.timedelta(days=7):return "STALE_EVIDENCE"
            if e.get("status") in ("INACTIVE","RULED_OUT","REPLACED"):return "NEGATIVE_OFFICIAL_EVIDENCE"
            if e.get("status")!="CONFIRMED_STARTER":return "UNSUPPORTED_CLAIM"
            positives+=1
        return "HUMAN_REVIEWED_ONLY_NO_PROMOTION" if positives else "NO_EVIDENCE"
    except (KeyError,ValueError,TypeError,OverflowError,AttributeError):
        return "INVALID_RECORD"

def fixtures():
    g={"gameId":"fixture","teamId":"6","opponentId":"9","kickoff":"2026-11-05T20:15:00-05:00","featureCutoff":"2026-11-05T18:00:00-05:00"}
    c={"teamId":"6","athleteId":"123","verification":"DEPTH_CHART_CANDIDATE_ONLY"}
    e={"gameId":"fixture","teamId":"6","opponentId":"9","athleteId":"123","sourceType":"NFL_OFFICIAL","sourceUrl":"https://www.nfl.com/news/fixture","sha256":"a"*64,"retrievalStatus":"FETCHED_REVIEW_REQUIRED","reviewedBy":"fixture-reviewer","reviewStatus":"MANUALLY_VERIFIED","sourceExcerpt":"fixture-only claim","reviewedClaimMatchesSource":True,"publishedAt":"2026-11-05T16:00:00-05:00","observedAt":"2026-11-05T16:10:00-05:00","reviewedAt":"2026-11-05T17:00:00-05:00","status":"CONFIRMED_STARTER"}
    def check(expected,**updates):
        got=review(g,c,[dict(e,**updates)])
        assert got==expected,(expected,got)
    check("HUMAN_REVIEWED_ONLY_NO_PROMOTION")
    check("GAME_MISMATCH",opponentId="8")
    check("QB_IDENTITY_CONFLICT",athleteId="999")
    check("UNTRUSTED_PROVENANCE",sourceUrl="https://nfl.com.evil.test/news/fixture")
    check("INVALID_RETRIEVAL_DIGEST",sha256="fakehash")
    check("UNVERIFIED_SOURCE_CONTENT",reviewStatus="PENDING")
    check("UNVERIFIED_SOURCE_CONTENT",reviewedClaimMatchesSource=False)
    check("UNVERIFIED_SOURCE_CONTENT",retrievalStatus="FETCH_FAILED_CLOSED")
    check("STALE_EVIDENCE",publishedAt="2026-10-20T16:00:00-04:00")
    check("FUTURE_OR_POST_CUTOFF",reviewedAt="2026-11-05T19:00:00-05:00")
    check("NEGATIVE_OFFICIAL_EVIDENCE",status="RULED_OUT")
    check("INVALID_RECORD",publishedAt="bad")
    assert review(g,c,[e,dict(e,status="INACTIVE")])=="NEGATIVE_OFFICIAL_EVIDENCE"
    assert review(g,c,[])=="NO_EVIDENCE"
    print("PASS: source provenance, 64-hex digest, manual review, game/QB matching, cutoff, stale/conflicts, no promotion")
if __name__=="__main__":
    fixtures()
    print("READ_ONLY: offline review fixtures; no file writes, no prediction changes, no starter promotion")
