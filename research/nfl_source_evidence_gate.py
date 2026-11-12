"""Research-only verification of immutable Wednesday input evidence.

Never fetches, writes, freezes or publishes. All payloads are supplied by caller.
Evidence schemas here are isolated test contracts, not production data formats.
"""
import datetime as dt
import hashlib
import json
import re
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")

def timestamp(value):
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return t.astimezone(UTC)

def require_hash(raw, claimed):
    if not isinstance(raw, bytes) or not re.fullmatch(r"[0-9a-f]{64}", str(claimed)):
        raise ValueError("INVALID_HASH_EVIDENCE")
    if hashlib.sha256(raw).hexdigest() != claimed:
        raise ValueError("SOURCE_HASH_MISMATCH")

def check_window(captured, cutoff):
    if not cutoff - dt.timedelta(hours=24) <= timestamp(captured) <= cutoff:
        raise ValueError("EVIDENCE_OUTSIDE_CUTOFF_WINDOW")

def verify_schedule(evidence, cutoff):
    if not evidence.get("source") or not evidence.get("raw"):
        raise ValueError("SCHEDULE_SOURCE_MISSING")
    require_hash(evidence["raw"], evidence["sha256"])
    check_window(evidence["capturedAt"], cutoff)
    payload = json.loads(evidence["raw"])
    if payload.get("season") is None or payload.get("week") is None:
        raise ValueError("SCHEDULE_WEEK_MISSING")
    games = payload.get("games", [])
    if not games or len({str(g["id"]) for g in games}) != len(games):
        raise ValueError("INVALID_SCHEDULE_GAMES")
    slate = sorted((str(g["id"]), g["home"], g["away"], timestamp(g["date"]).isoformat()) for g in games)
    return (payload["season"], payload["week"]), slate, games

def verify(*, schedule_a, schedule_b, qb, markets, cutoff):
    """Fail closed with no side effects. Returns research status, never readiness."""
    cutoff = timestamp(cutoff)
    local = cutoff.astimezone(ET)
    if local.weekday() != 2 or local.time() != dt.time(11):
        raise ValueError("INVALID_WEDNESDAY_CUTOFF")
    if schedule_a.get("source") == schedule_b.get("source"):
        raise ValueError("INDEPENDENT_SOURCES_REQUIRED")
    week_a, slate_a, games = verify_schedule(schedule_a, cutoff)
    week_b, slate_b, _ = verify_schedule(schedule_b, cutoff)
    if week_a != week_b or slate_a != slate_b:
        raise ValueError("SCHEDULE_DISAGREEMENT")
    ids = {g[0] for g in slate_a}
    if (markets.get("season"), markets.get("week")) != week_a:
        raise ValueError("MARKET_WEEK_MISMATCH")
    market_games = markets.get("games", [])
    if len(market_games) != len(ids) or {str(m["id"]) for m in market_games} != ids:
        raise ValueError("MARKET_COVERAGE_MISSING")
    for market in market_games:
        if not market.get("provider") or not market.get("source"):
            raise ValueError("MARKET_PROVENANCE_MISSING")
        if not isinstance(market.get("spread"), (int, float)) or not isinstance(market.get("total"), (int, float)):
            raise ValueError("MARKET_LINE_MISSING")
        check_window(market["capturedAt"], cutoff)
    expected_sides = {(str(g["id"]), side) for g in games for side in ("home", "away")}
    actual_sides = {(str(q["gameId"]), q["side"]) for q in qb}
    if len(qb) != len(expected_sides) or actual_sides != expected_sides:
        raise ValueError("QB_EVIDENCE_MISSING")
    for item in qb:
        if item.get("verification") != "OFFICIAL_GAME_SPECIFIC" or not item.get("source") or not item.get("starter"):
            raise ValueError("QB_NOT_OFFICIALLY_VERIFIED")
        check_window(item["capturedAt"], cutoff)
    return {"status": "RESEARCH_EVIDENCE_PASS", "productionReady": False,
            "season": week_a[0], "week": week_a[1], "games": len(ids),
            "verifiedQbSides": len(expected_sides), "marketGames": len(market_games)}
