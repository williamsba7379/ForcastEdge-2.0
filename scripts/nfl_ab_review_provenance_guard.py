"""Fail-closed metadata validation for manual research-only capture/review workflows."""
import hashlib
import datetime as dt
import json
import re
from pathlib import PurePosixPath
from scripts.nfl_ab_archive_adapter import parse_time

BRANCH="audit/nfl-four-model-publisher-diagnostic"
WORKFLOW=".github/workflows/nfl-ab-wednesday-evidence-rehearsal.yml"
HEX64=re.compile(r"^[0-9a-f]{64}$")
HEX40=re.compile(r"^[0-9a-f]{40}$")

def validate_capture_run(run, run_id, sha):
    if not isinstance(run,dict) or not isinstance(run_id,str) or not run_id.isdecimal() or not isinstance(sha,str) or not HEX40.fullmatch(sha):
        raise ValueError("INVALID_CAPTURE_IDENTITY")
    if (run.get("id")!=int(run_id) or run.get("event")!="workflow_dispatch"
        or run.get("name")!="NFL A-B manual Wednesday evidence rehearsal (research only)"
        or run.get("path") not in (WORKFLOW,WORKFLOW+"@"+BRANCH)
        or run.get("head_branch")!=BRANCH or run.get("head_sha")!=sha
        or run.get("status")!="completed" or run.get("conclusion")!="success"):
        raise ValueError("UNTRUSTED_CAPTURE_RUN")
    return True

def validate_capture_artifact(artifact, run_id):
    if (not isinstance(artifact,dict) or artifact.get("name")!="nfl-ab-raw-capture"
        or artifact.get("expired") is not False
        or artifact.get("workflow_run",{}).get("id")!=int(run_id)):
        raise ValueError("UNTRUSTED_CAPTURE_ARTIFACT")
    return True

def validate_review_manifest(path, expected_sha, data):
    if not isinstance(path,str) or not path.startswith("research/reviewed-manifests/") or path.startswith("/") or ".." in PurePosixPath(path).parts or not path.endswith(".json"):
        raise ValueError("INVALID_REVIEW_MANIFEST_PATH")
    if not isinstance(expected_sha,str) or not HEX64.fullmatch(expected_sha):
        raise ValueError("INVALID_REVIEW_MANIFEST_HASH")
    if hashlib.sha256(data).hexdigest()!=expected_sha:
        raise ValueError("REVIEW_MANIFEST_HASH_MISMATCH")
    try:
        games=json.loads(data)
    except (ValueError,UnicodeDecodeError) as exc:
        raise ValueError("INVALID_REVIEW_MANIFEST_JSON") from exc
    if not isinstance(games,list) or not games:
        raise ValueError("EMPTY_REVIEW_MANIFEST")
    return games

def validate_capture_review_chain(run, capture_sha, review_sha, manifest_commit, ancestor_ok):
    """Fail closed on commit lineage and post-capture GitHub commit evidence."""
    if not isinstance(review_sha,str) or not HEX40.fullmatch(review_sha):
        raise ValueError("INVALID_REVIEW_COMMIT")
    if not isinstance(capture_sha,str) or not HEX40.fullmatch(capture_sha) or review_sha==capture_sha or ancestor_ok is not True:
        raise ValueError("INVALID_COMMIT_LINEAGE")
    if not isinstance(manifest_commit,dict) or manifest_commit.get("sha")!=review_sha:
        raise ValueError("MANIFEST_COMMIT_MISMATCH")
    completed=run.get("updated_at")
    committed=manifest_commit.get("commit",{}).get("committer",{}).get("date")
    if not completed or not committed or parse_time(committed)<=parse_time(completed):
        raise ValueError("REVIEW_NOT_AFTER_CAPTURE")
    return True

def validate_artifact_expiry(artifact, run_id, now):
    validate_capture_artifact(artifact,run_id)
    if not isinstance(artifact.get("id"),int) or artifact["id"]<=0:
        raise ValueError("INVALID_ARTIFACT_ID")
    digest=artifact.get("digest")
    if not isinstance(digest,str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",digest):
        raise ValueError("MISSING_ARTIFACT_DIGEST")
    created=artifact.get("created_at")
    expires=artifact.get("expires_at")
    if not created or not expires:
        raise ValueError("MISSING_ARTIFACT_RETENTION")
    start,end,now_time=parse_time(created),parse_time(expires),parse_time(now)
    if not (dt.timedelta(days=29)<=end-start<=dt.timedelta(days=31)) or not (start<=now_time<end):
        raise ValueError("ARTIFACT_EXPIRED_OR_RETENTION_MISMATCH")
    return True

def verify_archive_digest(archive_bytes, artifact):
    expected=artifact.get("digest","")
    if "sha256:"+hashlib.sha256(archive_bytes).hexdigest()!=expected:
        raise ValueError("ARTIFACT_ARCHIVE_DIGEST_MISMATCH")
    return True
