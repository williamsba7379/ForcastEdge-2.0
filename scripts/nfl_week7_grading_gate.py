"""Read-only Week 7 A/B/C grading gate. Never writes or publishes grades.

Historical archive is a candidate score source, NOT independently timestamp-verified.
This gate requires an externally verified Week 7 snapshot before certified grading.
"""
import datetime as dt

def parse(value):
    x=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if x.tzinfo is None: raise ValueError("timezone required")
    return x.astimezone(dt.timezone.utc)

def inspect(ab,c,archive,*,verified_snapshot=False):
    failures=[]
    if ab.get("season")!=2026 or c.get("season")!=2026 or c.get("week")!=7:
        failures.append("SEASON_WEEK_MISMATCH")
    a=ab.get("games",[]); b=c.get("games",[])
    ids_a=[str(g.get("id")) for g in a];ids_c=[str(g.get("id")) for g in b]
    if len(ids_a)!=14 or len(ids_c)!=14 or len(set(ids_a))!=14 or set(ids_a)!=set(ids_c):
        failures.append("FROZEN_MATCHUP_COVERAGE_MISMATCH")
    history=[g for g in archive.get("games",[]) if g.get("season")==2026 and g.get("week")==7]
    ids_h=[str(g.get("id")) for g in history]
    if len(ids_h)!=14 or len(set(ids_h))!=14 or set(ids_a)!=set(ids_h):
        failures.append("HISTORICAL_GAME_ID_COVERAGE_MISMATCH")
    by_c={str(g.get("id")):g for g in b}
    by_h={str(g.get("id")):g for g in history}
    eligible=0
    for g in a:
        key=str(g.get("id"));pilot=by_c.get(key);final=by_h.get(key)
        if not pilot or not final:continue
        if (g.get("week")!=7 or
            any(g.get(k)!=pilot.get(k) or g.get(k)!=final.get(k) for k in ("home","away","date"))):
            failures.append("GAME_ID_TEAM_DATE_MISMATCH:"+key);continue
        try:
            kickoff=parse(g["date"])
            frozen=parse(ab["frozenAt"])
            cday=dt.date.fromisoformat(c["createdAt"])
            if not (frozen<kickoff and cday<kickoff.date()):
                failures.append("NOT_FROZEN_BEFORE_KICKOFF:"+key);continue
        except (ValueError,KeyError,TypeError):
            failures.append("INVALID_FREEZE_TIME:"+key);continue
        if not all(p in (g["home"],g["away"]) for p in
                   (g.get("baseline30Pick"),g.get("experimental0Pick"),pilot.get("pick"))):
            failures.append("INVALID_PICK:"+key);continue
        if (not isinstance(final.get("homeScore"),int) or
            not isinstance(final.get("awayScore"),int) or
            final["homeScore"]==final["awayScore"] or
            final.get("winner")!=(g["home"] if final["homeScore"]>final["awayScore"] else g["away"])):
            failures.append("UNVERIFIED_FINAL_SCORE:"+key);continue
        eligible+=1
    if not verified_snapshot:
        failures.append("INDEPENDENT_FINAL_PROVENANCE_NOT_VERIFIED")
    return {"eligibleCandidates":eligible,"certified":not failures and eligible==14,
            "failures":sorted(set(failures)),"gradesPublished":False}
