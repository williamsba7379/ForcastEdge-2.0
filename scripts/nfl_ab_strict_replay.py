"""Strict, read-only A/B replay from timestamped, immutable historical observations.

Never fetch current results to pretend they were known at an earlier cutoff.
"""
import datetime as dt
import hashlib
import json
from scripts.nfl_ab_archive_adapter import parse_time

def canonical(row):
    return json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def replay(snapshot, frozen, metric_fn):
    cutoff=parse_time(frozen["frozenAt"])
    records=snapshot.get("observations")
    if not isinstance(records,list):
        raise ValueError("MISSING_OBSERVATION_SNAPSHOT")
    history=[]
    ids=set()
    for obs in records:
        row=obs.get("game")
        if not isinstance(row,dict) or not obs.get("sourceUrl") or not obs.get("retrievedAt") or not obs.get("observedFinalAt") or not obs.get("sha256") or not obs.get("responseSha256"):
            raise ValueError("MISSING_SOURCE_OR_FINALIZATION_PROVENANCE")
        if obs.get("finalObservationType") not in ("FIRST_OBSERVED_BY_COLLECTOR","VERIFIED_SOURCE_FINAL_TIMESTAMP"):\n            raise ValueError("UNVERIFIED_FINAL_OBSERVATION_TYPE")\n        if hashlib.sha256(canonical(row)).hexdigest()!=obs["sha256"]:
            raise ValueError("CONTENT_HASH_MISMATCH")
        observed=parse_time(obs["observedFinalAt"])
        retrieved=parse_time(obs["retrievedAt"])
        game_time=parse_time(row["date"])
        if not (game_time<observed<=retrieved<=cutoff):
            raise ValueError("FUTURE_OR_UNVERIFIED_FINAL_RESULT")
        if row.get("completed") is not True or row.get("homeScore") is None or row.get("awayScore") is None:
            raise ValueError("NOT_VERIFIED_FINAL")
        if row.get("id") in ids:
            raise ValueError("DUPLICATE_HISTORICAL_GAME")
        ids.add(row["id"])
        history.append(row)
    history.sort(key=lambda r:(parse_time(r["date"]),str(r["id"])))
    results=[]
    for game in frozen["games"]:
        if parse_time(game["date"])<=cutoff:
            raise ValueError("FROZEN_AFTER_TARGET_KICKOFF")
        older=[r for r in history if parse_time(r["date"])<cutoff and r.get("season")==frozen["season"]]
        home=metric_fn(older,game["home"]);away=metric_fn(older,game["away"])
        if min(home["games"],away["games"])<2:
            raise ValueError("INSUFFICIENT_VERIFIED_HISTORY")
        def pick(weight):
            edge=(1-weight)*(home["pointDifferential"]-away["pointDifferential"])+weight*(home["recentDifferential"]-away["recentDifferential"])+1.5
            return game["home"] if edge>=0 else game["away"]
        a,b=pick(.3),pick(0)
        if a!=game["baseline30Pick"] or b!=game["experimental0Pick"]:
            raise ValueError("ARCHIVED_AB_REPLAY_MISMATCH "+str(game["id"]))
        results.append({"id":game["id"],"A":a,"B":b})
    return results
