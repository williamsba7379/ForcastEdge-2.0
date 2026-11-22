#!/usr/bin/env python3
"""Research-only, fail-closed structural and provenance validation; never runs models."""
import datetime as dt
import hashlib
import json
from pathlib import Path

MODELS = ("A", "B", "C", "C-QB")
PUBLISHER = "nfl-official-wednesday"
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing timestamp")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return t.astimezone(dt.timezone.utc)
def evidence(value, deadline):
    if not isinstance(value, dict) or set(value) != {"source", "capturedAt", "sha256"}:
        raise ValueError("Evidence fields missing or unexpected")
    if not isinstance(value["source"], str) or not value["source"].strip():
        raise ValueError("Evidence source missing")
    if not isinstance(value["sha256"], str) or len(value["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in value["sha256"]):
        raise ValueError("Invalid SHA-256")
    if timestamp(value["capturedAt"]) > deadline:
        raise ValueError("Evidence captured after freeze")
def validate(card, schedule, schema):
    if not isinstance(card, dict) or not isinstance(schedule, dict):
        raise ValueError("Card and schedule must be objects")
    # No external JSON-schema library is required: strict structural checks are below.
    if set(card) != set(schema["required"]):
        raise ValueError("Card schema keys differ")
    if card["schemaVersion"] != "1.0" or card["publisherId"] != PUBLISHER:
        raise ValueError("Unexpected schema or publisher")
    if type(card["season"]) is not int or type(card["week"]) is not int or not 1 <= card["week"] <= 18:
        raise ValueError("Invalid season/week")
    if not isinstance(card["cardId"], str) or not card["cardId"].strip():
        raise ValueError("Missing card ID")
    if card["season"] != schedule.get("season") or card["week"] != schedule.get("week"):
        raise ValueError("Schedule season/week mismatch")
    cutoff = timestamp(card["cutoffAt"])
    frozen = timestamp(card["frozenAt"])
    published = timestamp(card["publishedAt"])
    if published < frozen:
        raise ValueError("Publication precedes freeze")
    if frozen > cutoff and card["status"] != "FROZEN_LATE":
        raise ValueError("Late card incorrectly labeled on time")
    if frozen <= cutoff and card["status"] != "FROZEN_ON_TIME":
        raise ValueError("On-time card incorrectly labeled late")
    from zoneinfo import ZoneInfo
    local = cutoff.astimezone(ZoneInfo("America/New_York"))
    if local.weekday() != 2 or (local.hour, local.minute, local.second, local.microsecond) != (11, 0, 0, 0):
        raise ValueError("Cutoff must be Wednesday 11:00 America/New_York")
    if card["inputManifestHash"] != digest(schedule):
        raise ValueError("Schedule manifest digest mismatch")
    if not isinstance(card["games"], list) or not card["games"]:
        raise ValueError("Missing games")
    expected = schedule.get("games")
    if not isinstance(expected, list) or not expected:
        raise ValueError("Missing independently approved schedule games")
    expected_ids = [str(g["id"]) for g in expected]
    actual_ids = [g.get("gameId") for g in card["games"]]
    if len(set(expected_ids)) != len(expected_ids) or len(set(actual_ids)) != len(actual_ids) or set(expected_ids) != set(actual_ids):
        raise ValueError("Incomplete, duplicate or extra games")
    reference = {str(g["id"]):g for g in expected}
    for game in card["games"]:
        if set(game) != {"gameId", "kickoffAt", "homeTeam", "awayTeam", "qbEvidence", "models"}:
            raise ValueError("Unexpected game keys")
        original = reference[game["gameId"]]
        if game["homeTeam"] != original["home"] or game["awayTeam"] != original["away"] or timestamp(game["kickoffAt"]) != timestamp(original["date"]):
            raise ValueError("Game identity mismatch")
        if timestamp(game["kickoffAt"]) <= frozen:
            raise ValueError("Kickoff not after freeze")
        evidence(game["qbEvidence"], frozen)
        if not isinstance(game["models"], dict) or set(game["models"]) != set(MODELS):
            raise ValueError("Missing four-model rows")
        for name in MODELS:
            m = game["models"][name]
            if not isinstance(m, dict) or set(m) != {"moneylineWinner","spreadPick","spreadLine","totalPick","totalLine","projectedHomeScore","projectedAwayScore","confidence","wagerStatus","marketEvidence","modelEvidence"}:
                raise ValueError("Missing model fields")
            if m["moneylineWinner"] not in (game["homeTeam"], game["awayTeam"]) or m["spreadPick"] not in (game["homeTeam"], game["awayTeam"]):
                raise ValueError("Invalid winner/spread team")
            if m["totalPick"] not in ("OVER", "UNDER") or m["wagerStatus"] != "NO BET":
                raise ValueError("Invalid total or unauthorized wager classification")
            for field in ("spreadLine","totalLine","projectedHomeScore","projectedAwayScore","confidence"):
                v = m[field]
                if type(v) not in (int,float) or not __import__("math").isfinite(v):
                    raise ValueError("Invalid numeric field")
            if m["projectedHomeScore"] < 0 or m["projectedAwayScore"] < 0 or not 0 <= m["confidence"] <= 1:
                raise ValueError("Invalid projection/confidence")
            evidence(m["marketEvidence"], frozen)
            evidence(m["modelEvidence"], frozen)
    core = {k:v for k,v in card.items() if k != "cardHash"}
    if card["cardHash"] != digest(core):
        raise ValueError("Card content hash mismatch")
    return True
def validate_files(card_path, schedule_path, schema_path):
    card = json.loads(Path(card_path).read_text())
    schedule = json.loads(Path(schedule_path).read_text())
    schema = json.loads(Path(schema_path).read_text())
    validate(card, schedule, schema)
    return card
