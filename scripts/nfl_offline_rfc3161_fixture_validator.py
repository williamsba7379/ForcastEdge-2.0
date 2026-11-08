"""Synthetic RFC 3161-like metadata fixture policy checks, NOT RFC 3161 verification.

No ASN.1 parsing, cryptographic signatures, certificate verification, network,
dependencies, filesystem writes, private keys, or live evidence collection.
Caller-provided metadata is untrusted; research-only acceptance is not proof.
"""
import datetime as dt
import hashlib
import re


_SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIME")
    value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("INVALID_TIME")
    return value.astimezone(dt.timezone.utc)


def validate_rfc3161_fixture(*, raw_evidence, fixture, expected_nonce,
                             approved_policies, approved_signers,
                             expected_token_id, used_token_ids=(),
                             earliest_time, latest_time,
                             production_requested=False):
    """Return (research_accepted, reason, metadata), always productionReady=False."""
    metadata = {"productionReady": False,
                "evidenceClass": "SYNTHETIC_RFC3161_METADATA_NOT_CRYPTOGRAPHICALLY_VERIFIED"}
    if production_requested:
        return False, "PRODUCTION_AUTHORIZATION_FORBIDDEN", metadata
    if not isinstance(raw_evidence, bytes) or not isinstance(fixture, dict):
        return False, "INVALID_FIXTURE", metadata
    imprint = fixture.get("messageImprint")
    if (not isinstance(imprint, dict)
            or not isinstance(imprint.get("algorithm"), str)
            or not isinstance(imprint.get("digest"), str)
            or not _SHA256_HEX.fullmatch(imprint["digest"])):
        return False, "MALFORMED_MESSAGE_IMPRINT", metadata
    if (imprint["algorithm"] != "sha256"
            or imprint["digest"] != hashlib.sha256(raw_evidence).hexdigest()):
        return False, "IMPRINT_MISMATCH", metadata
    if (not isinstance(expected_nonce, str) or not expected_nonce
            or not isinstance(fixture.get("nonce"), str)
            or fixture["nonce"] != expected_nonce):
        return False, "NONCE_MISMATCH", metadata
    if (not isinstance(approved_policies, (set, frozenset, tuple, list))
            or fixture.get("policyOid") not in approved_policies):
        return False, "UNAPPROVED_TIMESTAMP_POLICY", metadata
    signer = fixture.get("signerId")
    if (not isinstance(signer, str)
            or not isinstance(approved_signers, (set, frozenset, tuple, list))
            or signer not in approved_signers
            or fixture.get("extendedKeyUsage") != "timeStamping"):
        return False, "UNAPPROVED_TIMESTAMP_SIGNER", metadata
    token_id = fixture.get("tokenId")
    if (not isinstance(token_id, str) or not token_id
            or token_id != expected_token_id
            or token_id in used_token_ids):
        return False, "REPLAYED_OR_MISMATCHED_TOKEN_ID", metadata
    try:
        generated = _utc(fixture["genTime"])
        earliest = _utc(earliest_time)
        latest = _utc(latest_time)
        if earliest > latest or not earliest <= generated <= latest:
            return False, "INVALID_TIMESTAMP_WINDOW", metadata
    except (KeyError, ValueError, TypeError, OverflowError):
        return False, "INVALID_TIMESTAMP_WINDOW", metadata
    return True, "SYNTHETIC_RFC3161_FIXTURE_ACCEPTED_RESEARCH_ONLY", metadata
