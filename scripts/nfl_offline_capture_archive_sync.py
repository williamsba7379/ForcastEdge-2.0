"""Research-only offline capture -> immutable Git archive -> history sync pipeline."""
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from scripts.nfl_espn_trusted_capture_offline import inspect_response
from scripts.nfl_future_history_sync_gate import sha,time
from scripts.nfl_future_immutable_evidence import verify

def run(repo,history,raw,url,retrieved_at,archived_at,cutoff,season,week,expected_ids,commit,path):
    original=deepcopy(history)
    capture=inspect_response(url,raw,retrieved_at,cutoff,season,week,expected_ids)
    if capture["status"]!="CAPTURE_VALIDATED_OFFLINE":
        return {"status":"BLOCKED","stage":"CAPTURE","failures":capture["failures"],"promotionAuthorized":False,
                "originalSha256":sha(history),"candidateSha256":sha(history),"rollback":"discard candidate"},original
    try:
        if time(archived_at)<time(retrieved_at) or time(archived_at)>time(cutoff):
            raise ValueError("ARCHIVE_CUTOFF")
    except (ValueError,TypeError,AttributeError):
        return {"status":"BLOCKED","stage":"ARCHIVE_TIME","failures":["INVALID_ARCHIVE_TIME"],
                "promotionAuthorized":False,"originalSha256":sha(history),"candidateSha256":sha(history)},original
    report={"season":season,"week":week,"status":"COMPLETE","gamesCompleted":len(expected_ids),
            "gamesRemaining":0,"scoreSource":url,"results":capture["results"]}
    try:
        blob=subprocess.check_output(["git","-C",str(repo),"rev-parse",commit+":"+path],stderr=subprocess.DEVNULL).decode().strip()
    except (subprocess.CalledProcessError,ValueError,TypeError):
        return {"status":"BLOCKED","stage":"ARCHIVE","failures":["MISSING_GIT_BLOB"],
                "promotionAuthorized":False,"originalSha256":sha(history),"candidateSha256":sha(history)},original
    manifest={"provider":"ESPN","sourceUrl":url,"rawResponseSha256":hashlib.sha256(raw).hexdigest(),
              "archiveCommit":commit,"archivePath":path,"archiveBlob":blob,
              "retrievedAt":retrieved_at,"archivedAt":archived_at,"reportSha256":sha(report)}
    outcome,candidate=verify(repo,history,report,manifest,cutoff,expected_ids,require_native=True)
    if outcome["status"]!="RESEARCH_READY":
        return {"status":"BLOCKED","stage":"VERIFY_OR_SYNC","failures":outcome["errors"],
                "promotionAuthorized":False,"originalSha256":sha(history),"candidateSha256":sha(history),
                "rollback":"discard candidate"},original
    return {"status":"RESEARCH_READY","stage":"IN_MEMORY_ONLY","promotionAuthorized":False,
            "liveCapturePerformed":False,"productionFilesWritten":False,
            "originalSha256":sha(history),"candidateSha256":sha(candidate),
            "rawResponseSha256":manifest["rawResponseSha256"],"verifiedCommit":commit,
            "verifiedBlob":blob,"addedCount":outcome["addedCount"],
            "rollback":"discard candidate; source history unchanged"},candidate
