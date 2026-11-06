"""Fail-closed independent schedule comparison, research-only.

Second-source manifest must be captured independently from an NFL-operated
HTTPS source, with raw bytes, independently observed retrieval time and SHA256.
No synthetic ESPN-derived second source may be passed as independent evidence.
"""
import base64
import hashlib
import json
import urllib.parse
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_schedule_provenance import verify_schedule_evidence

ALLOWED_HOSTS=frozenset(("www.nfl.com","nfl.com"))

def capture_official_schedule(raw, retrieved_at, source_url):
    parsed=urllib.parse.urlsplit(source_url)
    if parsed.scheme!="https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("UNTRUSTED_SECOND_SOURCE")
    if not isinstance(raw,bytes) or not raw:
        raise ValueError("MISSING_SECOND_SOURCE_RAW")
    parse_time(retrieved_at)
    payload=json.loads(raw)
    if not isinstance(payload,dict) or not isinstance(payload.get("games"),list):
        raise ValueError("INVALID_SECOND_SOURCE_FORMAT")
    return {"schemaVersion":1,"sourceUrl":source_url,"retrievedAt":retrieved_at,
            "responseSha256":hashlib.sha256(raw).hexdigest(),
            "rawBodyBase64":base64.b64encode(raw).decode("ascii")}

def verify_independent_schedule(espn_evidence, second_evidence, cutoff, expected_schedule):
    primary=verify_schedule_evidence(espn_evidence,cutoff,expected_schedule)
    if not isinstance(second_evidence,dict) or second_evidence.get("schemaVersion")!=1:
        raise ValueError("MISSING_SECOND_SOURCE")
    url=second_evidence.get("sourceUrl")
    parsed=urllib.parse.urlsplit(url or "")
    if parsed.scheme!="https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("UNTRUSTED_SECOND_SOURCE")
    if parse_time(second_evidence["retrievedAt"])>parse_time(cutoff):
        raise ValueError("SECOND_SOURCE_AFTER_CUTOFF")
    try:
        raw=base64.b64decode(second_evidence["rawBodyBase64"],validate=True)
    except (TypeError,ValueError) as exc:
        raise ValueError("INVALID_SECOND_SOURCE_RAW") from exc
    if hashlib.sha256(raw).hexdigest()!=second_evidence.get("responseSha256"):
        raise ValueError("SECOND_SOURCE_HASH_MISMATCH")
    payload=json.loads(raw)
    if not isinstance(payload,dict) or not isinstance(payload.get("games"),list):
        raise ValueError("INVALID_SECOND_SOURCE_FORMAT")
    # Independent source may use its own IDs; match normalized kickoff and teams.
    def key(g):
        if not all(isinstance(g.get(k),str) and g[k] for k in ("date","home","away")):
            raise ValueError("INVALID_SECOND_SOURCE_GAME")
        return (parse_time(g["date"]),g["home"].strip().casefold(),g["away"].strip().casefold())
    first={key(g) for g in expected_schedule}
    second=[key(g) for g in payload["games"]]
    if len(first)!=len(expected_schedule) or len(second)!=len(set(second)) or first!=set(second):
        raise ValueError("INDEPENDENT_SCHEDULE_MISMATCH")
    return {**primary,"secondSourceUrl":url,
            "secondSourceRetrievedAt":second_evidence["retrievedAt"],
            "secondSourceSha256":second_evidence["responseSha256"],
            "independentSourceVerified":True}
