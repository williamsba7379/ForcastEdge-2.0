"""Fail-closed, read-only release eligibility for a four-model Wednesday card.

This is a review-branch contract, not production certification.
"""
import datetime as dt
import hashlib
import json
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")


def timestamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return parsed.astimezone(UTC)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(schedule, card, evidence, *, now=None):
    now = now or dt.datetime.now(UTC)
    now = now.astimezone(UTC)
    errors = []
    local = now.astimezone(ET)
    if local.weekday() != 2 or (local.hour, local.minute) >= (11, 0):
        errors.append("OUTSIDE_WEDNESDAY_PREDELIVERY_WINDOW")
    thursday = local.date() + dt.timedelta(days=1)
    monday = thursday + dt.timedelta(days=4)
    weeks = [w for w in schedule.get("weeks", []) if any(
        thursday <= timestamp(g["date"]).astimezone(ET).date() <= monday
        for g in w.get("games", []))]
    if len(weeks) != 1:
        return {"status": "DELIVERY_BLOCKED", "errors": ["AMBIGUOUS_OR_MISSING_WEEK"]}
    week = weeks[0]
    games = week.get("games", [])
    expected = {str(g["id"]): g for g in games}
    rows = card.get("games", []) if isinstance(card, dict) else []
    actual = {str(g.get("id")): g for g in rows}
    if len(expected) != len(games) or not games or len(actual) != len(rows) or set(actual) != set(expected):
        errors.append("INCOMPLETE_OR_DUPLICATE_GAME_COVERAGE")
    if card.get("season") != schedule.get("season") or card.get("week") != week.get("week"):
        errors.append("WRONG_SEASON_OR_WEEK")
    if card.get("status") in ("AUTOMATED_REVIEW_ONLY", "EXPERIMENTAL_SHADOW_ONLY", "RESEARCH_ONLY_NOT_DELIVERABLE"):
        errors.append("REVIEW_ONLY_CARD")
    for game_id, game in expected.items():
        if not thursday <= timestamp(game["date"]).astimezone(ET).date() <= monday:
            errors.append("OUTSIDE_THURSDAY_MONDAY_SLATE:" + game_id)
        row = actual.get(game_id, {})
        if any(row.get(k) != game.get(k) for k in ("away", "home", "date")):
            errors.append("GAME_IDENTITY_MISMATCH:" + game_id)
        picks = row.get("picks", {})
        if set(picks) != set(MODELS):
            errors.append("MODEL_COVERAGE:" + game_id)
        for model in MODELS:
            item = (evidence.get(game_id, {}) or {}).get(model, {})
            if picks.get(model) not in (game.get("away"), game.get("home")):
                errors.append("INVALID_WINNER:" + game_id + ":" + model)
            required = ("projectedAwayScore", "projectedHomeScore", "projectedMargin",
                        "projectedTotal", "confidence", "spreadPick", "totalPick",
                        "marketSpread", "marketTotal", "marketCapturedAt",
                        "generatedAt", "modelArtifactId", "engineSha256", "inputSha256")
            if any(item.get(k) is None for k in required):
                errors.append("MISSING_EVIDENCE:" + game_id + ":" + model)
                continue
            try:
                generated = timestamp(item["generatedAt"])
                market = timestamp(item["marketCapturedAt"])
                kickoff = timestamp(game["date"])
                if not (generated <= now and generated < kickoff and market <= now and market < kickoff):
                    errors.append("STALE_OR_FUTURE_TIMESTAMP:" + game_id + ":" + model)
                if any(not isinstance(item[k], (int, float)) or isinstance(item[k], bool)
                       for k in ("projectedAwayScore", "projectedHomeScore", "projectedMargin", "projectedTotal", "confidence")):
                    errors.append("NONNUMERIC_PROJECTION:" + game_id + ":" + model)
                if not 0 <= item["confidence"] <= 1:
                    errors.append("INVALID_CONFIDENCE:" + game_id + ":" + model)
                if abs(item["projectedAwayScore"] + item["projectedHomeScore"] - item["projectedTotal"]) > 0.01:
                    errors.append("TOTAL_INCONSISTENT:" + game_id + ":" + model)
                if abs(item["projectedHomeScore"] - item["projectedAwayScore"] - item["projectedMargin"]) > 0.01:
                    errors.append("MARGIN_INCONSISTENT:" + game_id + ":" + model)
                for field in ("engineSha256", "inputSha256"):
                    if len(str(item[field])) != 64 or any(c not in "0123456789abcdef" for c in str(item[field]).lower()):
                        errors.append("INVALID_HASH:" + game_id + ":" + model)
                if model in ("C", "C-QB") and not item.get("officialGameSpecificQB"):
                    errors.append("UNVERIFIED_QB:" + game_id + ":" + model)
                if not item.get("independentSourceVerified"):
                    errors.append("SOURCE_NOT_VERIFIED:" + game_id + ":" + model)
            except (ValueError, TypeError, KeyError):
                errors.append("INVALID_EVIDENCE:" + game_id + ":" + model)
    return {"status": "PASS" if not errors else "DELIVERY_BLOCKED",
            "season": schedule.get("season"), "week": week.get("week"),
            "expectedGames": len(games), "expectedRows": 4 * len(games),
            "errors": sorted(set(errors))}
