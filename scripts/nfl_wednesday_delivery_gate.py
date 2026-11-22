#!/usr/bin/env python3
"""Read-only four-model delivery gate. Does not generate picks, publish or overwrite cards."""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
FIELDS = ("moneylineWinner", "spreadPick", "spreadLine", "totalPick",
          "totalLine", "projectedHomeScore", "projectedAwayScore", "confidence",
          "wagerStatus")
EASTERN = ZoneInfo("America/New_York")


def check(card, schedule, cutoff):
    """Return reasons for rejection; absence of errors is NOT source authentication."""
    errors = []
    if cutoff.tzinfo is None:
        return ["Cutoff must have timezone"]
    local = cutoff.astimezone(EASTERN)
    if local.weekday() != 2 or (local.hour, local.minute) != (11, 0):
        errors.append("Cutoff is not Wednesday 11:00 Eastern")
    if not isinstance(card, dict) or not isinstance(schedule, dict):
        return errors + ["Card and schedule must be objects"]
    games = schedule.get("games")
    rows = card.get("games")
    if not isinstance(games, list) or not games or not isinstance(rows, list):
        return errors + ["Schedule/card games missing"]
    expected = {str(g.get("id")): g for g in games if isinstance(g, dict) and g.get("id") is not None}
    found = {str(g.get("gameId")): g for g in rows if isinstance(g, dict) and g.get("gameId") is not None}
    if len(expected) != len(games) or len(found) != len(rows) or set(expected) != set(found):
        errors.append("Missing, duplicate, or unexpected game IDs")
    if card.get("season") != schedule.get("season") or card.get("week") != schedule.get("week"):
        errors.append("Season/week mismatch")
    for game_id, source in expected.items():
        row = found.get(game_id)
        if row is None:
            continue
        for field, expected_field in (("homeTeam", "home"), ("awayTeam", "away"), ("kickoffAt", "date")):
            if row.get(field) != source.get(expected_field):
                errors.append(f"{game_id}: {field} differs from schedule")
        models = row.get("models")
        if not isinstance(models, dict) or set(models) != set(MODELS):
            errors.append(f"{game_id}: exactly four distinct model labels required")
            continue
        for name in MODELS:
            m = models[name]
            if not isinstance(m, dict):
                errors.append(f"{game_id}/{name}: model row missing")
                continue
            missing = [field for field in FIELDS if m.get(field) is None]
            if missing:
                errors.append(f"{game_id}/{name}: missing {','.join(missing)}")
            if m.get("wagerStatus") != "NO BET":
                errors.append(f"{game_id}/{name}: NO BET must be preserved")
            if m.get("moneylineWinner") not in (source.get("home"), source.get("away")):
                errors.append(f"{game_id}/{name}: invalid winner")
            if m.get("spreadPick") not in (source.get("home"), source.get("away")):
                errors.append(f"{game_id}/{name}: invalid spread pick")
            if m.get("totalPick") not in ("OVER", "UNDER"):
                errors.append(f"{game_id}/{name}: missing sourced total selection")
            for numeric in ("spreadLine", "totalLine", "projectedHomeScore", "projectedAwayScore", "confidence"):
                v = m.get(numeric)
                if type(v) not in (int, float) or not -1e8 < v < 1e8:
                    errors.append(f"{game_id}/{name}: invalid {numeric}")
            if type(m.get("confidence")) in (int, float) and not 0 <= m["confidence"] <= 1:
                errors.append(f"{game_id}/{name}: confidence out of range")
            for evidence in ("qbEvidence", "marketEvidence", "modelEvidence"):
                item = row.get(evidence) if evidence == "qbEvidence" else m.get(evidence)
                if not isinstance(item, dict) or not item.get("source") or not item.get("capturedAt"):
                    errors.append(f"{game_id}/{name}: {evidence} source/timestamp missing")
    for field in ("frozenAt", "publishedAt"):
        raw = card.get(field)
        if not isinstance(raw, str):
            errors.append(f"Missing {field}")
            continue
        try:
            instant = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                raise ValueError("naive")
            if instant > cutoff:
                errors.append(f"{field} after Wednesday cutoff; cannot label on time")
        except ValueError:
            errors.append(f"Invalid {field}")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Check completeness only; no production publishing")
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--cutoff", required=True, help="ISO8601 offset-aware Wednesday 11 AM ET")
    args = parser.parse_args()
    errors = check(json.loads(args.card.read_text()), json.loads(args.schedule.read_text()),
                   dt.datetime.fromisoformat(args.cutoff))
    print(json.dumps({"status": "BLOCKED" if errors else "COMPLETE_UNAUTHENTICATED",
                      "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
