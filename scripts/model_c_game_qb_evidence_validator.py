#!/usr/bin/env python3
"""Read-only, fail-closed game-specific NFL quarterback evidence validator.

Consumes human-reviewed, explicitly game-scoped evidence; never scrapes,
promotes a starter, writes a snapshot, or changes any forecast.
"""
import datetime as dt
import json
import sys

UTC=dt.timezone.utc
OFFICIAL={"NFL_OFFICIAL","TEAM_OFFICIAL"}
POSITIVE={"CONFIRMED_STARTER"}
NEGATIVE={"RULED_OUT","INACTIVE","REPLACED"}
RANK_KEYS=("rank","depth","depthOrder","order","slot")

def timestamp(value):
    if not isinstance(value,str):raise ValueError("missing timestamp")
    parsed=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if parsed.tzinfo is None:raise ValueError("timezone required")
    return parsed.astimezone(UTC)

def explicit_qb1(positions):
    """Extract only uniquely ranked QB1 with stable identity, never list order."""
    if not isinstance(positions,dict):return None,"UNSUPPORTED_POSITIONS"
    qb=positions.get("qb") or positions.get("QB")
    if not isinstance(qb,dict):return None,"NO_QB_POSITION"
    athletes=qb.get("athletes")
    if not isinstance(athletes,list):return None,"NO_QB_ATHLETES"
    ids=[]
    for entry in athletes:
        if not isinstance(entry,dict):continue
        present=[entry[k] for k in RANK_KEYS if k in entry and entry[k] is not None]
        if not present:continue
        if len({str(v) for v in present})!=1:return None,"CONFLICTING_RANK_FIELDS"
        if str(present[0])!="1":continue
        player=entry.get("athlete")
        if not isinstance(player,dict):return None,"UNRESOLVED_QB_IDENTITY"
        ident=player.get("id")
        if not isinstance(ident,(str,int)) or not str(ident).strip():return None,"UNRESOLVED_QB_IDENTITY"
        ids.append(str(ident))
    if len(ids)!=1:return None,"AMBIGUOUS_OR_MISSING_QB1"
    return ids[0],"DEPTH_CHART_CANDIDATE_ONLY"

def validate(game,candidate,evidence,now=None):
    """Fail closed unless independent official positive evidence is game-specific."""
    try:
        now=now or dt.datetime.now(UTC)
        kickoff=timestamp(game["kickoff"])
        cutoff=timestamp(game["featureCutoff"])
        if cutoff>kickoff or now<cutoff:return "INVALID_GAME_TIMING"
        team,opponent=game["teamId"],game["opponentId"]
        if not team or not opponent or team==opponent:return "INVALID_MATCHUP"
        if not candidate or candidate.get("teamId")!=team or not candidate.get("athleteId"):
            return "NO_UNIQUE_QB1_CANDIDATE"
        if candidate.get("verification")!="DEPTH_CHART_CANDIDATE_ONLY":return "INVALID_CANDIDATE_STATUS"
        positives=0
        for item in evidence:
            if not isinstance(item,dict):return "INVALID_EVIDENCE"
            if item.get("sourceType") not in OFFICIAL:return "UNTRUSTED_SOURCE"
            if item.get("teamId")!=team or item.get("opponentId")!=opponent or item.get("gameId")!=game.get("gameId"):
                return "GAME_MISMATCH"
            published=timestamp(item["publishedAt"])
            observed=timestamp(item["observedAt"])
            if published>observed or observed>cutoff or published>cutoff or published>kickoff:
                return "FUTURE_OR_POST_CUTOFF_EVIDENCE"
            if published<kickoff-dt.timedelta(days=7):return "STALE_EVIDENCE"
            if item.get("athleteId")!=candidate["athleteId"]:return "CONFLICTING_QB_IDENTITY"
            status=item.get("status")
            if status in NEGATIVE:return "OFFICIAL_NEGATIVE_STATUS"
            if status not in POSITIVE:return "UNSUPPORTED_OFFICIAL_STATUS"
            if not item.get("sourceUrl") or not item.get("reviewedBy"):return "UNREVIEWED_EVIDENCE"
            positives+=1
        return "OFFICIAL_GAME_SPECIFIC_CONFIRMATION_REVIEW_ONLY" if positives else "NO_OFFICIAL_GAME_SPECIFIC_CONFIRMATION"
    except (KeyError,TypeError,ValueError,OverflowError):
        return "INVALID_OR_MISSING_EVIDENCE"

