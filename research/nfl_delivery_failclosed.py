"""Read-only, fail-closed NFL delivery validator. Never writes frozen records."""
import datetime as dt
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
ET = ZoneInfo("America/New_York")

def parse(value):
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return t.astimezone(dt.timezone.utc)

def validate(schedule, card, now, *, source_evidence=None, qb_evidence=None):
    now = parse(now) if isinstance(now, str) else now.astimezone(dt.timezone.utc)
    local = now.astimezone(ET)
    thursday = local.date() + dt.timedelta(days=(3 - local.weekday()) % 7)
    monday = thursday + dt.timedelta(days=4)
    issues = []
    weeks = [w for w in schedule.get("weeks", []) if any(
        thursday <= parse(g["date"]).astimezone(ET).date() <= monday
        for g in w.get("games", []))]
    if len(weeks) != 1:
        issues.append("MISSING_OR_AMBIGUOUS_UPCOMING_WEEK")
        return {"status": "FAILED_COMPLETENESS_CHECK", "issues": issues}
    week = weeks[0]
    expected = [g for g in week["games"] if thursday <= parse(g["date"]).astimezone(ET).date() <= monday]
    if len(expected) != len(week["games"]) or len({str(g["id"]) for g in expected}) != len(expected):
        issues.append("SCHEDULE_COVERAGE_INVALID")
    if card is None or (card.get("season"), card.get("week")) != (schedule.get("season"), week["week"]):
        issues.append("MISSING_OR_STALE_FROZEN_CARD")
        card = {}
    rows = {str(g["id"]): g for g in card.get("games", [])}
    if len(rows) != len(card.get("games", [])) or set(rows) != {str(g["id"]) for g in expected}:
        issues.append("FOUR_MODEL_GAME_COVERAGE_INVALID")
    valid = 0
    unavailable = []
    for game in expected:
        row = rows.get(str(game["id"]), {})
        if row.get("away") != game["away"] or row.get("home") != game["home"] or row.get("date") != game["date"]:
            issues.append("GAME_IDENTITY_MISMATCH:" + str(game["id"]))
        for model in MODELS:
            pick = row.get("picks", {}).get(model)
            evidence = (source_evidence or {}).get(str(game["id"]), {}).get(model, {})
            qb = (qb_evidence or {}).get(str(game["id"]), {}).get(model, {})
            required = ("projectedAwayScore", "projectedHomeScore", "projectedMargin",
                        "projectedTotal", "modelArtifactId", "engineSha256", "inputSha256")
            missing = [field for field in required if evidence.get(field) is None]
            if pick not in (game["away"], game["home"]):
                missing.append("winner")
            try:
                if not evidence.get("generatedAt") or parse(evidence["generatedAt"]) >= parse(game["date"]) or parse(evidence["generatedAt"]) > now:
                    missing.append("PREKICKOFF_TIMESTAMP")
            except (ValueError, TypeError):
                missing.append("VALID_TIMESTAMP")
            if model in ("C", "C-QB") and not qb.get("officialGameSpecific"):
                missing.append("OFFICIAL_QB_EVIDENCE")
            if missing:
                unavailable.append({"game": str(game["id"]), "model": model, "fields": missing})
            else:
                valid += 1
    if unavailable:
        issues.append("INCOMPLETE_MODEL_ROWS")
    return {"status": "PASS" if not issues else "FAILED_COMPLETENESS_CHECK",
            "season": schedule.get("season"), "week": week["week"],
            "expectedGames": len(expected), "expectedRows": len(expected)*4,
            "validCompleteRows": valid, "unavailable": unavailable, "issues": issues,
            "earliestKickoff": min((g["date"] for g in expected), default=None)}

def main():
    root = pathlib.Path(__file__).resolve().parents[1] / "data"
    schedule = json.loads((root / "nfl-schedule.json").read_text())
    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(ET)
    thursday = local.date() + dt.timedelta(days=(3-local.weekday()) % 7)
    weeks = [w for w in schedule.get("weeks", []) if any(parse(g["date"]).astimezone(ET).date() == thursday for g in w.get("games", []))]
    card = None
    if len(weeks) == 1:
        path = root / "four-model-head-to-head" / f'{schedule["season"]}-week-{weeks[0]["week"]}.json'
        if path.exists():
            card = json.loads(path.read_text())
    result = validate(schedule, card, now)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
