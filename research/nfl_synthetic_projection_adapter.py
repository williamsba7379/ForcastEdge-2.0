"""Pure synthetic-only four-model projection research.

No production imports, I/O, publishing or engine execution.
Expected margins, totals and probabilities are supplied;
this module does not estimate or calibrate them.
"""
import math

MODELS = ("A", "B", "C", "C-QB")
SHADOW = "EXPERIMENTAL_SHADOW_ONLY"
RESEARCH = "SYNTHETIC_RESEARCH_ONLY"


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def blocked(reason):
    return {
        "status": "DELIVERY_BLOCKED",
        "reason": reason,
        "published": False,
    }


def project_four_models(
    game, original_picks, inputs, market,
    calibration, provenance
):
    """Produce a non-deliverable research result or block."""

    if not all(
        isinstance(x, dict)
        for x in (
            game, original_picks, inputs, market,
            calibration, provenance
        )
    ):
        return blocked("MALFORMED_INPUT")

    if not (
        set(original_picks) == set(inputs)
        == set(calibration) == set(MODELS)
    ):
        return blocked("INCOMPLETE_MODELS")

    if provenance.get("syntheticOnly") is not True:
        return blocked("NOT_SYNTHETIC")

    gid = game.get("id")
    home = game.get("home")
    away = game.get("away")

    if not (
        isinstance(gid, str) and gid.strip()
        and isinstance(home, str) and home.strip()
        and isinstance(away, str) and away.strip()
        and home != away
    ):
        return blocked("INVALID_GAME")

    spread = market.get("homeSpread")
    line = market.get("total")

    if not (
        finite(spread) and finite(line) and line > 0
    ):
        return blocked("INVALID_MARKET")

    results = {}

    for model in MODELS:
        item = inputs[model]
        cal = calibration[model]
        winner = original_picks[model]

        if not isinstance(item, dict):
            return blocked("INVALID_MODEL_INPUT")

        if not isinstance(cal, dict):
            return blocked("INVALID_CALIBRATION")

        if (
            not isinstance(winner, str)
            or winner not in (home, away)
        ):
            return blocked("INVALID_WINNER")

        margin = item.get("expectedHomeMargin")
        total = item.get("expectedTotal")
        confidence = cal.get("winnerProbability")

        if not all(
            finite(x) for x in (margin, total, confidence)
        ):
            return blocked("MISSING_CALCULATION")

        if (
            total <= 0 or abs(margin) > total
        ):
            return blocked("IMPOSSIBLE_SCORES")

        if not 0 <= confidence <= 1:
            return blocked("INVALID_CONFIDENCE")

        expected_class = (
            SHADOW if model == "C-QB" else RESEARCH
        )
        if item.get("classification") != expected_class:
            return blocked("INVALID_CLASSIFICATION")

        projected_home = (total + margin) / 2
        projected_away = (total - margin) / 2

        if not all(
            finite(x) and x >= 0
            for x in (projected_home, projected_away)
        ):
            return blocked("IMPOSSIBLE_SCORES")

        # An exact projected tie cannot imply a winner.
        if margin == 0:
            return blocked("SCORE_WINNER_INCONSISTENCY")

        implied_winner = home if margin > 0 else away

        if implied_winner != winner:
            return blocked("SCORE_WINNER_INCONSISTENCY")

        cover_edge = margin + spread
        total_edge = total - line

        if not all(
            finite(x) for x in (cover_edge, total_edge)
        ):
            return blocked("INVALID_CALCULATION")

        spread_pick = (
            home if cover_edge > 0
            else away if cover_edge < 0
            else "Push"
        )

        total_pick = (
            "Over" if total_edge > 0
            else "Under" if total_edge < 0
            else "Push"
        )

        results[model] = {
            "winner": winner,
            "projectedHomeScore": projected_home,
            "projectedAwayScore": projected_away,
            "projectedMargin": margin,
            "projectedTotal": total,
            "spreadPick": spread_pick,
            "totalPick": total_pick,
            "confidence": confidence,
            "classification": expected_class,
        }

    return {
        "status": "RESEARCH_ONLY_NOT_DELIVERABLE",
        "gameId": gid,
        "models": results,
        "published": False,
    }
