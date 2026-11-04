#!/usr/bin/env python3
"""Read-only historical synchronization/provenance audit. No writes or model execution."""
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from scripts.nfl_week9_history_freshness_gate import from_commit, EVIDENCE_COMMIT, FROZEN_PATH, HISTORY_PATH

SOURCE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=8"

def timestamp(s):
    value=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    if value.tzinfo is None: raise ValueError("timestamp missing timezone")
    return value

def validate(report, history, frozen, evidence_commit=EVIDENCE_COMMIT):
    failures=[]
    freeze=timestamp(frozen["frozenAt"])
    rows=report.get("results",[])
    if (report.get("season"),report.get("week"),report.get("status"),report.get("gamesCompleted"),report.get("gamesRemaining"),len(rows)) != (2026,8,"COMPLETE",14,0,14):
        failures.append("INCOMPLETE_SOURCE_REPORT")
    counts=Counter(str(g.get("gameId")) for g in rows)
    if len(counts)!=14 or any(n!=1 for n in counts.values()):
        failures.append("DUPLICATE_SOURCE_IDS")
    all_history=history.get("games",[])
    historical_counts=Counter((g.get("season"),str(g.get("id"))) for g in all_history)
    if any(n>1 for n in historical_counts.values()):
        failures.append("DUPLICATE_HISTORY_IDS")
    history_by_id={(g.get("season"),str(g.get("id"))):g for g in all_history}
    missing=[]; conflicts=[]; source_errors=[]; cutoff_errors=[]
    for g in rows:
        gid=str(g.get("gameId"))
        try:
            if timestamp(g["date"])>=freeze: cutoff_errors.append(gid)
        except (ValueError,TypeError,KeyError): cutoff_errors.append(gid)
        if g.get("scoreSource")!=SOURCE: source_errors.append(gid)
        if not isinstance(g.get("homeScore"),int) or not isinstance(g.get("awayScore"),int) or min(g.get("homeScore",-1),g.get("awayScore",-1))<0:
            conflicts.append(gid); continue
        winner=g.get("home") if g["homeScore"]>g["awayScore"] else g.get("away") if g["awayScore"]>g["homeScore"] else None
        if winner!=g.get("winner"): conflicts.append(gid)
        item=history_by_id.get((2026,gid))
        if item is None: missing.append(gid)
        elif any(item.get(k)!=g.get(k) for k in ("home","away","homeScore","awayScore","winner","date")) or item.get("week")!=8:
            conflicts.append(gid)
    if missing: failures.append("MISSING_HISTORY_GAMES")
    if conflicts: failures.append("CONFLICTING_RESULTS")
    if source_errors: failures.append("INVALID_SCORE_SOURCE")
    if cutoff_errors: failures.append("INVALID_RESULT_CUTOFF")
    return {"status":"BLOCKED" if failures else "CONSISTENT_NOT_PROMOTABLE",
            "promotionAuthorized":False,"evidenceCommit":evidence_commit,
            "week9FrozenAt":frozen["frozenAt"],"archivedFinals":len(rows),
            "historyMatches":len(rows)-len(set(missing))-len(set(conflicts)),
            "missingGameIds":sorted(set(missing)),"conflictingGameIds":sorted(set(conflicts)),
            "invalidSourceIds":sorted(set(source_errors)),"invalidCutoffIds":sorted(set(cutoff_errors)),
            "failures":failures,"originalHttpRetrievalTimes":"NOT_PRESERVED",
            "observedFinalTimes":"NOT_PRESERVED",
            "sourceProvenance":"ARCHIVED_ESPN_URL_AND_PRE_FREEZE_GIT_COMMIT_NOT_RAW_HTTP_HASH"}

if __name__=="__main__":
    report=from_commit()
    history=json.loads(Path(HISTORY_PATH).read_text())
    frozen=json.loads(Path(FROZEN_PATH).read_text())
    result=validate(report,history,frozen)
    print(json.dumps(result,indent=2))
    assert result["status"]=="BLOCKED" and len(result["missingGameIds"])==14 and not result["conflictingGameIds"],"Unexpected history state; fail closed"
