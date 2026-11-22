#!/usr/bin/env python3
"""Read-only dependency inventory for an upcoming four-model NFL review.
No model execution, file writes, publication, or synthetic replacement picks.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def parse_time(value):
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def inspect(schedule, draft, shadow, history, qb_history, starters, now):
    if now.tzinfo is None:
        raise ValueError("As-of must be timezone aware")
    upcoming = []
    for week in schedule.get("weeks", []):
        games = week.get("games", [])
        dates = [parse_time(g.get("date")) for g in games]
        if games and all(dates) and min(dates) > now:
            upcoming.append((min(dates), week))
    if not upcoming:
        return {"status": "BLOCKED", "reasons": ["No complete future week in schedule"]}
    _, week = min(upcoming, key=lambda row: row[0])
    games = week["games"]
    expected = {str(g.get("id")): g for g in games}
    reasons = []
    if len(expected) != len(games):
        reasons.append("Duplicate or missing schedule IDs")
    for label, source in (("C", draft), ("C-QB", shadow)):
        if (source.get("season"), source.get("week")) != (schedule.get("season"), week.get("week")):
            reasons.append(label + " wrong season/week")
        generated = parse_time(source.get("generatedAt"))
        if generated is None or not dt.timedelta(0) <= now - generated <= dt.timedelta(hours=8):
            reasons.append(label + " missing/stale generation timestamp")
        rows = source.get("games", [])
        actual = {str(g.get("id")): g for g in rows}
        if len(actual) != len(rows) or set(actual) != set(expected):
            reasons.append(label + " incomplete/mismatched game IDs")
        for gid in set(actual) & set(expected):
            if any(actual[gid].get(k) != expected[gid].get(k) for k in ("date", "home", "away")):
                reasons.append(label + " schedule mismatch for " + gid)
    if shadow.get("status") != "EXPERIMENTAL_SHADOW_ONLY":
        reasons.append("C-QB shadow not experimental-only")
    updated = parse_time(history.get("updatedAt"))
    if updated is None or not dt.timedelta(0) <= now-updated <= dt.timedelta(days=7):
        reasons.append("Historical results snapshot older than seven days; verify latest completed finals")
    qb_generated = parse_time(qb_history.get("generatedAt"))
    if qb_generated is None or not dt.timedelta(0) <= now-qb_generated <= dt.timedelta(days=7):
        reasons.append("QB history snapshot older than seven days; do not claim current QB adjustments")
    if not starters.get("teams"):
        reasons.append("No game-specific confirmed starters; QB adjustments must remain unconfirmed")
    return {"status": "BLOCKED" if reasons else "SOURCES_PRESENT_NOT_AUTHENTICATED",
            "season": schedule.get("season"), "week": week.get("week"),
            "scheduledGames": len(games), "expectedModelRows": len(games)*4,
            "checkedAt": now.isoformat(), "reasons": reasons}


def main():
    p = argparse.ArgumentParser()
    for name in ("schedule", "draft", "shadow", "history", "qb-history", "starters"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--as-of", required=True)
    args = p.parse_args()
    now = parse_time(args.as_of)
    if now is None:
        raise SystemExit("BLOCKED: invalid as-of")
    read = lambda path: json.loads(path.read_text())
    result = inspect(read(args.schedule), read(args.draft), read(args.shadow),
                     read(args.history), read(args.qb_history), read(args.starters), now)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "SOURCES_PRESENT_NOT_AUTHENTICATED" else 1)


if __name__ == "__main__":
    main()