def fixtures():
    kickoff="2026-11-05T20:15:00-05:00"
    game={"gameId":"fixture-game","teamId":"6","opponentId":"9","kickoff":kickoff,"featureCutoff":"2026-11-05T18:00:00-05:00"}
    candidate={"teamId":"6","athleteId":"123","verification":"DEPTH_CHART_CANDIDATE_ONLY"}
    item={"sourceType":"TEAM_OFFICIAL","teamId":"6","opponentId":"9","gameId":"fixture-game","athleteId":"123","status":"CONFIRMED_STARTER","publishedAt":"2026-11-05T16:00:00-05:00","observedAt":"2026-11-05T17:00:00-05:00","sourceUrl":"https://example.invalid/official","reviewedBy":"fixture-reviewer"}
    now=timestamp("2026-11-05T18:01:00-05:00")
    def check(expected,records,**changes):
        assert validate(game,candidate,[dict(item,**changes)] if records else [],now)==expected
    check("OFFICIAL_GAME_SPECIFIC_CONFIRMATION_REVIEW_ONLY",True)
    check("NO_OFFICIAL_GAME_SPECIFIC_CONFIRMATION",False)
    check("GAME_MISMATCH",True,opponentId="8")
    check("GAME_MISMATCH",True,gameId="other")
    check("UNTRUSTED_SOURCE",True,sourceType="ESPN_DEPTH_CHART")
    check("CONFLICTING_QB_IDENTITY",True,athleteId="999")
    check("OFFICIAL_NEGATIVE_STATUS",True,status="RULED_OUT")
    check("STALE_EVIDENCE",True,publishedAt="2026-10-20T12:00:00-04:00")
    check("FUTURE_OR_POST_CUTOFF_EVIDENCE",True,publishedAt="2026-11-05T19:00:00-05:00")
    check("UNREVIEWED_EVIDENCE",True,reviewedBy="")
    check("INVALID_OR_MISSING_EVIDENCE",True,publishedAt="not-a-date")
    check("UNSUPPORTED_OFFICIAL_STATUS",True,status="QUESTIONABLE")
    assert validate(game,candidate,[item,dict(item,status="INACTIVE")],now)=="OFFICIAL_NEGATIVE_STATUS"
    assert explicit_qb1({"qb":{"athletes":[{"rank":1,"athlete":{"id":"123"}},{"rank":2,"athlete":{"id":"456"}}]}})==("123","DEPTH_CHART_CANDIDATE_ONLY")
    assert explicit_qb1({"qb":{"athletes":[{"athlete":{"id":"123"}}]}})[0] is None
    assert explicit_qb1({"qb":{"athletes":[{"rank":1,"athlete":{"id":"123"}},{"rank":1,"athlete":{"id":"456"}}]}})[0] is None
    assert explicit_qb1({"qb":{"athletes":[{"rank":1,"depth":2,"athlete":{"id":"123"}}]}})[0] is None
    assert explicit_qb1({"qb":{"athletes":[{"rank":1,"athlete":{"$ref":"https://example.invalid/athlete"}}]}})[0] is None
    print("PASS: unique explicit QB1, official game identity, timestamps, conflicts, negative statuses, no list-order inference, review-only")

if __name__=="__main__":
    fixtures()
    if "--live" in sys.argv:
        print("READ_ONLY: no live official-starter promotion; human-reviewed game-specific official evidence required")
