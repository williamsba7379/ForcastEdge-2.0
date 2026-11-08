"""Synthetic-only readiness gate for NFL evidence research.

This module makes no network requests, does not create or alter databases,
and cannot establish real timestamp or archival trust. Trust receipts, key
registry and external anchors are caller-supplied fixtures only.
"""
import datetime as dt
import hashlib
import hmac
import json
import sqlite3
from pathlib import Path

from nfl_signed_evidence_manifest import canonical_bytes


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("INVALID_TIMESTAMP")
    return t.astimezone(dt.timezone.utc)


def assess(*, envelope, manifest, signature, receipt, external_anchor,
           key_id, key_registry, db_path, game_id, submission_state="ANCHORED"):
    """Return (ready, reason). Never repairs or writes evidence.

    A receipt is a synthetic representation of an independently authenticated
    timestamp. It is NOT cryptographic proof; caller must establish that trust.
    A digest is NOT protected merely because the caller passes it here.
    """
    if submission_state != "ANCHORED":
        return False, "INCOMPLETE_SUBMISSION"
    if not isinstance(receipt, dict) or receipt.get("trusted") is not True:
        return False, "MISSING_TRUSTED_TIMESTAMP_RECEIPT"
    try:
        if receipt.get("gameId") != game_id or receipt.get("contentSha256") != envelope.get("contentSha256"):
            return False, "TIMESTAMP_RECEIPT_MISMATCH"
        issued = _utc(receipt["issuedAt"])
        captured = _utc(envelope["capturedAt"])
        if issued < captured or (issued - captured) > dt.timedelta(minutes=5):
            return False, "TIMESTAMP_RECEIPT_MISMATCH"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False, "TIMESTAMP_RECEIPT_MISMATCH"
    if not isinstance(external_anchor, dict) or external_anchor.get("protected") is not True:
        return False, "MISSING_PROTECTED_EXTERNAL_ANCHOR"
    if not isinstance(key_registry, dict) or not isinstance(key_id, str):
        return False, "UNKNOWN_OR_REVOKED_KEY"
    entry = key_registry.get(key_id)
    if not isinstance(entry, dict) or entry.get("status") != "active":
        return False, "UNKNOWN_OR_REVOKED_KEY"
    secret = entry.get("secret")
    if not isinstance(secret, bytes) or len(secret) < 32:
        return False, "UNKNOWN_OR_REVOKED_KEY"
    try:
        if (not isinstance(manifest, dict)
                or manifest.get("gameId") != game_id
                or manifest.get("contentSha256") != envelope.get("contentSha256")
                or manifest.get("capturedAt") != envelope.get("capturedAt")):
            return False, "MANIFEST_EVIDENCE_MISMATCH"
        expected_digest = hashlib.sha256(canonical_bytes(manifest)).hexdigest()
        if (external_anchor.get("gameId") != game_id
                or external_anchor.get("digest") != expected_digest):
            return False, "EXTERNAL_ANCHOR_MISMATCH"
        expected_signature = hmac.new(secret, canonical_bytes(manifest), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected_signature, signature):
            return False, "KEY_OR_SIGNATURE_MISMATCH"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False, "UNVERIFIABLE_MANIFEST"
    if not isinstance(db_path, (str, Path)):
        return False, "STORAGE_UNAVAILABLE"
    path = Path(db_path)
    if not path.is_file():
        return False, "STORAGE_UNAVAILABLE"
    try:
        # mode=ro prevents accidental creation of a missing database.
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return False, "STORAGE_CORRUPT"
            row = db.execute(
                "SELECT evidence_json,content_sha256,raw_response FROM first_final_evidence WHERE game_id=?",
                (game_id,)).fetchone()
        if row is None:
            return False, "STORED_EVIDENCE_MISSING"
        record = json.loads(row[0])
        raw = row[2]
        if (not isinstance(record, dict) or not isinstance(raw, str)
                or record.get("gameId") != game_id
                or record.get("rawResponse") != raw
                or record.get("contentSha256") != row[1]
                or hashlib.sha256(raw.encode("utf-8")).hexdigest() != row[1]
                or row[1] != envelope.get("contentSha256")
                or raw != envelope.get("rawResponse")
                or record.get("retrievedAt") != envelope.get("capturedAt")
                or record.get("observedFinalAt") != envelope.get("capturedAt")):
            return False, "STORED_EVIDENCE_MISMATCH"
    except (sqlite3.DatabaseError, sqlite3.OperationalError, OSError, ValueError,
            TypeError, UnicodeError, KeyError):
        return False, "STORAGE_CORRUPT_OR_UNAVAILABLE"
    return True, "SYNTHETIC_READINESS_GATE_PASSED"
