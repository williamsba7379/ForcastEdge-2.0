"""Read-only current-week input preflight. Never writes files or generates picks."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

def parse(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

def check(data_dir, now):
    data_dir = Path(data_dir)
    local = now.astimezone(ET)
    thursday = local.date() + dt.timedelta(days=(3-local.weekday()) % 7)
    monday = thursday + dt.timedelta(days=4)
    missing = []
    def load(name):
        try:
            return json.loads((data_dir / name).read_text())
        except (OSError, ValueError) as exc:
            missing.append({"code": "MISSING_OR_INVALID_FILE", "file": name, "detail": type(exc).__name__})
            return None
    schedule = load("nfl-schedule.json")
    history = load("nfl-historical-results.json")
    draft = load("model-c-automated-draft.json")
    shadow = load("model-c-qb-shadow.json")
    reviewed = load("model-c-qb-reviewed-announcements.json")
    starters = load("model-c-qb-starters.json")
    selected = None
    if schedule:
        weeks = [w for w in schedule.get("weeks", []) if any(
            thursday <= parse(g["date"]).astimezone(ET).date() <= monday
            for g in w.get("games", []))]
        if len(weeks) != 1:
            missing.append({"code": "AMBIGUOUS_CURRENT_WEEK", "matches": len(weeks)})
        else:
            selected = weeks[0]
    if selected and history:
        ids = {str(g["id"]) for g in history.get("games", [])}
        # Only games listed as completed in the selected schedule can be required here.
        completed = [g for g in selected["games"] if str(g.get("status", "")).upper() in
                     ("FINAL", "STATUS_FINAL", "COMPLETED")]
        for g in completed:
            if str(g["id"]) not in ids:
                missing.append({"code": "MISSING_COMPLETED_HISTORY", "gameId": str(g["id"])})
        # Historical coverage must include all earlier scheduled completed games,
        # not merely QB-stat referenced games; report archive cutoff explicitly.
        prior = [g for g in history.get("games", []) if g.get("season") == schedule.get("season")]
        if not prior:
            missing.append({"code": "NO_SEASON_HISTORY"})
        else:
            latest = max(parse(g["date"]) for g in prior)
            missing.append({"code": "HISTORY_CUTOFF_REVIEW_REQUIRED", "latestSavedGame": latest.isoformat(),
                            "note": "Independent completed-game schedule needed to prove coverage"})
    if selected and schedule:
        expected = {str(g["id"]) for g in selected["games"]}
        for label, artifact in (("C", draft), ("C-QB", shadow)):
            if artifact:
                if (artifact.get("season"), artifact.get("week")) != (schedule.get("season"), selected["week"]):
                    missing.append({"code": "MODEL_WEEK_MISMATCH", "model": label,
                                    "actualWeek": artifact.get("week"), "expectedWeek": selected["week"]})
                actual = [str(g["id"]) for g in artifact.get("games", [])]
                if len(actual) != len(expected) or set(actual) != expected:
                    missing.append({"code": "MODEL_GAME_IDS_MISMATCH", "model": label,
                                    "missingIds": sorted(expected-set(actual)),
                                    "unexpectedIds": sorted(set(actual)-expected)})
                try:
                    age = (now - parse(artifact["generatedAt"])).total_seconds()
                    if age < 0 or age > 8*3600:
                        missing.append({"code": "MODEL_ARTIFACT_STALE", "model": label})
                except (KeyError, ValueError, TypeError):
                    missing.append({"code": "MODEL_ARTIFACT_TIMESTAMP_INVALID", "model": label})
        if reviewed is not None and starters is not None:
            entries = reviewed.get("entries", [])
            teams = starters.get("teams", {})
            for game in selected["games"]:
                for team in (game["home"], game["away"]):
                    if not any(e.get("team") == team and str(e.get("gameId")) == str(game["id"])
                               and e.get("status") == "CONFIRMED_STARTER" and e.get("reviewed") is True
                               and e.get("sourceType") == "TEAM_ANNOUNCEMENT" for e in entries):
                        missing.append({"code": "QB_OFFICIAL_CONFIRMATION_MISSING",
                                        "gameId": str(game["id"]), "team": team})
                    if team not in teams:
                        missing.append({"code": "QB_VERIFIED_INTAKE_MISSING", "team": team})
    return {"status": "BLOCKED_MISSING_INPUTS" if missing else "PREFLIGHT_NO_BLOCKERS_NOT_DELIVERY_APPROVAL",
            "season": schedule.get("season") if schedule else None,
            "week": selected.get("week") if selected else None,
            "expectedGames": len(selected["games"]) if selected else None,
            "issues": missing, "published": False, "readOnly": True,
            "wednesdayHandoffReady": False}

if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1] / "data", dt.datetime.now(UTC))
    print(json.dumps(result, indent=2))
