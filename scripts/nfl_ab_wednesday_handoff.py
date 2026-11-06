"""Read-only Wednesday A/B handoff. No freezing, publication, betting or writes.

Consumes a complete, verified pre-cutoff ESPN v2 snapshot and an independently
supplied expected schedule. Research-only output is NOT an official frozen card.
"""
import hashlib
from scripts.nfl_ab_strict_replay import canonical
from scripts.nfl_ab_full_slate_audit import audit
from scripts.nfl_ab_archive_adapter import parse_time

def build_ab_wednesday_handoff(snapshot, fixtures, cutoff, expected_schedule):
    if not isinstance(expected_schedule,list) or not expected_schedule:
        raise ValueError("MISSING_INDEPENDENT_SCHEDULE")
    expected_ids=[]
    expected_by_id={}
    for g in expected_schedule:
        ident=str(g["id"])
        if not ident or ident in expected_by_id:
            raise ValueError("DUPLICATE_OR_EMPTY_EXPECTED_ID")
        if not all(isinstance(g.get(k),str) and g[k] for k in ("date","home","away")):
            raise ValueError("INVALID_EXPECTED_MATCHUP")
        if parse_time(g["date"])<=parse_time(cutoff):
            raise ValueError("EXPECTED_GAME_NOT_FUTURE")
        expected_ids.append(ident)
        expected_by_id[ident]=g
    if len(expected_ids)!=len(fixtures):
        raise ValueError("SCHEDULE_COVERAGE_MISMATCH")
    for g in fixtures:
        ident=str(g["id"])
        source=expected_by_id.get(ident)
        if source is None or any(g.get(k)!=source.get(k) for k in ("date","home","away","season")):
            raise ValueError("SCHEDULE_IDENTITY_MISMATCH")
    result=audit(snapshot,fixtures,cutoff,expected_ids)
    if result["coverage"]!=len(expected_ids):
        raise ValueError("AB_INCOMPLETE_SLATE")
    rows=[]
    for g in result["games"]:
        if g["A"] not in (g["home"],g["away"]) or g["B"] not in (g["home"],g["away"]):
            raise ValueError("INVALID_AB_WINNER")
        original=expected_by_id[g["id"]]
        rows.append({"id":g["id"],"date":original["date"],
                     "home":g["home"],"away":g["away"],
                     "picks":{"A":g["A"],"B":g["B"]},
                     "researchEdges":{"A_home_edge":g["A_home_edge"],
                                      "B_home_edge":g["B_home_edge"]},
                     "source_status":"RESEARCH_ONLY_NO_BET",
                     "verifiedHistoryGames":{"home":g["home_history_games"],
                                             "away":g["away_history_games"]}})
    return {"schemaVersion":1,"kind":"AB_WEDNESDAY_RESEARCH_HANDOFF",
            "officialFrozen":False,"publishable":False,
            "cutoff":result["cutoff"],"snapshotSha256":hashlib.sha256(canonical(snapshot)).hexdigest(),
            "scheduleSha256":hashlib.sha256(canonical(expected_schedule)).hexdigest(),
            "expectedCount":len(expected_ids),"games":rows,
            "missingFields":["C","C-QB","projectedScore","spread","total","confidence"],
            "noBet":True,"readOnly":True}

def build_verified_wednesday_handoff(snapshot, fixtures, cutoff, expected_schedule, schedule_evidence):
    """Strict entry point requiring independently hashed, on-time ESPN schedule."""
    from scripts.nfl_ab_schedule_provenance import verify_schedule_evidence
    from scripts.nfl_ab_archive_adapter import parse_time
    if parse_time(snapshot["capturedAt"])>parse_time(cutoff):
        raise ValueError("CAPTURE_COMPLETED_AFTER_CUTOFF")
    if parse_time(snapshot["cutoff"])!=parse_time(cutoff):
        raise ValueError("CAPTURE_CUTOFF_MISMATCH")
    times=[parse_time(r["retrievedAt"]) for r in snapshot["responses"]]
    if times and parse_time(snapshot["capturedAt"])<max(times):
        raise ValueError("CAPTURE_BEFORE_LAST_RESPONSE")
    provenance=verify_schedule_evidence(schedule_evidence,cutoff,expected_schedule)
    result=build_ab_wednesday_handoff(snapshot,fixtures,cutoff,expected_schedule)
    result["scheduleProvenance"]=provenance
    result["captureCompletedAt"]=snapshot["capturedAt"]
    return result

def build_two_source_wednesday_handoff(snapshot, fixtures, cutoff, expected_schedule,
                                       espn_evidence, official_evidence):
    """Research-only A/B handoff; fail closed unless both schedule sources agree."""
    from scripts.nfl_ab_independent_schedule import verify_independent_schedule
    provenance=verify_independent_schedule(espn_evidence,official_evidence,cutoff,expected_schedule)
    result=build_verified_wednesday_handoff(snapshot,fixtures,cutoff,expected_schedule,espn_evidence)
    result["scheduleProvenance"]=provenance
    return result
