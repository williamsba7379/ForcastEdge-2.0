"""Independent, read-only ESPN schedule provenance for Wednesday A/B research.

The caller supplies raw bytes and a retrieval timestamp observed at fetch time.
Never treats an unverified local schedule or a later response as a freeze.
"""
import base64
import hashlib
import json
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_strict_replay import canonical

ESPN_SCHEDULE_URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def capture_schedule_response(raw_body, retrieved_at, source_url=ESPN_SCHEDULE_URL):
    if not isinstance(raw_body,bytes) or not raw_body:
        raise ValueError("MISSING_RAW_SCHEDULE_RESPONSE")
    if not isinstance(source_url,str) or not source_url.startswith(ESPN_SCHEDULE_URL):
        raise ValueError("UNTRUSTED_SCHEDULE_SOURCE")
    parse_time(retrieved_at)
    payload=json.loads(raw_body)
    if not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
        raise ValueError("INVALID_SCHEDULE_RESPONSE")
    return {"schemaVersion":1,"sourceUrl":source_url,"retrievedAt":retrieved_at,
            "responseSha256":hashlib.sha256(raw_body).hexdigest(),
            "rawBodyBase64":base64.b64encode(raw_body).decode("ascii")}

def verify_schedule_evidence(evidence, cutoff, expected_schedule):
    if not isinstance(evidence,dict) or evidence.get("schemaVersion")!=1:
        raise ValueError("MISSING_SCHEDULE_PROVENANCE")
    url=evidence.get("sourceUrl")
    if not isinstance(url,str) or not url.startswith(ESPN_SCHEDULE_URL):
        raise ValueError("UNTRUSTED_SCHEDULE_SOURCE")
    if parse_time(evidence["retrievedAt"])>parse_time(cutoff):
        raise ValueError("SCHEDULE_AFTER_CUTOFF")
    try:
        raw=base64.b64decode(evidence["rawBodyBase64"],validate=True)
    except (ValueError,TypeError) as exc:
        raise ValueError("INVALID_RAW_SCHEDULE_EVIDENCE") from exc
    if hashlib.sha256(raw).hexdigest()!=evidence.get("responseSha256"):
        raise ValueError("SCHEDULE_HASH_MISMATCH")
    payload=json.loads(raw)
    events=payload.get("events")
    if not isinstance(events,list):
        raise ValueError("INVALID_SCHEDULE_RESPONSE")
    observed={}
    for e in events:
        try:
            sides=e["competitions"][0]["competitors"]
            home=next(x for x in sides if x["homeAway"]=="home")
            away=next(x for x in sides if x["homeAway"]=="away")
            row={"id":str(e["id"]),"date":e["date"],
                 "home":home["team"]["displayName"],"away":away["team"]["displayName"]}
        except (KeyError,IndexError,StopIteration,TypeError) as exc:
            raise ValueError("INVALID_SCHEDULE_EVENT") from exc
        if row["id"] in observed:
            raise ValueError("DUPLICATE_SCHEDULE_EVENT")
        observed[row["id"]]=row
    expected={str(g["id"]):g for g in expected_schedule}
    if len(expected)!=len(expected_schedule) or set(expected)!=set(observed):
        raise ValueError("SCHEDULE_COVERAGE_MISMATCH")
    for ident,row in observed.items():
        source=expected[ident]
        if any(row[k]!=source[k] for k in ("date","home","away")):
            raise ValueError("SCHEDULE_IDENTITY_MISMATCH")
        if parse_time(row["date"])<=parse_time(cutoff):
            raise ValueError("EXPECTED_GAME_NOT_FUTURE")
    return {"scheduleResponseSha256":evidence["responseSha256"],
            "scheduleRetrievedAt":evidence["retrievedAt"],
            "expectedScheduleSha256":hashlib.sha256(canonical(expected_schedule)).hexdigest(),
            "gameCount":len(observed)}
