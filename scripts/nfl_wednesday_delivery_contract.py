"""Read-only manifest contract; no network, GitHub writes or publication."""
import hashlib
import json
from pathlib import Path


def manifest(candidate, *, immutable_uri=None):
    if candidate.get("status") != "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED":
        return {"status": "DELIVERY_BLOCKED", "reason": "NO_VERIFIED_RELEASE_CANDIDATE"}
    if not immutable_uri:
        return {"status": "DELIVERY_BLOCKED", "reason": "NO_APPROVED_READ_ONLY_RETRIEVAL_URI"}
    return {"status": "RETRIEVAL_READY_NOT_PUBLISHED",
            "season": candidate["season"], "week": candidate["week"],
            "frozenAt": candidate["frozenAt"],
            "cardSha256": candidate["cardSha256"],
            "evidenceSha256": candidate["evidenceSha256"],
            "immutableUri": immutable_uri,
            "note": "A consumer must independently verify bytes, source, and approval before displaying as official."}


def inspect_local(path):
    """Local read-only inspection; does not fetch external URLs."""
    raw = Path(path).read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
