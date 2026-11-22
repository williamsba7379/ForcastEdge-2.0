"""Read-only manifest: verified local bytes and separately approved retrieval locator."""
import hashlib
import json
from pathlib import Path
from .nfl_wednesday_freeze import verify_candidate


def manifest(candidate, *, immutable_uri=None, approved_uri=None, candidate_bytes=None):
    try:
        verify_candidate(candidate)
        if not isinstance(immutable_uri, str) or not immutable_uri or immutable_uri != approved_uri:
            return {"status": "DELIVERY_BLOCKED", "reason": "UNAPPROVED_RETRIEVAL_URI"}
        if not isinstance(candidate_bytes, bytes):
            return {"status": "DELIVERY_BLOCKED", "reason": "MISSING_CANDIDATE_BYTES"}
        decoded = json.loads(candidate_bytes)
        if decoded != candidate:
            return {"status": "DELIVERY_BLOCKED", "reason": "CANDIDATE_BYTES_MISMATCH"}
        return {"status": "RETRIEVAL_READY_NOT_PUBLISHED",
                "season": candidate["season"], "week": candidate["week"],
                "frozenAt": candidate["frozenAt"],
                "candidateSha256": hashlib.sha256(candidate_bytes).hexdigest(),
                "cardSha256": candidate["cardSha256"],
                "evidenceSha256": candidate["evidenceSha256"],
                "immutableUri": immutable_uri,
                "published": False}
    except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
        return {"status": "DELIVERY_BLOCKED", "reason": "INVALID_CANDIDATE_OR_BYTES"}


def inspect_local(path):
    raw = Path(path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
