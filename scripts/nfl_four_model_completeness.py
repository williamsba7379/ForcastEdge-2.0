"""Fail-closed, read-only NFL four-model completeness audit. Never generates picks."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

MODELS = ("A", "B", "C", "C-QB")
FIELDS = ("projected_home_score", "projected_away_score", "projected_margin", "projected_total", "confidence")

def stamp(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return d.astimezone(dt.timezone.utc)

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate(card, expected_games=None, schedule=None):
    errors = []
    games = card.get("games")
    if not isinstance(games, list) or not games:
        return ["MISSING_GAMES"]
    if expected_games is not None and len(games) != expected_games:
        errors.append("GAME_COVERAGE expected=%d actual=%d" % (expected_games, len(games)))
    if schedule is not None:
        expected_ids = {str(g["id"]) for g in schedule["games"]}
        actual_ids = {str(g.get("id")) for g in games}
        if expected_ids != actual_ids:
            errors.append("SCHEDULE_ID_MISMATCH missing=%s unexpected=%s" % (sorted(expected_ids-actual_ids),sorted(actual_ids-expected_ids)))
    seen = set()
    for i, game in enumerate(games):
        ident = str(game.get("id") or "")
        prefix = "game[%d]=%s" % (i, ident or "UNKNOWN")
        if not ident or ident in seen:
            errors.append(prefix + " INVALID_OR_DUPLICATE_ID")
        seen.add(ident)
        try:
            kickoff = stamp(game.get("date"))
            frozen = stamp(card.get("frozenAt"))
            if frozen >= kickoff:
                errors.append(prefix + " POST_KICKOFF_FREEZE")
        except (ValueError, TypeError):
            errors.append(prefix + " INVALID_FREEZE_OR_KICKOFF_TIMESTAMP")
        picks = game.get("picks")
        if not isinstance(picks, dict):
            picks = {}
        for model in MODELS:
            if not isinstance(picks.get(model), str) or picks[model] not in (game.get("home"), game.get("away")):
                errors.append(prefix + " " + model + " MISSING_OR_INVALID_WINNER")
        forecasts = game.get("model_forecasts") or {}
        for model in MODELS:
            row = forecasts.get(model) if isinstance(forecasts, dict) else None
            if not isinstance(row, dict):
                errors.append(prefix + " " + model + " MISSING_POINT_FORECAST")
                continue
            for field in FIELDS:
                if not finite(row.get(field)):
                    errors.append(prefix + " " + model + " MISSING_OR_INVALID_" + field.upper())
            h, a, m, t = (row.get(k) for k in FIELDS[:4])
            if all(finite(v) for v in (h, a, m, t)):
                if min(h, a) < 0 or abs((h-a)-m)>0.01 or abs((h+a)-t)>0.01:
                    errors.append(prefix + " " + model + " INCONSISTENT_SCORES")
            if finite(row.get("confidence")) and not (0 <= row["confidence"] <= 1):
                errors.append(prefix + " " + model + " INVALID_CONFIDENCE_RANGE")
            if not row.get("confidence_calibration_source"):
                errors.append(prefix + " " + model + " UNVERIFIED_CONFIDENCE_CALIBRATION")
            try:
                if stamp(row.get("generated_at_utc")) >= kickoff:
                    errors.append(prefix + " " + model + " POST_KICKOFF_MODEL")
            except (ValueError, TypeError):
                errors.append(prefix + " " + model + " MISSING_MODEL_TIMESTAMP")
            for market in ("spread", "total"):
                item = row.get(market)
                if not isinstance(item, dict) or not all(item.get(k) for k in ("source_url", "bookmaker", "quoted_at_utc", "selection")):
                    errors.append(prefix + " " + model + " UNVERIFIED_" + market.upper() + "_QUOTE")
                    continue
                if not str(item["source_url"]).startswith("https://"):
                    errors.append(prefix + " " + model + " INVALID_" + market.upper() + "_SOURCE")
                try:
                    if stamp(item["quoted_at_utc"]) >= kickoff:
                        errors.append(prefix + " " + model + " POST_KICKOFF_" + market.upper() + "_QUOTE")
                except (ValueError, TypeError):
                    errors.append(prefix + " " + model + " INVALID_" + market.upper() + "_TIMESTAMP")
    return errors

def main():
    p = argparse.ArgumentParser()
    p.add_argument("card", type=Path)
    p.add_argument("--expected-games", type=int)
    p.add_argument("--schedule", type=Path)
    p.add_argument("--output", type=Path, default=Path("completeness-report.json"))
    args = p.parse_args()
    try:
        schedule = json.loads(args.schedule.read_text()) if args.schedule else None
        expected = len(schedule["games"]) if schedule else args.expected_games
        errors = validate(json.loads(args.card.read_text()), expected, schedule)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors = ["UNREADABLE_CARD " + str(exc)]
    report = {"status": "FAILED_COMPLETENESS_CHECK" if errors else "PASS", "missing_count": len(errors), "issues": errors, "source": str(args.card), "read_only": True}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if errors else 0)

if __name__ == "__main__":
    main()
