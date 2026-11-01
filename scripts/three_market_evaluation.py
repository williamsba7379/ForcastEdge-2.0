"""Read-only winner, signed-home-spread and total research evaluation.

No predictions are generated or revised. Research directions computed from
frozen point forecasts are not historical betting picks. All wagers stay NO_BET.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

SPORT = "NFL"  # Set independently in each sport repository.


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(dt.timezone.utc)


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite number")
    return result


def identity(row):
    keys = ("game_id", "home_id", "away_id")
    if any(not isinstance(row.get(k), str) or not row[k].strip() for k in keys):
        raise ValueError("Nonempty string game/team IDs required")
    if row["home_id"] == row["away_id"]:
        raise ValueError("Identical teams")
    return tuple(row[k] for k in keys) + (timestamp(row["start_utc"]),)


def native_predictions(data, sport=SPORT):
    """Adapt frozen winners without turning ratings or companion scores into points.

    Canonical records are accepted separately for explicitly archived point
    forecasts. Names serve as identity keys for NFL archives without team IDs.
    """
    if isinstance(data, dict) and "canonical_predictions" in data:
        return data["canonical_predictions"]
    if sport == "NFL":
        if data.get("status") not in ("FROZEN_PREKICKOFF", "FRESH_PREKICKOFF_SNAPSHOT"):
            raise ValueError("Use original frozen NFL winner card")
        return [dict(game_id=str(g["id"]), home_id=g["home"], away_id=g["away"],
                     start_utc=g["date"], frozen_at_utc=data["frozenAt"],
                     model=model, winner_id=pick, wagering_status="NO_BET")
                for g in data["games"] for model, pick in g["picks"].items()]
    rows = data if isinstance(data, list) else [data]
    result = []
    for r in rows:
        if sport == "NBA":
            frozen = r["frozen_at_utc"]
            if timestamp(r["feature_cutoff_utc"]) > timestamp(frozen):
                raise ValueError("NBA features after forecast")
            if r.get("status") not in ("FROZEN", "NO_PREDICTION"):
                raise ValueError("Use frozen NBA prediction, not grading output")
            winner = r.get("predicted_winner")
            sides = {r["home"]: str(r["home_id"]), r["away"]: str(r["away_id"])}
            if winner is not None and winner not in sides:
                raise ValueError("Invalid NBA winner")
            p = dict(game_id=str(r["game_id"]), home_id=str(r["home_id"]),
                     away_id=str(r["away_id"]), start_utc=r["tipoff_utc"],
                     frozen_at_utc=frozen, model=r["model"],
                     winner_id=sides.get(winner), wagering_status=r["wagering_status"])
            if r["status"] == "FROZEN":
                p.update(projected_margin=r.get("predicted_margin"),
                         projected_total=r.get("predicted_total"))
            elif winner is not None:
                raise ValueError("NO_PREDICTION contains a winner")
        elif sport == "CFB":
            p = dict(game_id=str(r["game_id"]), home_id=str(r["home_team_id"]),
                     away_id=str(r["away_team_id"]), start_utc=r["kickoff_utc"],
                     frozen_at_utc=r["generated_at_utc"], model=r["model"],
                     winner_id=r.get("predicted_winner_id") or None,
                     wagering_status="NO_BET")
            # score_difference is a rating, not points. The separate experimental
            # score model must have its own canonical model identity and timestamp.
        else:
            raise ValueError("Unknown sport")
        result.append(p)
    return result


def indexed(rows, label):
    result = {}
    for row in rows:
        key = row["game_id"]
        identity(row)
        if key in result:
            raise ValueError("Duplicate " + label + " game: " + key)
        result[key] = row
    return result


def matched(record, prediction):
    return identity(record) == identity(prediction)


def market_status(market, prediction, field, max_age):
    if market is None:
        return "MISSING_MARKET"
    if not matched(market, prediction):
        return "MARKET_GAME_MISMATCH"
    if not all(isinstance(market.get(k), str) and market[k].strip()
               for k in ("source", "bookmaker")) or not market["source"].startswith("https://"):
        return "MISSING_MARKET_PROVENANCE"
    try:
        captured = timestamp(market["captured_at_utc"])
        frozen = timestamp(prediction["frozen_at_utc"])
        if captured >= timestamp(prediction["start_utc"]):
            return "POST_START_MARKET"
        if captured > frozen:
            return "MARKET_AFTER_FORECAST"
        if frozen - captured > dt.timedelta(hours=max_age):
            return "STALE_MARKET"
        value = number(market.get(field))
        if value is None:
            return "MISSING_MARKET_FIELD"
        if field == "total_points" and value <= 0:
            return "INVALID_MARKET"
        if field == "home_spread" and market.get("spread_convention") != "SIGNED_HOME":
            return "UNVERIFIED_SPREAD_SIGN"
    except (ValueError, TypeError, KeyError, AttributeError):
        return "INVALID_MARKET"
    return "VALID"


def outcome(selected, actual):
    if actual == 0:
        return "PUSH"
    return "WIN" if selected == (1 if actual > 0 else -1) else "LOSS"


def evaluate(predictions, results=(), markets=(), max_market_age_hours=24):
    if not math.isfinite(max_market_age_hours) or max_market_age_hours <= 0:
        raise ValueError("Positive finite market-age limit required")
    predictions = list(predictions)
    if not predictions:
        raise ValueError("No frozen predictions supplied")
    finals, lines = indexed(results, "result"), indexed(markets, "market")
    seen, rows, game_metadata = set(), [], {}
    for p in predictions:
        meta = identity(p)
        model = p.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model identity required")
        key = (p["game_id"], model)
        if key in seen:
            raise ValueError("Duplicate game/model: " + str(key))
        seen.add(key)
        if p["game_id"] in game_metadata and game_metadata[p["game_id"]] != meta:
            raise ValueError("Models disagree on game metadata")
        game_metadata[p["game_id"]] = meta
        if timestamp(p["frozen_at_utc"]) >= meta[-1]:
            raise ValueError("Prediction must be frozen before start")
        if p.get("wagering_status") != "NO_BET":
            raise ValueError("This research evaluator requires NO_BET")
        winner = p.get("winner_id")
        if winner is not None and winner not in (p["home_id"], p["away_id"]):
            raise ValueError("Invalid winner ID")
        pm, pt = number(p.get("projected_margin")), number(p.get("projected_total"))
        if pt is not None and (pt < 0 or (pm is not None and abs(pm) > pt)):
            raise ValueError("Impossible point forecast")
        row = dict(game_id=p["game_id"], model=model, wagering_status="NO_BET",
                   winner={"status": "PENDING_RESULT"},
                   spread={"status": "PENDING_RESULT"},
                   total={"status": "PENDING_RESULT"},
                   margin_absolute_error=None, total_absolute_error=None)
        source = finals.get(p["game_id"])
        reason = "PENDING_RESULT"
        if source is not None:
            if not matched(source, p):
                reason = "RESULT_GAME_MISMATCH"
            elif source.get("final") is not True:
                reason = "PENDING_RESULT"
            else:
                try:
                    h, a = number(source["home_points"]), number(source["away_points"])
                    if h is None or a is None or min(h, a) < 0 or not h.is_integer() or not a.is_integer():
                        raise ValueError("Invalid final scores")
                    reason = "FINAL"
                except (ValueError, TypeError, KeyError):
                    reason = "INVALID_FINAL_SCORE"
        if reason != "FINAL":
            for category in ("winner", "spread", "total"):
                row[category]["status"] = reason
            rows.append(row)
            continue
        margin, total = h - a, h + a
        actual_winner = p["home_id"] if margin > 0 else p["away_id"] if margin < 0 else None
        row["winner"] = {"status": "NO_PREDICTION" if winner is None else
                         "TIE" if actual_winner is None else "WIN" if winner == actual_winner else "LOSS"}
        if pm is not None:
            row["margin_absolute_error"] = abs(pm - margin)
        if pt is not None:
            row["total_absolute_error"] = abs(pt - total)
        market = lines.get(p["game_id"])
        for category, projection, field, actual in (
                ("spread", pm, "home_spread", margin),
                ("total", pt, "total_points", total)):
            state = "NO_POINT_FORECAST" if projection is None else market_status(
                market, p, field, max_market_age_hours)
            if state != "VALID":
                row[category] = {"status": state}
                continue
            line = number(market[field])
            edge = projection + line if category == "spread" else projection - line
            if abs(edge) < 1e-9:
                row[category] = {"status": "NO_DIRECTION", "line": line}
                continue
            direction = 1 if edge > 0 else -1
            residual = actual + line if category == "spread" else actual - line
            if abs(residual) < 1e-9:
                residual = 0
            row[category] = {"status": outcome(direction, residual), "line": line,
                             "research_direction": ("HOME" if direction > 0 else "AWAY")
                             if category == "spread" else ("OVER" if direction > 0 else "UNDER"),
                             "market_source": market["source"],
                             "market_captured_at_utc": market["captured_at_utc"]}
        rows.append(row)
    summaries = {}
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"]].append(row)
    for model, own in sorted(groups.items()):
        summary = {"prediction_rows": len(own), "actionable_wagers": 0}
        for category in ("winner", "spread", "total"):
            counts = Counter(r[category]["status"] for r in own)
            wins, losses = counts["WIN"], counts["LOSS"]
            summary[category] = dict(wins=wins, losses=losses, pushes=counts["PUSH"],
                                     decided=wins + losses,
                                     accuracy=wins / (wins + losses) if wins + losses else None,
                                     coverage=(wins + losses + counts["PUSH"]) / len(own),
                                     statuses=dict(sorted(counts.items())))
        for name in ("margin", "total"):
            errors = [r[name + "_absolute_error"] for r in own if r[name + "_absolute_error"] is not None]
            summary[name + "_mae"] = sum(errors) / len(errors) if errors else None
            summary[name + "_error_games"] = len(errors)
        summaries[model] = summary
    return dict(sport=SPORT, wagering_status="NO_BET", evaluation_type="RESEARCH_ONLY",
                direction_policy="Frozen projections versus markets available at forecast time; not original betting picks",
                max_market_age_hours=max_market_age_hours, summary=summaries, rows=rows)


def read_rows(path):
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--markets", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-market-age-hours", type=float, default=24)
    args = parser.parse_args()
    predictions = native_predictions(read_rows(args.predictions))
    report = evaluate(predictions, read_rows(args.results),
                      read_rows(args.markets) if args.markets else [], args.max_market_age_hours)
    # Exclusive creation prevents overwriting frozen inputs, history or prior reports.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["summary"], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
