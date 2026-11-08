"""Fail-closed OFFLINE trust-policy checks over synthetic parsed metadata only.

This does NOT parse or cryptographically authenticate RFC 3161 tokens,
certificates, archive signatures, or external services. Caller assertions are
untrusted fixtures; success is RESEARCH ONLY and never production readiness.
No network, filesystem writes, or private keys.
"""
import datetime as dt
import hashlib

from nfl_signed_evidence_manifest import canonical_bytes


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIME")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("INVALID_TIME")
    return parsed.astimezone(dt.timezone.utc)


def assess_trust_policy(*, envelope, manifest, timestamp_proof, archive_proof,
                        timestamp_authorities, archive_authorities,
                        expected_timestamp_id, expected_archive_id,
                        used_proof_ids=(), production_requested=False):
    """Return (accepted_for_research, reason, metadata); never production-ready."""
    meta = {"productionReady": False, "evidenceClass": "SYNTHETIC_METADATA_UNVERIFIED"}
    if production_requested:
        return False, "PRODUCTION_AUTHORIZATION_FORBIDDEN", meta
    if not isinstance(envelope, dict) or not isinstance(manifest, dict):
        return False, "INVALID_EVIDENCE", meta
    try:
        raw = envelope["rawResponse"]
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if (not isinstance(raw, str) or digest != envelope["contentSha256"]
                or manifest.get("gameId") != envelope.get("gameId")
                or manifest.get("contentSha256") != digest
                or manifest.get("capturedAt") != envelope.get("capturedAt")
                or manifest.get("captureType") != "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION"):
            return False, "EVIDENCE_BINDING_MISMATCH", meta
        if not isinstance(timestamp_proof, dict) or not timestamp_proof.get("authorityId"):
            return False, "MISSING_TIMESTAMP_AUTHORITY", meta
        if not isinstance(timestamp_authorities, dict):
            return False, "UNTRUSTED_TIMESTAMP_AUTHORITY", meta
        ts_auth = timestamp_authorities.get(timestamp_proof["authorityId"])
        if not isinstance(ts_auth, dict) or ts_auth.get("status") != "trusted":
            return False, "UNTRUSTED_TIMESTAMP_AUTHORITY", meta
        if not isinstance(archive_proof, dict) or not archive_proof.get("authorityId"):
            return False, "MISSING_ARCHIVE_AUTHORITY", meta
        if not isinstance(archive_authorities, dict):
            return False, "UNTRUSTED_ARCHIVE_AUTHORITY", meta
        ar_auth = archive_authorities.get(archive_proof["authorityId"])
        if not isinstance(ar_auth, dict) or ar_auth.get("status") != "trusted":
            return False, "UNTRUSTED_ARCHIVE_AUTHORITY", meta
        captured = _utc(envelope["capturedAt"])
        issued = _utc(timestamp_proof["issuedAt"])
        archived = _utc(archive_proof["archivedAt"])
        for authority, proof_time in ((ts_auth, issued), (ar_auth, archived)):
            if (authority.get("certificateStatus") != "valid"
                    or authority.get("revocationStatus") != "good"
                    or not _utc(authority["validFrom"]) <= proof_time <= _utc(authority["validUntil"])):
                return False, "INVALID_CERTIFICATE_METADATA", meta
        if (timestamp_proof.get("gameId") != envelope["gameId"]
                or timestamp_proof.get("contentSha256") != digest):
            return False, "TIMESTAMP_EVIDENCE_MISMATCH", meta
        if not captured <= issued <= captured + dt.timedelta(minutes=5):
            return False, "TIMESTAMP_ORDER_MISMATCH", meta
        manifest_digest = hashlib.sha256(canonical_bytes(manifest)).hexdigest()
        if (archive_proof.get("protectionStatus") != "independently_protected"
                or archive_proof.get("retentionStatus") != "locked"):
            return False, "MISSING_ARCHIVAL_PROTECTION", meta
        tid, aid = timestamp_proof.get("proofId"), archive_proof.get("proofId")
        if (not isinstance(tid, str) or not tid or tid != expected_timestamp_id
                or not isinstance(aid, str) or not aid or aid != expected_archive_id
                or tid == aid or tid in used_proof_ids or aid in used_proof_ids):
            return False, "REPLAYED_OR_MISMATCHED_PROOF_ID", meta
        if (archive_proof.get("gameId") != envelope["gameId"]
                or archive_proof.get("manifestSha256") != manifest_digest
                or archive_proof.get("timestampProofSha256")
                    != hashlib.sha256(canonical_bytes(timestamp_proof)).hexdigest()
                or archived < issued):
            return False, "ARCHIVE_BINDING_MISMATCH", meta
        return True, "SYNTHETIC_TRUST_POLICY_ACCEPTED_NOT_CRYPTOGRAPHICALLY_VERIFIED", meta
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError, UnicodeError):
        return False, "UNVERIFIABLE_TRUST_METADATA", meta
