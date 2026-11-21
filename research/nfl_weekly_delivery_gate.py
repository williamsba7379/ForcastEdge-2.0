"""Fail-closed, read-only research gate for the Wednesday four-model handoff.

This is NOT connected to production publication. Independent schedule evidence must
be captured by a separate collector; matching copies of one source are insufficient.
"""
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MODELS = {"A", "B", "C", "C-QB"}

def instant(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return parsed.astimezone(dt.timezone.utc)

def identity(games):
    result = [(str(g["id"]), g["away"], g["home"], instant(g["date"])) for g in games]
    if not result or len(result) != len(set(result)) or len({g[0] for g in result}) != len(result):
        raise ValueError("INVALID_OR_DUPLICATE_SLATE")
    return sorted(result)

def validate(expected, independent, draft, shadow, card, market, cutoff):
    """Raise before any publication; never write or mutate inputs."""
    cutoff = instant(cutoff)
    local = cutoff.astimezone(ET)
    if local.weekday() != 2 or local.time() != dt.time(11):
        raise ValueError("INVALID_WEDNESDAY_CUTOFF")
    if expected.get("source") == independent.get("source") or not expected.get("source") or not independent.get("source"):
        raise ValueError("INDEPENDENT_SCHEDULE_SOURCE_REQUIRED")
    if not expected.get("sha256") or not independent.get("sha256"):
        raise ValueError("SCHEDULE_HASH_MISSING")
    for source in (expected, independent):
        captured = instant(source["capturedAt"])
        if captured > cutoff or captured < cutoff - dt.timedelta(hours=24):
            raise ValueError("SCHEDULE_CAPTURE_OUTSIDE_WINDOW")
    key = (expected["season"], expected["week"])
    if (independent["season"], independent["week"]) != key:
        raise ValueError("INDEPENDENT_SCHEDULE_WEEK_MISMATCH")
    slate = identity(expected["games"])
    if identity(independent["games"]) != slate:
        raise ValueError("INDEPENDENT_SCHEDULE_MISMATCH")
    for game in expected["games"]:
        day = instant(game["date"]).astimezone(ET).date()
        if not (local.date() + dt.timedelta(days=1) <= day <= local.date() + dt.timedelta(days=5)):
            raise ValueError("NOT_THURSDAY_THROUGH_MONDAY")
    for name, item in (("MODEL_C", draft), ("MODEL_C_QB", shadow), ("CARD", card)):
        if (item["season"], item["week"]) != key:
            raise ValueError("STALE_WEEK_" + name)
        if identity(item["games"]) != slate:
            raise ValueError("SLATE_MISMATCH_" + name)
    if (market["season"], market["week"]) != key:
        raise ValueError("MARKET_WEEK_MISMATCH")
    for name, item in (("MODEL_C", draft), ("MODEL_C_QB", shadow)):
        if not (cutoff - dt.timedelta(hours=11) <= instant(item["generatedAt"]) <= cutoff):
            raise ValueError("STALE_OR_LATE_" + name)
    if instant(card["frozenAt"]) > cutoff:
        raise ValueError("LATE_CARD")
    if any(set(game.get("picks", {})) != MODELS for game in card["games"]):
        raise ValueError("INCOMPLETE_FOUR_MODEL_CARD")
    return {"status": "RESEARCH_GATE_PASS", "productionReady": False,
            "season": key[0], "week": key[1], "games": len(slate),
            "modelRows": len(slate) * len(MODELS)}
