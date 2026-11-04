"""Fail-closed future-week history synchronization gate; research-only, no writes."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime,timezone

def time(value):
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None: raise ValueError("NAIVE_TIMESTAMP")
    return t

def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def gate(history,report,manifest,cutoff,expected_ids):
    """All evidence is caller-supplied; never fetch live results or modify files."""
    failures=[]
    original=sha(history)
    candidate=deepcopy(history)
    try:
        deadline=time(cutoff)
        archived=time(manifest["archivedAt"])
        retrieved=time(manifest["retrievedAt"])
        if archived>deadline or retrieved>archived: failures.append("INVALID_ARCHIVE_CUTOFF")
    except (KeyError,ValueError,TypeError,AttributeError):
        failures.append("INVALID_ARCHIVE_CUTOFF")
    if manifest.get("provider")!="ESPN" or manifest.get("sourceUrl")!=report.get("scoreSource") or not str(manifest.get("sourceUrl","")).startswith("https://site.api.espn.com/"):
        failures.append("INVALID_PROVENANCE")
    if not isinstance(manifest.get("rawResponseSha256"),str) or len(manifest["rawResponseSha256"])!=64 or any(c not in "0123456789abcdef" for c in manifest["rawResponseSha256"]):
        failures.append("MISSING_RAW_RESPONSE_HASH")
    if not isinstance(manifest.get("archiveCommit"),str) or len(manifest["archiveCommit"])!=40 or any(c not in "0123456789abcdef" for c in manifest["archiveCommit"]):
        failures.append("MISSING_ARCHIVE_COMMIT")
    if not isinstance(manifest.get("reportSha256"),str) or manifest["reportSha256"]!=sha(report):
        failures.append("REPORT_HASH_MISMATCH")
    rows=report.get("results",[])
    ids=[str(g.get("gameId")) for g in rows]
    expected={str(i) for i in expected_ids}
    if not expected or len(expected)!=len(expected_ids) or set(ids)!=expected or len(ids)!=len(set(ids)) or report.get("status")!="COMPLETE" or report.get("gamesCompleted")!=len(expected) or report.get("gamesRemaining")!=0:
        failures.append("INCOMPLETE_OR_DUPLICATE_FINALS")
    old=history.get("games",[])
    keys=[(g.get("season"),str(g.get("id"))) for g in old]
    if len(keys)!=len(set(keys)): failures.append("DUPLICATE_HISTORY_IDS")
    index={key:g for key,g in zip(keys,old)}
    new=[]
    for g in rows:
        gid=str(g.get("gameId"))
        try:
            if g["scoreSource"]!=manifest["sourceUrl"]: failures.append("GAME_SOURCE_MISMATCH")
            if time(g["date"])>=deadline: failures.append("GAME_AFTER_CUTOFF")
            a,h=g["awayScore"],g["homeScore"]
            if type(a)!=int or type(h)!=int or min(a,h)<0 or a==h: raise ValueError("INVALID_SCORE")
            winner=g["home"] if h>a else g["away"]
            if g["winner"]!=winner: raise ValueError("WINNER_MISMATCH")
            if not g["home"] or not g["away"] or g["home"]==g["away"]: raise ValueError("TEAM_MISMATCH")
            item={"season":report["season"],"week":report["week"],"id":gid,**{k:g[k] for k in ("date","home","away","homeScore","awayScore","winner")}}
            prior=index.get((item["season"],gid))
            if prior and any(prior.get(k)!=item[k] for k in ("week","date","home","away","homeScore","awayScore","winner")): failures.append("CONFLICTING_HISTORY")
            if not prior:new.append(item)
        except (KeyError,ValueError,TypeError,AttributeError):
            failures.append("INVALID_GAME_RECORD")
    if report.get("week") is None or report.get("season") is None: failures.append("INVALID_REPORT_SCOPE")
    if not failures:
        candidate["games"].extend(new)
    return {"status":"RESEARCH_READY" if not failures else "BLOCKED",
            "promotionAuthorized":False,"productionFilesWritten":False,
            "originalSha256":original,"candidateSha256":sha(candidate),
            "addedCount":len(new) if not failures else 0,
            "failures":sorted(set(failures)),
            "rollback":"Discard in-memory candidate; original history unchanged"},candidate
