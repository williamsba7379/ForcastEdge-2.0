#!/usr/bin/env python3
"""Isolated, fail-closed historical final-result availability audit. No writes."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

UTC = dt.timezone.utc
REQUIRED = ("gameId", "source", "observedFinalAt", "retrievedAt", "contentSha256", "kickoffAt", "rawResponse")

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)

def validate(record, cutoff):
    """Return (eligible, reason). Fail closed on missing, inconsistent or late evidence."""
    if not isinstance(record, dict) or any(not record.get(k) for k in REQUIRED):
        return False, "UNVERIFIED_HISTORICAL_AVAILABILITY"
    try:
        limit = timestamp(cutoff)
        observed = timestamp(record["observedFinalAt"])
        retrieved = timestamp(record["retrievedAt"])
        kickoff = timestamp(record["kickoffAt"])
        source = record["source"]
        digest = record["contentSha256"]
        if not isinstance(record["gameId"], str) or not record["gameId"].strip():
            return False, "INVALID_GAME_ID"
        if not isinstance(source, str) or urlsplit(source).scheme != "https" or urlsplit(source).hostname not in ("site.api.espn.com", "www.nfl.com", "nfl.com"):
            return False, "INVALID_SOURCE"
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return False, "INVALID_CONTENT_HASH"
        if "rawResponse" in record:
            raw = record["rawResponse"]
            if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
                return False, "CONTENT_HASH_MISMATCH"
        if observed < kickoff:
            return False, "FINAL_BEFORE_KICKOFF"
        if retrieved < observed:
            return False, "INCONSISTENT_EVIDENCE_TIMES"
        if observed >= limit or retrieved >= limit:
            return False, "LATE_FINAL_EVIDENCE"
    except (ValueError, TypeError, KeyError, OverflowError):
        return False, "INVALID_EVIDENCE"
    return True, "VERIFIED_AS_OF_CUTOFF"

def audit(records, cutoff):
    results = [{"gameId": r.get("gameId") if isinstance(r, dict) else None,
                "eligible": validate(r, cutoff)[0], "reason": validate(r, cutoff)[1]}
               for r in records]
    return {"cutoff": cutoff, "eligible": sum(x["eligible"] for x in results),
            "rejected": sum(not x["eligible"] for x in results), "results": results}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--cutoff", required=True)
    args = parser.parse_args()
    records = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        parser.error("evidence must be a JSON list")
    print(json.dumps(audit(records, args.cutoff), indent=2))

if __name__ == "__main__":
    main()
