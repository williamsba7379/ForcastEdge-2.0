"""Offline-only composition of synthetic proof verification and storage readiness.

This is NOT production readiness. Never interprets caller flags as external trust.
No network access, filesystem writes, or production integration.
"""
from nfl_offline_external_proof_verifier import verify_external_proofs
from nfl_offline_readiness_gate import assess


def assess_offline_proof_readiness(*, envelope, manifest, signature,
                                  timestamp_receipt, archive_receipt,
                                  timestamp_authorities, archive_authorities,
                                  expected_timestamp_id, expected_archive_id,
                                  receipt, external_anchor, key_id, key_registry,
                                  db_path, game_id, submission_state="ANCHORED",
                                  used_proof_ids=()):
    """Return (False, reason, metadata); never grant production authorization.

    Existing readiness gate consumes synthetic trusted/protected flags; this
    adapter requires separate signed synthetic proof verification first, and
    checks bindings between both receipt representations before invoking it.
    """
    denied = {"productionReady": False, "evidenceClass": "SYNTHETIC_OFFLINE_ONLY"}
    if submission_state != "ANCHORED":
        return False, "INCOMPLETE_SUBMISSION", denied
    valid, reason = verify_external_proofs(
        envelope=envelope, manifest=manifest,
        timestamp_receipt=timestamp_receipt, archive_receipt=archive_receipt,
        timestamp_authorities=timestamp_authorities,
        archive_authorities=archive_authorities,
        expected_timestamp_id=expected_timestamp_id,
        expected_archive_id=expected_archive_id,
        used_proof_ids=used_proof_ids)
    if not valid:
        return False, reason, denied
    if (not isinstance(receipt, dict) or not isinstance(timestamp_receipt, dict)
            or receipt.get("trusted") is not True
            or receipt.get("gameId") != timestamp_receipt.get("gameId")
            or receipt.get("contentSha256") != timestamp_receipt.get("contentSha256")
            or receipt.get("issuedAt") != timestamp_receipt.get("issuedAt")):
        return False, "TIMESTAMP_GATE_RECEIPT_MISMATCH", denied
    if (not isinstance(external_anchor, dict)
            or external_anchor.get("protected") is not True
            or external_anchor.get("gameId") != archive_receipt.get("gameId")
            or external_anchor.get("digest") != archive_receipt.get("manifestSha256")):
        return False, "ARCHIVE_GATE_ANCHOR_MISMATCH", denied
    ready, reason = assess(
        envelope=envelope, manifest=manifest, signature=signature,
        receipt=receipt, external_anchor=external_anchor, key_id=key_id,
        key_registry=key_registry, db_path=db_path, game_id=game_id,
        submission_state=submission_state)
    if not ready:
        return False, reason, denied
    return True, "SYNTHETIC_OFFLINE_CHAIN_VERIFIED_NOT_PRODUCTION_READY", denied
