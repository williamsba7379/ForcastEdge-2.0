"""Fail-closed read-only full-slate A/B validation from immutable ESPN captures.

Only predicts hypothetical/future fixtures. Never writes a frozen card.
"""
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_strict_replay import canonical
from scripts.nfl_team_strength import team_metrics
import base64
import hashlib
import json

def audit(snapshot, fixtures, cutoff, expected_ids):
    stamp=parse_time(cutoff)
    if snapshot.get("schemaVersion")!=2 or not isinstance(snapshot.get("responses"),list):
        raise ValueError("REQUIRE_V2_RAW_ESPN_CAPTURE")
    if not isinstance(fixtures,list) or not fixtures:
        raise ValueError("EMPTY_SLATE")
    ids=[str(g["id"]) for g in fixtures]
    if len(ids)!=len(set(ids)) or set(ids)!=set(map(str,expected_ids)):
        raise ValueError("SCHEDULE_COVERAGE_MISMATCH")
    responses={}
    for r in snapshot["responses"]:
        if r["id"] in responses:
            raise ValueError("DUPLICATE_RESPONSE_ID")
        body=base64.b64decode(r["rawBodyBase64"],validate=True)
        if hashlib.sha256(body).hexdigest()!=r["responseSha256"]:
            raise ValueError("RAW_ESPN_HASH_MISMATCH")
        payload=json.loads(body)
        if not isinstance(payload.get("events"),list):
            raise ValueError("INVALID_ESPN_EVENTS")
        if parse_time(r["retrievedAt"])>stamp:
            raise ValueError("RESPONSE_AFTER_CUTOFF")
        responses[r["id"]]=(r,payload)
    history=[]
    seen=set()
    for obs in snapshot.get("observations",[]):
        row=obs["game"]
        if row["id"] in seen:
            raise ValueError("DUPLICATE_HISTORICAL_GAME")
        seen.add(row["id"])
        if hashlib.sha256(canonical(row)).hexdigest()!=obs["sha256"]:
            raise ValueError("GAME_HASH_MISMATCH")
        if obs.get("finalObservationType")!="FIRST_OBSERVED_BY_COLLECTOR":
            raise ValueError("UNVERIFIED_FINAL_EVIDENCE")
        r,payload=responses[obs["responseId"]]
        if any(r[k]!=obs[k] for k in ("sourceUrl","retrievedAt","responseSha256")):
            raise ValueError("RESPONSE_LINK_MISMATCH")
        matching=[e for e in payload["events"] if str(e.get("id"))==str(row["id"])]
        if len(matching)!=1 or matching[0].get("status",{}).get("type",{}).get("completed") is not True:
            raise ValueError("RAW_FINAL_NOT_CONFIRMED")
        raw=matching[0]
        try:
            sides=raw["competitions"][0]["competitors"]
            home=next(c for c in sides if c["homeAway"]=="home")
            away=next(c for c in sides if c["homeAway"]=="away")
            if (home["team"]["displayName"]!=row["home"] or
                away["team"]["displayName"]!=row["away"] or
                int(home["score"])!=row["homeScore"] or
                int(away["score"])!=row["awayScore"] or
                parse_time(raw["date"])!=parse_time(row["date"])):
                raise ValueError("RAW_GAME_CONTENT_MISMATCH")
        except (KeyError,IndexError,StopIteration,TypeError) as exc:
            raise ValueError("RAW_GAME_CONTENT_MISMATCH") from exc
        if not (parse_time(row["date"])<parse_time(obs["observedFinalAt"])<=parse_time(obs["retrievedAt"])<=stamp):
            raise ValueError("HISTORICAL_FINAL_AFTER_CUTOFF")
        if row.get("completed") is not True or not isinstance(row.get("homeScore"),int) or not isinstance(row.get("awayScore"),int):
            raise ValueError("INVALID_FINAL_SCORE")
        history.append(row)
    history.sort(key=lambda g:(parse_time(g["date"]),str(g["id"])))
    rows=[]
    for fixture in sorted(fixtures,key=lambda g:(parse_time(g["date"]),str(g["id"]))):
        if parse_time(fixture["date"])<=stamp:
            raise ValueError("TARGET_NOT_FUTURE")
        if fixture["home"]==fixture["away"]:
            raise ValueError("INVALID_MATCHUP")
        prior=[g for g in history if g["season"]==fixture["season"]]
        hm=team_metrics(prior,fixture["home"])
        am=team_metrics(prior,fixture["away"])
        if min(hm["games"],am["games"])<2:
            raise ValueError("INSUFFICIENT_VERIFIED_HISTORY "+str(fixture["id"]))
        delta=hm["pointDifferential"]-am["pointDifferential"]
        recent=hm["recentDifferential"]-am["recentDifferential"]
        a_edge=round(.7*delta+.3*recent+1.5,4)
        b_edge=round(delta+1.5,4)
        rows.append({"id":str(fixture["id"]),"home":fixture["home"],"away":fixture["away"],
                     "A":fixture["home"] if a_edge>=0 else fixture["away"],
                     "B":fixture["home"] if b_edge>=0 else fixture["away"],
                     "A_home_edge":a_edge,"B_home_edge":b_edge,
                     "home_history_games":hm["games"],"away_history_games":am["games"],
                     "status":"RESEARCH_ONLY_NO_BET"})
    return {"status":"OFFLINE_RESEARCH_ONLY","cutoff":stamp.isoformat(),"games":rows,
            "coverage":len(rows),"does_not_freeze_or_publish":True}
