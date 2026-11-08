"""Synthetic offline proof verification. HMAC fixtures are NOT third-party attestations.

No network, filesystem writes, private production keys, or live capture.
A caller must supply separately trusted key registries and expected proof IDs.
"""
import datetime as dt
import hashlib
import hmac
from nfl_signed_evidence_manifest import canonical_bytes

def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def _time(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIME")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("INVALID_TIME")
    return parsed.astimezone(dt.timezone.utc)

def _auth(proof, registry, kind):
    if not isinstance(proof, dict) or proof.get("kind") != kind:
        return False
    key_id = proof.get("authorityId")
    if not isinstance(registry, dict) or not isinstance(key_id, str):
        return False
    entry = registry.get(key_id)
    if not isinstance(entry, dict) or entry.get("status") != "trusted":
        return False
    key = entry.get("testKey")
    sig = proof.get("signature")
    if not isinstance(key, bytes) or len(key) < 32 or not isinstance(sig, str):
        return False
    payload = {k: v for k, v in proof.items() if k != "signature"}
    expected = hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)

def verify_external_proofs(*, envelope, manifest, timestamp_receipt,
                           archive_receipt, timestamp_authorities,
                           archive_authorities, expected_timestamp_id,
                           expected_archive_id, used_proof_ids=()):
    """Return (accepted, reason). Never marks a synthetic proof production-ready."""
    try:
        if not isinstance(envelope, dict) or not isinstance(manifest, dict):
            return False, "INVALID_EVIDENCE"
        raw = envelope["rawResponse"]
        if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != envelope["contentSha256"]:
            return False, "RAW_RESPONSE_HASH_MISMATCH"
        if (manifest.get("gameId") != envelope.get("gameId")
                or manifest.get("contentSha256") != envelope["contentSha256"]
                or manifest.get("capturedAt") != envelope.get("capturedAt")
                or manifest.get("captureType") != "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION"):
            return False, "MANIFEST_BINDING_MISMATCH"
        if not _auth(timestamp_receipt, timestamp_authorities, "timestamp"):
            return False, "UNTRUSTED_TIMESTAMP_PROOF"
        if not _auth(archive_receipt, archive_authorities, "archive"):
            return False, "UNTRUSTED_ARCHIVE_PROOF"
        tid = timestamp_receipt.get("proofId")
        aid = archive_receipt.get("proofId")
        if (not isinstance(tid, str) or not tid or tid != expected_timestamp_id
                or not isinstance(aid, str) or not aid or aid != expected_archive_id
                or tid == aid or tid in used_proof_ids or aid in used_proof_ids):
            return False, "REPLAYED_OR_INCONSISTENT_PROOF_ID"
        if (timestamp_receipt.get("gameId") != envelope["gameId"]
                or timestamp_receipt.get("contentSha256") != envelope["contentSha256"]):
            return False, "TIMESTAMP_EVIDENCE_MISMATCH"
        captured = _time(envelope["capturedAt"])
        issued = _time(timestamp_receipt["issuedAt"])
        if not captured <= issued <= captured + dt.timedelta(minutes=5):
            return False, "TIMESTAMP_INCONSISTENT"
        if (archive_receipt.get("gameId") != envelope["gameId"]
                or archive_receipt.get("manifestSha256") != _digest(manifest)
                or archive_receipt.get("timestampProofSha256") != _digest(timestamp_receipt)):
            return False, "ARCHIVE_BINDING_MISMATCH"
        archived = _time(archive_receipt["archivedAt"])
        if archived < issued:
            return False, "ARCHIVE_TIME_INCONSISTENT"
        return True, "SYNTHETIC_EXTERNAL_PROOFS_VERIFIED"
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False, "UNVERIFIABLE_EXTERNAL_PROOF"
