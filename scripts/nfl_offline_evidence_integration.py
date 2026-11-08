"""Synthetic-only end-to-end evidence adapter; no network or production integration.

The external anchor and HMAC key must be supplied by a separate trusted test
caller. A passing result does not prove an independently trusted timestamp.
"""
import datetime as dt
import hashlib
import hmac

from nfl_offline_capture_envelope import capture_envelope
from nfl_future_final_evidence import capture as validate_final
from nfl_signed_evidence_manifest import make_manifest, authenticate, verify, canonical_bytes
from nfl_sqlite_evidence_store import SQLiteAppendOnlyEvidence


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("INVALID_TIMESTAMP")
    return stamp


def prepare(*, game_id, source, response_bytes, request_started_at, clock, schedule):
    """Construct a validated first-final record from an offline fixture."""
    if not isinstance(schedule, dict) or schedule.get("gameId") != game_id:
        return None, None, "GAME_ID_MISMATCH"
    try:
        envelope = capture_envelope(
            game_id=game_id, source=source, response_bytes=response_bytes,
            clock=clock, request_started_at=request_started_at)
        captured = _timestamp(envelope["capturedAt"])
        kickoff = _timestamp(schedule["kickoffAt"])
        record, reason = validate_final(
            game_id=game_id, kickoff_at=kickoff, source=source,
            raw_response=response_bytes, retrieved_at=captured, now=captured)
        if record is None:
            return None, None, reason
        if (record["retrievedAt"] != envelope["capturedAt"]
                or record["observedFinalAt"] != envelope["capturedAt"]
                or record["rawResponse"] != envelope["rawResponse"]
                or record["contentSha256"] != envelope["contentSha256"]):
            return None, None, "ENVELOPE_RECORD_MISMATCH"
        # Reuse the stronger schedule/team/season evidence gate before any write.
        from nfl_future_evidence_safeguards import MemoryAppendOnlyEvidence
        accepted, reason = MemoryAppendOnlyEvidence().submit(record, schedule)
        if not accepted:
            return None, None, reason
        return envelope, record, "VALIDATED_OFFLINE_FINAL"
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
        return None, None, "UNVERIFIABLE_OFFLINE_FIXTURE"


def persist(*, db_path, envelope, record, schedule, secret, storage_reference):
    """Write validated fixture and return an HMAC manifest and local digest.

    The returned digest is NOT an external trust anchor until a separate
    trusted system preserves it. This method cannot establish that trust.
    """
    if not isinstance(envelope, dict) or not isinstance(record, dict):
        return None, None, None, "INVALID_EVIDENCE"
    if (envelope.get("observationType") != "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION"
            or record.get("gameId") != envelope.get("gameId")
            or record.get("rawResponse") != envelope.get("rawResponse")
            or record.get("contentSha256") != envelope.get("contentSha256")
            or record.get("retrievedAt") != envelope.get("capturedAt")
            or record.get("observedFinalAt") != envelope.get("capturedAt")):
        return None, None, None, "ENVELOPE_RECORD_MISMATCH"
    try:
        manifest = make_manifest(envelope, storage_reference=storage_reference)
        signature = authenticate(manifest, secret=secret)
        store = SQLiteAppendOnlyEvidence(db_path)
        accepted, reason = store.submit(record, schedule)
        if not accepted:
            return None, None, None, reason
        anchor_candidate = hashlib.sha256(canonical_bytes(manifest)).hexdigest()
        return manifest, signature, anchor_candidate, "STORED_OFFLINE_FINAL"
    except (ValueError, TypeError, KeyError, OSError):
        return None, None, None, "UNVERIFIABLE_OFFLINE_EVIDENCE"


def verify_persisted(*, db_path, game_id, envelope, manifest, signature,
                     secret, external_anchor, expected_storage_reference):
    """Fail closed if the original externally preserved anchor is unavailable."""
    if (not isinstance(manifest, dict)
            or manifest.get("gameId") != game_id
            or manifest.get("storageReference") != expected_storage_reference):
        return False, "STORAGE_REFERENCE_MISMATCH"
    valid, reason = verify(manifest, signature, secret=secret,
                           external_anchor=external_anchor, envelope=envelope)
    if not valid:
        return False, reason
    try:
        record = SQLiteAppendOnlyEvidence(db_path).get(game_id)
        if record is None:
            return False, "MISSING_STORED_EVIDENCE"
        if (record.get("gameId") != game_id
                or record.get("rawResponse") != envelope.get("rawResponse")
                or record.get("contentSha256") != envelope.get("contentSha256")
                or record.get("retrievedAt") != envelope.get("capturedAt")
                or record.get("observedFinalAt") != envelope.get("capturedAt")):
            return False, "STORED_EVIDENCE_MISMATCH"
        return True, "VERIFIED_OFFLINE_STORED_EVIDENCE"
    except (ValueError, TypeError, KeyError, OSError):
        return False, "STORED_EVIDENCE_INTEGRITY_FAILURE"
