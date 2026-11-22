"""Review-only create-only freeze; never writes historical or production paths."""
import datetime as dt
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from .nfl_wednesday_release_gate import digest, validate, UTC


def prepare(schedule, card, evidence, *, now=None, sources=None):
    now = now or dt.datetime.now(UTC)
    decision = validate(schedule, card, evidence, now=now, sources=sources)
    if decision["status"] != "PASS":
        return {"status": "DELIVERY_BLOCKED", "validation": decision}
    return {"status": "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED",
            "frozenAt": now.astimezone(UTC).isoformat(),
            "season": card["season"], "week": card["week"],
            "card": card, "evidence": evidence,
            "cardSha256": digest(card), "evidenceSha256": digest(evidence),
            "validation": decision}


def verify_candidate(candidate):
    if not isinstance(candidate, dict) or candidate.get("status") != "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED":
        raise ValueError("INVALID_CANDIDATE")
    if (digest(candidate["card"]) != candidate["cardSha256"]
            or digest(candidate["evidence"]) != candidate["evidenceSha256"]):
        raise ValueError("CANDIDATE_DIGEST_MISMATCH")
    if candidate.get("validation", {}).get("status") != "PASS":
        raise ValueError("CANDIDATE_NOT_VALIDATED")


def write_create_only(candidate, destination, *, allowed_directory):
    """Atomic create-only install inside a caller-provided isolated directory.

    No path outside allowed_directory is accepted; hard links and pre-existing
    targets cannot be replaced. This is local crash-safety, not durable retention.
    """
    verify_candidate(candidate)
    root = Path(allowed_directory).resolve(strict=True)
    path = Path(destination)
    if path.parent.resolve(strict=True) != root or path.name in ("", ".", ".."):
        raise ValueError("DESTINATION_OUTSIDE_ISOLATION")
    if not stat.S_ISDIR(os.lstat(root).st_mode) or path.is_symlink():
        raise ValueError("UNSAFE_DESTINATION")
    if path.exists() or path.is_symlink():
        raise FileExistsError(str(path))
    payload = (json.dumps(candidate, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".candidate-", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic no-replace install; unlike os.replace this cannot overwrite.
        os.link(temporary, path, follow_symlinks=False)
        directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
    return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}
