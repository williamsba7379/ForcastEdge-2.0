"""Create-only release-candidate writer. Never updates historical or production files."""
import datetime as dt
import json
import os
from pathlib import Path
from .nfl_wednesday_release_gate import digest, validate, UTC


def prepare(schedule, card, evidence, *, now=None):
    now = now or dt.datetime.now(UTC)
    decision = validate(schedule, card, evidence, now=now)
    if decision["status"] != "PASS":
        return {"status": "DELIVERY_BLOCKED", "validation": decision}
    frozen = {"status": "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED",
              "frozenAt": now.astimezone(UTC).isoformat(),
              "season": card["season"], "week": card["week"],
              "card": card, "evidence": evidence,
              "cardSha256": digest(card), "evidenceSha256": digest(evidence),
              "validation": decision}
    return frozen


def write_create_only(candidate, destination):
    if candidate.get("status") != "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED":
        raise ValueError("NOT_AN_ELIGIBLE_CANDIDATE")
    path = Path(destination)
    if not path.parent.exists():
        raise FileNotFoundError("DESTINATION_DIRECTORY_MUST_ALREADY_EXIST")
    payload = (json.dumps(candidate, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # A partial candidate remains visible for independent investigation.
        raise
    return {"path": str(path), "sha256": __import__("hashlib").sha256(payload).hexdigest()}
