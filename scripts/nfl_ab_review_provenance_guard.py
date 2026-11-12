"""Fail-closed metadata validation for manual research-only capture/review workflows."""
import hashlib
import json
import re
from pathlib import PurePosixPath

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
