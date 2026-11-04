#!/usr/bin/env python3
"""Read-only, fail-closed 2026 Week 9 four-model readiness audit. Never freezes picks."""
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(UTC)

def validate(draft, model_c, shadow, now):
    errors = []
    def fail(msg): errors.append(msg)
    if not isinstance(draft.get("week"), str) or "2026 NFL Week 9" not in draft["week"]:
        fail("SCHEDULE_WEEK_MISMATCH")
    games = draft.get("games", [])
    if len(games) != 15: fail("SCHEDULE_NOT_15")
    schedule = {}
    for g in games:
        key = (g.get("away"), g.get("home"))
        if not all(key) or key in schedule: fail("SCHEDULE_DUPLICATE_OR_MISSING_TEAM")
        schedule[key] = g
        try:
            date = g["date"] + "T" + g["time"] + ":00-05:00"
            kickoff = timestamp(date)
            if kickoff <= now: fail("SCHEDULE_KICKOFF_PASSED")
        except (KeyError, ValueError, TypeError): fail("SCHEDULE_KICKOFF_INVALID")
    if len(schedule) != 15: fail("SCHEDULE_UNIQUE_COVERAGE")
    for name, obj, expected_status in (("C", model_c, "AUTOMATED_REVIEW_ONLY"),
                                        ("C-QB", shadow, "EXPERIMENTAL_SHADOW_ONLY")):
        if obj.get("season") != 2026 or obj.get("week") != 9:
            fail(name + "_STALE_OR_WRONG_WEEK")
        if obj.get("status") != expected_status: fail(name + "_STATUS_INVALID")
        try:
            created = timestamp(obj.get("generatedAt"))
            if created > now or now - created > dt.timedelta(hours=48):
                fail(name + "_TIMESTAMP_STALE_OR_FUTURE")
        except (ValueError, TypeError): fail(name + "_TIMESTAMP_INVALID")
        rows = obj.get("games", [])
        if len(rows) != 15: fail(name + "_NOT_15")
        seen = set()
        for g in rows:
            key = (g.get("away"), g.get("home"))
            if key in seen: fail(name + "_DUPLICATE")
            seen.add(key)
            if key not in schedule: fail(name + "_MATCHUP_MISMATCH")
            try:
                kickoff = timestamp(g["date"])
                if timestamp(obj["generatedAt"]) >= kickoff or now >= kickoff:
                    fail(name + "_NOT_PREKICKOFF")
            except (KeyError, ValueError, TypeError): fail(name + "_KICKOFF_INVALID")
            if name == "C-QB":
                adj = g.get("qbAdjustments")
                if not isinstance(adj, dict) or set(adj) != {"home", "away"}:
                    fail("QB_EVIDENCE_MISSING")
                    continue
                for side in ("home", "away"):
                    evidence = adj[side]
                    points = evidence.get("points")
                    if not isinstance(points, (int, float)) or isinstance(points, bool):
                        fail("QB_POINTS_INVALID")
                    if points != 0 or evidence.get("status") in ("EXPERIMENTAL_APPLIED", "APPLIED"):
                        sources = evidence.get("sources")
                        if not isinstance(sources, list) or not sources or not all(
                            isinstance(s, dict) and s.get("url", "").startswith("https://")
                            and s.get("publishedAt") and s.get("retrievedAt")
                            and s.get("contentHash") and s.get("player")
                            and s.get("humanApproved") is True for s in sources):
                            fail("QB_UNVERIFIED_ADJUSTMENT")
                    elif evidence.get("status") != "NO_ADJUSTMENT":
                        fail("QB_UNKNOWN_STATUS")
        if seen != set(schedule): fail(name + "_COVERAGE_MISMATCH")
    c_by_id = {str(g.get("id")): g for g in model_c.get("games", [])}
    for g in shadow.get("games", []):
        baseline = c_by_id.get(str(g.get("id")))
        if not baseline or (g.get("away"), g.get("home")) != (baseline.get("away"), baseline.get("home")):
            fail("C_QB_BASELINE_ID_MISMATCH")
        elif g.get("originalPick") != baseline.get("pick") or g.get("originalHomeEdgePoints") != baseline.get("homeEdgePoints"):
            fail("C_QB_BASELINE_CHANGED")
    return sorted(set(errors))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    data = args.root / "data"
    files = ("nfl-draft-picks.json", "model-c-automated-draft.json", "model-c-qb-shadow.json")
    try:
        draft, c, qb = [json.loads((data / name).read_text()) for name in files]
        errors = validate(draft, c, qb, dt.datetime.now(UTC))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors = ["INPUT_UNAVAILABLE_OR_INVALID: " + str(exc)]
    print(json.dumps({"season": 2026, "week": 9, "ready": not errors, "errors": errors,
                      "mode": "READ_ONLY_NO_FREEZE"}, indent=2))
    raise SystemExit(1 if errors else 0)

if __name__ == "__main__":
    main()
