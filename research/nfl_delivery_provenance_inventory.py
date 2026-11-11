"""Research-only per-row provenance inventory. Never fabricates or publishes evidence."""
import datetime as dt
import json
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
ET = ZoneInfo("America/New_York")

def timestamp(value):
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t.astimezone(dt.timezone.utc) if t.tzinfo else None
    except (ValueError, TypeError):
        return None

def audit(schedule, card, now, *, evidence=None, qb_evidence=None, market_evidence=None):
    """Evidence is accepted only from explicitly supplied authentic records."""
    now = timestamp(now) if isinstance(now, str) else now.astimezone(dt.timezone.utc)
    local = now.astimezone(ET)
    if local.weekday() != 2:
        raise ValueError("WEDNESDAY_ONLY")
    cutoff = local.replace(hour=11, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)
    thursday = local.date() + dt.timedelta(days=1)
    monday = thursday + dt.timedelta(days=4)
    matches = [w for w in schedule.get("weeks", []) if any(thursday <= timestamp(g.get("date")).astimezone(ET).date() <= monday for g in w.get("games", []) if timestamp(g.get("date")))]
    if len(matches) != 1:
        raise ValueError("AMBIGUOUS_SCHEDULE")
    week = matches[0]
    games = week["games"]
    if len({str(g["id"]) for g in games}) != len(games) or any(not timestamp(g.get("date")) or not thursday <= timestamp(g["date"]).astimezone(ET).date() <= monday for g in games):
        raise ValueError("INVALID_GAME_COVERAGE")
    rows = {str(g["id"]): g for g in (card or {}).get("games", [])}
    if len(rows) != len((card or {}).get("games", [])):
        raise ValueError("DUPLICATE_CARD_IDS")
    result = []
    for game in games:
        gid = str(game["id"])
        card_row = rows.get(gid, {}) if (card or {}).get("week") == week["week"] and (card or {}).get("season") == schedule.get("season") else {}
        identity = all(card_row.get(k) == game.get(k) for k in ("id", "date", "home", "away"))
        for model in MODELS:
            e = (evidence or {}).get(gid, {}).get(model, {})
            m = (market_evidence or {}).get(gid, {}).get(model, {})
            q = (qb_evidence or {}).get(gid, {}).get(model, {})
            pick = card_row.get("picks", {}).get(model) if identity else None
            missing = []
            if pick not in (game["home"], game["away"]):
                missing.append("winner")
            for field in ("projectedAwayScore", "projectedHomeScore", "projectedMargin", "projectedTotal", "modelArtifactId", "engineSha256", "inputSha256", "confidence"):
                if e.get(field) is None or e.get(field) == "":
                    missing.append(field)
            for field in ("spreadPick", "totalPick", "spreadLine", "totalLine", "marketSource", "marketCapturedAt"):
                if m.get(field) is None or m.get(field) == "":
                    missing.append(field)
            generated = timestamp(e.get("generatedAt"))
            market_at = timestamp(m.get("marketCapturedAt"))
            if not generated or generated > cutoff or generated >= timestamp(game["date"]):
                missing.append("VERIFIED_PRE_11AM_MODEL_CAPTURE")
            if not market_at or market_at > cutoff or market_at >= timestamp(game["date"]):
                missing.append("VERIFIED_PRE_11AM_MARKET_CAPTURE")
            if model in ("C", "C-QB") and not q.get("officialGameSpecific"):
                missing.append("OFFICIAL_GAME_SPECIFIC_QB")
            result.append({"gameId":gid, "away":game["away"], "home":game["home"], "kickoff":game["date"], "model":model, "winner":pick, "status":"PASS" if not missing else "MISSING_EVIDENCE", "missing":missing, "noBet":True})
    return {"status":"RESEARCH_ONLY_NOT_DELIVERABLE", "season":schedule.get("season"), "week":week["week"], "cutoffET":cutoff.astimezone(ET).isoformat(), "expectedGames":len(games), "expectedRows":len(games)*4, "rows":result, "completeRows":sum(r["status"]=="PASS" for r in result), "published":False, "historicalFreezeVerified":False}
