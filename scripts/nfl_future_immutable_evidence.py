"""Offline independent verification of archived ESPN evidence; never fetches network or writes."""
import hashlib
import json
import re
import subprocess
from scripts.nfl_future_history_sync_gate import gate,sha,time

def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],stderr=subprocess.DEVNULL)

def verify(repo,history,report,manifest,cutoff,expected_ids):
    errors=[]
    commit=manifest.get("archiveCommit","")
    path=manifest.get("archivePath","")
    if not re.fullmatch(r"[0-9a-f]{40}",commit) or not isinstance(path,str) or not re.fullmatch(r"[a-zA-Z0-9_./-]+",path) or path.startswith("/") or ".." in path.split("/"):
        errors.append("INVALID_ARCHIVE_REFERENCE")
    raw=b""
    if not errors:
        try:
            resolved=git(repo,"rev-parse","--verify",commit+"^{commit}").decode().strip()
            if resolved!=commit: errors.append("COMMIT_MISMATCH")
            raw=git(repo,"show",commit+":"+path)
            blob=git(repo,"rev-parse",commit+":"+path).decode().strip()
            if blob!=manifest.get("archiveBlob"): errors.append("BLOB_MISMATCH")
            committed=time(git(repo,"show","-s","--format=%cI",commit).decode().strip())
            if committed>time(cutoff) or committed>time(manifest["archivedAt"]):
                errors.append("COMMIT_AFTER_ARCHIVE_OR_CUTOFF")
        except (subprocess.CalledProcessError,ValueError,KeyError,TypeError,AttributeError):
            errors.append("ARCHIVE_NOT_VERIFIED")
    if hashlib.sha256(raw).hexdigest()!=manifest.get("rawResponseSha256"):
        errors.append("RAW_SHA256_MISMATCH")
    try:
        parsed=json.loads(raw)
        if "events" in parsed:
            from scripts.nfl_espn_trusted_capture_offline import inspect_response
            capture=inspect_response(manifest["sourceUrl"],raw,manifest["retrievedAt"],cutoff,report["season"],report["week"],[g["gameId"] for g in report["results"]])
            if capture["status"]!="CAPTURE_VALIDATED_OFFLINE":
                errors.extend(capture["failures"])
            raw_rows=capture["results"]
        else:
            if parsed.get("provider")!="ESPN" or parsed.get("sourceUrl")!=manifest.get("sourceUrl"):
                errors.append("RAW_SOURCE_MISMATCH")
            if parsed.get("season")!=report.get("season") or parsed.get("week")!=report.get("week"):
                errors.append("RAW_SCOPE_MISMATCH")
            raw_rows=parsed["results"]
        report_rows=report["results"]
        def index(rows):
            keys=[str(g["gameId"]) for g in rows]
            if len(keys)!=len(set(keys)): raise ValueError("DUPLICATE_RAW_IDS")
            return {str(g["gameId"]):g for g in rows}
        source=index(raw_rows);reported=index(report_rows)
        if set(source)!=set(reported): errors.append("RAW_GAME_IDS_MISMATCH")
        for gid,g in reported.items():
            original=source.get(gid,{})
            for field in ("date","home","away","homeScore","awayScore","winner"):
                if original.get(field)!=g.get(field): errors.append("RAW_SCORE_OR_TEAM_MISMATCH")
    except (ValueError,KeyError,TypeError,AttributeError):
        errors.append("INVALID_RAW_EVIDENCE")
    base,candidate=gate(history,report,manifest,cutoff,expected_ids)
    errors.extend(base["failures"])
    if errors:
        return {"status":"BLOCKED","promotionAuthorized":False,"errors":sorted(set(errors)),
                "originalSha256":base["originalSha256"],"candidateSha256":base["originalSha256"],
                "addedCount":0},history
    return {"status":"RESEARCH_READY","promotionAuthorized":False,"errors":[],
            "originalSha256":base["originalSha256"],"candidateSha256":base["candidateSha256"],
            "addedCount":base["addedCount"],"verifiedCommit":commit,
            "verifiedBlob":manifest["archiveBlob"],
            "rawResponseSha256":hashlib.sha256(raw).hexdigest(),
            "rollback":"Discard candidate; original untouched"},candidate
