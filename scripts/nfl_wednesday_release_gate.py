"""Review-only fail-closed eligibility. Evidence is checked against independently pinned bytes."""
import datetime as dt
import hashlib
import json
import math
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")
REQUIRED = ("projectedAwayScore", "projectedHomeScore", "projectedMargin",
            "projectedTotal", "confidence", "spreadPick", "totalPick",
            "marketSpread", "marketTotal", "marketCapturedAt", "generatedAt",
            "modelArtifactId", "engineSha256", "inputSha256")


def blocked(*reasons):
    return {"status": "DELIVERY_BLOCKED", "errors": sorted(set(reasons))}


def timestamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return parsed.astimezone(UTC)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def verify_sources(item, sources, game_id, model):
    """sources are independently supplied byte blobs and separately pinned expected hashes.

    Merely setting independentSourceVerified or providing an unpinned hash is insufficient.
    The caller must acquire the expected digests from an independently trusted channel.
    """
    entry = sources.get(game_id, {}).get(model) if isinstance(sources, dict) else None
    if not isinstance(entry, dict):
        return False
    for label, field in (("engine", "engineSha256"), ("input", "inputSha256"),
                         ("modelArtifact", "modelArtifactSha256")):
        data = entry.get(label + "Bytes")
        pinned = entry.get(label + "PinnedSha256")
        if not isinstance(data, bytes) or not valid_sha(pinned):
            return False
        actual = hashlib.sha256(data).hexdigest()
        if actual != pinned:
            return False
        if label == "modelArtifact":
            if item.get(field) != pinned:
                return False
        elif item.get(field) != pinned:
            return False
    if not entry.get("independentAuthorityId") or not entry.get("independentReceiptId"):
        return False
    return True


def validate(schedule, card, evidence, *, now=None, sources=None):
    if not all(isinstance(obj, dict) for obj in (schedule, card, evidence)):
        return blocked("MALFORMED_INPUT")
    try:
        now = timestamp(now or dt.datetime.now(UTC).isoformat())
        local = now.astimezone(ET)
        if local.weekday() != 2 or (local.hour, local.minute) >= (11, 0):
            return blocked("OUTSIDE_WEDNESDAY_PREDELIVERY_WINDOW")
        thursday = local.date() + dt.timedelta(days=1)
        monday = thursday + dt.timedelta(days=4)
        weeks = schedule.get("weeks")
        if not isinstance(weeks, list) or not weeks:
            return blocked("INVALID_SCHEDULE")
        matching = []
        for week in weeks:
            if not isinstance(week, dict) or not isinstance(week.get("games"), list):
                return blocked("INVALID_SCHEDULE")
            for game in week["games"]:
                if not isinstance(game, dict) or not all(k in game for k in ("id", "date", "home", "away")):
                    return blocked("INVALID_SCHEDULE")
                if thursday <= timestamp(game["date"]).astimezone(ET).date() <= monday:
                    matching.append(week)
                    break
        if len(matching) != 1:
            return blocked("MISSING_OR_AMBIGUOUS_UPCOMING_WEEK")
        week = matching[0]
        games = week["games"]
        ids = [str(g["id"]) for g in games]
        if not ids or len(ids) != len(set(ids)):
            return blocked("DUPLICATE_OR_EMPTY_SCHEDULE")
        if any(not thursday <= timestamp(g["date"]).astimezone(ET).date() <= monday for g in games):
            return blocked("SCHEDULE_OUTSIDE_SLATE")
        rows = card.get("games")
        if not isinstance(rows, list) or any(not isinstance(r, dict) or "id" not in r for r in rows):
            return blocked("INVALID_CARD")
        actual = {str(r["id"]): r for r in rows}
        if len(actual) != len(rows) or set(actual) != set(ids):
            return blocked("FOUR_MODEL_GAME_COVERAGE_INVALID")
        if (card.get("season"), card.get("week")) != (schedule.get("season"), week.get("week")):
            return blocked("WRONG_SEASON_OR_WEEK")
        if card.get("status") in ("AUTOMATED_REVIEW_ONLY", "EXPERIMENTAL_SHADOW_ONLY", "RESEARCH_ONLY_NOT_DELIVERABLE"):
            return blocked("REVIEW_ONLY_CARD")
        issues = []
        for game in games:
            gid = str(game["id"])
            row = actual[gid]
            if any(row.get(k) != game[k] for k in ("date", "home", "away")):
                issues.append("GAME_IDENTITY_MISMATCH:" + gid)
            picks = row.get("picks")
            if not isinstance(picks, dict) or set(picks) != set(MODELS):
                issues.append("MODEL_COVERAGE:" + gid)
                continue
            for model in MODELS:
                prefix = gid + ":" + model
                item = evidence.get(gid, {}).get(model) if isinstance(evidence.get(gid), dict) else None
                if not isinstance(item, dict) or any(item.get(k) is None for k in REQUIRED):
                    issues.append("MISSING_EVIDENCE:" + prefix)
                    continue
                if picks[model] not in (game["away"], game["home"]):
                    issues.append("INVALID_WINNER:" + prefix)
                if not all(finite(item[k]) for k in ("projectedAwayScore", "projectedHomeScore", "projectedMargin",
                                                    "projectedTotal", "confidence", "marketSpread", "marketTotal")):
                    issues.append("NONFINITE_NUMBER:" + prefix)
                    continue
                if not 0 <= item["confidence"] <= 1:
                    issues.append("INVALID_CONFIDENCE:" + prefix)
                if abs(item["projectedAwayScore"] + item["projectedHomeScore"] - item["projectedTotal"]) > .01:
                    issues.append("INCONSISTENT_TOTAL:" + prefix)
                if abs(item["projectedHomeScore"] - item["projectedAwayScore"] - item["projectedMargin"]) > .01:
                    issues.append("INCONSISTENT_MARGIN:" + prefix)
                if not item.get("spreadPick") or item.get("totalPick") not in ("Over", "Under", "Push"):
                    issues.append("INVALID_MARKET_PICK:" + prefix)
                if not item.get("marketSource") or not item.get("marketSourceId"):
                    issues.append("UNSOURCED_MARKET:" + prefix)
                if model in ("C", "C-QB") and not item.get("officialGameSpecificQB"):
                    issues.append("UNVERIFIED_QB:" + prefix)
                if not verify_sources(item, sources, gid, model):
                    issues.append("UNVERIFIED_PROVENANCE:" + prefix)
                if not (timestamp(item["generatedAt"]) <= now and timestamp(item["generatedAt"]) < timestamp(game["date"])
                        and timestamp(item["marketCapturedAt"]) <= now and timestamp(item["marketCapturedAt"]) < timestamp(game["date"])):
                    issues.append("INVALID_SOURCE_TIME:" + prefix)
        return {"status": "PASS" if not issues else "DELIVERY_BLOCKED",
                "season": schedule.get("season"), "week": week.get("week"),
                "expectedGames": len(games), "expectedRows": len(games) * len(MODELS),
                "errors": sorted(set(issues))}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return blocked("MALFORMED_INPUT_OR_TIMESTAMP")
