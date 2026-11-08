"""Offline HMAC manifest prototype, not a production signed timestamp authority.

An HMAC authenticates data only to parties holding the shared secret. It is not
an asymmetric digital signature and cannot prove a real retrieval time.
"""
import hashlib
import hmac
import json

def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def _digest(raw):
    return hashlib.sha256(raw).hexdigest()

def make_manifest(envelope, *, storage_reference):
    if not isinstance(envelope, dict) or envelope.get("observationType") != "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION":
        raise ValueError("UNVERIFIED_ENVELOPE")
    raw = envelope.get("rawResponse")
    if not isinstance(raw, str) or _digest(raw.encode("utf-8")) != envelope.get("contentSha256"):
        raise ValueError("CONTENT_HASH_MISMATCH")
    if not isinstance(storage_reference, str) or not storage_reference.strip():
        raise ValueError("INVALID_STORAGE_REFERENCE")
    if not isinstance(envelope.get("capturedAt"), str) or envelope.get("retrievedAt") != envelope["capturedAt"]:
        raise ValueError("INCONSISTENT_TIMESTAMPS")
    return {
        "schemaVersion": 1,
        "gameId": envelope["gameId"],
        "source": envelope["source"],
        "capturedAt": envelope["capturedAt"],
        "contentSha256": envelope["contentSha256"],
        "storageReference": storage_reference,
        "captureType": "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION",
    }

def authenticate(manifest, *, secret):
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("INVALID_HMAC_KEY")
    return hmac.new(secret, canonical_bytes(manifest), hashlib.sha256).hexdigest()

def verify(manifest, signature, *, secret, external_anchor=None, envelope=None):
    """Fail closed without an independently supplied expected manifest digest."""
    if not isinstance(external_anchor, str) or len(external_anchor) != 64:
        return False, "MISSING_EXTERNAL_TRUST_ANCHOR"
    if not isinstance(signature, str) or len(signature) != 64:
        return False, "INVALID_SIGNATURE"
    try:
        actual = canonical_bytes(manifest)
        if not hmac.compare_digest(_digest(actual), external_anchor):
            return False, "EXTERNAL_ANCHOR_MISMATCH"
        expected = authenticate(manifest, secret=secret)
        if not hmac.compare_digest(expected, signature):
            return False, "SIGNATURE_MISMATCH"
        if envelope is not None:
            rebuilt = make_manifest(envelope, storage_reference=manifest["storageReference"])
            if canonical_bytes(rebuilt) != actual:
                return False, "EVIDENCE_MISMATCH"
        return True, "VERIFIED_OFFLINE_MANIFEST"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False, "UNVERIFIABLE_MANIFEST"
