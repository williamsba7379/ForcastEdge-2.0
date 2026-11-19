"""Offline synthetic-only score evidence validator. No network, filesystem or production imports."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
HEX = re.compile(r"^[0-9a-f]{64}$")
class EvidenceError(ValueError):
    def __init__(self, code, field):
        self.code, self.field = code, field
        super().__init__(f"{code}:{field}")

def canonical(value):
    """Conservative JCS-compatible subset: no floats, no surrogate characters, no duplicate JSON keys."""
    def check(x):
        if x is None or isinstance(x, (str, bool, int)):
            if isinstance(x, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in x):
                raise EvidenceError("E002_CANONICAL_INVALID", "unicode")
            return
        if isinstance(x, list):
            for y in x: check(y)
            return
        if isinstance(x, dict) and all(isinstance(k, str) for k in x):
            for k, v in x.items(): check(k); check(v)
            return
        raise EvidenceError("E002_CANONICAL_INVALID", "value")
    check(value)
    # Restricted RFC 8785 subset: reject unsafe integers and unsupported floats.
    def safe(x):
        if type(x) is int and abs(x) > 9007199254740991:
            raise EvidenceError("E002_CANONICAL_INVALID", "unsafe_integer")
        if isinstance(x, list):
            for y in x: safe(y)
        if isinstance(x, dict):
            for y in x.values(): safe(y)
    safe(value)
    # JCS sorts property names by UTF-16 code units.
    def ordered(x):
        if isinstance(x, dict):
            return {k: ordered(x[k]) for k in sorted(x, key=lambda k: k.encode("utf-16-be"))}
        if isinstance(x, list): return [ordered(y) for y in x]
        return x
    return json.dumps(ordered(value), sort_keys=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def parse(raw):
    def pairs(p):
        d = {}
        for k, v in p:
            if k in d: raise EvidenceError("E001_SCHEMA_INVALID", k)
            d[k] = v
        return d
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except EvidenceError: raise
    except (ValueError, UnicodeError, TypeError) as exc:
        raise EvidenceError("E001_SCHEMA_INVALID", "json") from exc

def timestamp(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", s):
        raise EvidenceError("E007_TIME_CONFLICT", "timestamp")
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc: raise EvidenceError("E007_TIME_CONFLICT", "timestamp") from exc

def cutoff(day):
    try:
        d = date.fromisoformat(day)
        if d.weekday() != 2: raise ValueError("not Wednesday")
        return datetime(d.year, d.month, d.day, 11, tzinfo=ZoneInfo("America/New_York")).astimezone(UTC)
    except ValueError as exc: raise EvidenceError("E001_SCHEMA_INVALID", "freezeDate") from exc

def validate(payload_bytes, responses, schedule_bytes, attestation, artifact_bytes=None):
    """Pure function. Inputs are caller-provided bytes/dicts; returns sorted error codes."""
    errors = set()
    def flag(code): errors.add(code)
    try:
        p = parse(payload_bytes)
        s = parse(schedule_bytes)
        if not isinstance(p, dict) or not isinstance(s, dict): raise EvidenceError("E001_SCHEMA_INVALID", "root")
        if p.get("schemaVersion") != "1.2-synthetic" or p.get("purpose") != "research-ab-score-snapshot":
            flag("E001_SCHEMA_INVALID")
        if canonical(p) != payload_bytes: flag("E002_CANONICAL_INVALID")
        if canonical(s) != schedule_bytes: flag("E002_CANONICAL_INVALID")
        limit = cutoff(p["freezeDate"])
        if p.get("cutoffUtc") != limit.strftime("%Y-%m-%dT%H:%M:%S.000Z"): flag("E007_TIME_CONFLICT")
        if digest(schedule_bytes) != p.get("scheduleSha256"): flag("E014_SCHEDULE_INVALID")
        if attestation.get("capturePayloadSha256") != digest(payload_bytes): flag("E015_PAYLOAD_HASH_MISMATCH")
        if attestation.get("scheduleSha256") != digest(schedule_bytes): flag("E014_SCHEDULE_INVALID")
        # Synthetic trust anchor: explicit fixture marker, never accepted as real-world timestamp proof.
        if attestation.get("kind") != "SYNTHETIC_TEST_ONLY" or attestation.get("proof") != "SYNTHETIC_VALID":
            flag("E017_ATTESTATION_INVALID")
        if attestation.get("timingClassification") != "SYNTHETIC_VERIFIED": flag("E006_TIME_UNVERIFIED")
        # Digest-bound synthetic seal is a test fixture, NOT real timestamp authentication.
        seal = attestation.get("syntheticSeal", {})
        expected_seal = digest(canonical({
            "capturePayloadSha256": digest(payload_bytes),
            "scheduleSha256": digest(schedule_bytes),
            "sealedAtUtc": seal.get("sealedAtUtc"),
            "kind": "SYNTHETIC_TEST_ONLY"
        }))
        if seal.get("bindingSha256") != expected_seal:
            flag("E017_ATTESTATION_INVALID")
        else:
            if timestamp(seal["sealedAtUtc"]) > limit: flag("E005_CAPTURE_LATE")
        schedule_capture = p.get("scheduleCapture")
        if not isinstance(schedule_capture, dict):
            flag("E014_SCHEDULE_INVALID")
        else:
            if schedule_capture.get("responseSha256") != digest(schedule_bytes):
                flag("E014_SCHEDULE_INVALID")
            try:
                if timestamp(schedule_capture["completedAtUtc"]) > limit:
                    flag("E005_CAPTURE_LATE")
            except (KeyError, EvidenceError):
                flag("E014_SCHEDULE_INVALID")
        if artifact_bytes is not None and digest(artifact_bytes) != attestation.get("artifactSha256"):
            flag("E016_ARTIFACT_INVALID")
        elif artifact_bytes is None and attestation.get("artifactSha256") is not None:
            flag("E016_ARTIFACT_INVALID")
        # An in-memory digest cannot establish external retention or immutability.
        if attestation.get("retentionProof") not in (None, "SYNTHETIC_TEST_ONLY"):
            flag("E016_ARTIFACT_INVALID")
        response_map = {}
        for r in p["responses"]:
            rid = r["responseId"]
            if rid in response_map: flag("E011_GAME_CONFLICT")
            response_map[rid] = r
            if rid not in responses: flag("E004_SOURCE_MISSING"); continue
            raw = responses[rid]
            if digest(raw) != r["sha256"] or len(raw) != r["byteLength"]: flag("E003_SOURCE_HASH_MISMATCH")
            if not r["url"].startswith("synthetic://"): flag("E018_ISOLATION_VIOLATION")
            start, end = timestamp(r["requestStartedUtc"]), timestamp(r["responseCompletedUtc"])
            if start > end: flag("E007_TIME_CONFLICT")
            if end > limit: flag("E005_CAPTURE_LATE")
        if set(responses) != set(response_map): flag("E013_COVERAGE_UNEXPECTED")
        expected = {}
        for event in s["events"]:
            gid = str(event["id"])
            if gid in expected: flag("E010_GAME_DUPLICATE")
            expected[gid] = event
        # Reconcile all retained observations, including unselected responses.
        observations = {}
        for rid, raw in responses.items():
            try:
                source = parse(raw)
                response_seen = set()
                for event in source["events"]:
                    gid = str(event["id"])
                    if gid in response_seen: flag("E010_GAME_DUPLICATE")
                    response_seen.add(gid)
                    comp = event["competitions"][0]["competitors"]
                    home = next(c for c in comp if c["homeAway"] == "home")
                    away = next(c for c in comp if c["homeAway"] == "away")
                    signature = (home["team"]["id"], away["team"]["id"],
                                 home["score"], away["score"],
                                 event.get("status", {}).get("type", {}).get("completed"))
                    if gid in observations and observations[gid] != signature:
                        flag("E011_GAME_CONFLICT")
                    observations[gid] = signature
            except (KeyError, IndexError, TypeError, StopIteration, EvidenceError):
                flag("E001_SCHEMA_INVALID")
        seen = set()
        for g in p["games"]:
            gid, rid = str(g["gameId"]), g["responseId"]
            if gid in seen: flag("E010_GAME_DUPLICATE")
            seen.add(gid)
            if gid not in expected: flag("E013_COVERAGE_UNEXPECTED"); continue
            ev = expected[gid]
            for key, field in [("homeTeamId","homeTeamId"),("awayTeamId","awayTeamId"),("kickoffUtc","kickoffUtc")]:
                if g[key] != ev[field]: flag("E011_GAME_CONFLICT")
            if rid not in responses: flag("E004_SOURCE_MISSING"); continue
            try:
                source = parse(responses[rid])
                matching = [e for e in source["events"] if str(e.get("id")) == gid]
                if len(matching) != 1: flag("E011_GAME_CONFLICT"); continue
                e = matching[0]
                if e.get("status", {}).get("type", {}).get("completed") is not True:
                    flag("E008_STATUS_NOT_FINAL")
                comp = e["competitions"][0]["competitors"]
                home = [x for x in comp if x["homeAway"] == "home"]
                away = [x for x in comp if x["homeAway"] == "away"]
                if len(home) != 1 or len(away) != 1: flag("E011_GAME_CONFLICT"); continue
                h, a = home[0], away[0]
                if h["team"]["id"] != g["homeTeamId"] or a["team"]["id"] != g["awayTeamId"]:
                    flag("E011_GAME_CONFLICT")
                hs, az = h["score"], a["score"]
                if type(hs) is not int or type(az) is not int or hs < 0 or az < 0: flag("E009_SCORE_INVALID")
                elif (hs, az, h["team"]["id"] if hs > az else a["team"]["id"] if az > hs else None) != (g["homeScore"], g["awayScore"], g["winnerTeamId"]):
                    flag("E011_GAME_CONFLICT")
                if timestamp(g["kickoffUtc"]) > limit: flag("E013_COVERAGE_UNEXPECTED")
            except (KeyError, IndexError, TypeError, EvidenceError):
                flag("E001_SCHEMA_INVALID")
        for gid, event in expected.items():
            if gid not in seen and event.get("state") == "FINAL":
                flag("E012_COVERAGE_MISSING")
            if gid in seen and event.get("state") != "FINAL":
                flag("E013_COVERAGE_UNEXPECTED")
        if set(p.get("excludedGameIds", [])) != set(expected)-seen:
            flag("E012_COVERAGE_MISSING")
    except EvidenceError as exc: flag(exc.code)
    except (KeyError, TypeError, AttributeError, ValueError, IndexError): flag("E001_SCHEMA_INVALID")
    return {"passed": not errors, "errors": sorted(errors), "syntheticOnly": True}
