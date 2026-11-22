"""Synthetic Scoring Input Contract v1.

Research only. No production imports, filesystem access,
network access, model execution, or publishing.

This contract checks the shape and internal consistency
of synthetic evidence. It cannot authenticate provenance.
"""
import datetime as dt
import math
import re
from collections.abc import Mapping

MODELS = ("A", "B", "C", "C-QB")
RESEARCH = "SYNTHETIC_RESEARCH_ONLY"
SHADOW = "EXPERIMENTAL_SHADOW_ONLY"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def nonempty(value):
    return type(value) is str and bool(value.strip())


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def mapping(value):
    return type(value) is dict


def keys(value):
    return mapping(value) and set(value) == set(MODELS)


def timestamp(value):
    require(nonempty(value), "INVALID_TIMESTAMP")
    try:
        parsed = dt.datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        require(
            parsed.tzinfo is not None
            and parsed.utcoffset() is not None,
            "INVALID_TIMESTAMP",
        )
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise ContractError("INVALID_TIMESTAMP") from None


def sha(value):
    return (
        type(value) is str
        and HEX64.fullmatch(value) is not None
    )


def blocked(code):
    return {
        "status": "DELIVERY_BLOCKED",
        "reason": code,
        "published": False,
    }


def validate_provenance(
    provenance, game, models, cutoff_utc
):
    require(mapping(provenance), "INVALID_PROVENANCE")
    require(
        provenance.get("contractVersion")
        == "synthetic-scoring-v1",
        "INVALID_VERSION",
    )
    require(
        provenance.get("syntheticOnly") is True,
        "NOT_SYNTHETIC",
    )
    require(
        provenance.get("independentVerification") is False,
        "FALSE_AUTHORITY",
    )
    require(
        provenance.get("published") is False,
        "PUBLICATION_FORBIDDEN",
    )
    require(
        provenance.get("gameId") == game["id"],
        "PROVENANCE_GAME_MISMATCH",
    )
    require(
        provenance.get("cutoffUtc") == cutoff_utc,
        "CUTOFF_MISMATCH",
    )
    require(
        type(models) is tuple
        and models == MODELS,
        "INVALID_MODELS",
    )

    cutoff = timestamp(cutoff_utc)
    generated = timestamp(
        provenance.get("generatedAtUtc")
    )
    kickoff = timestamp(game["kickoffUtc"])
    require(
        generated <= cutoff < kickoff,
        "INVALID_CHRONOLOGY",
    )

    entries = provenance.get("modelEvidence")
    require(keys(entries), "INCOMPLETE_PROVENANCE")

    for model in MODELS:
        entry = entries[model]
        require(mapping(entry), "INVALID_PROVENANCE")
        require(
            nonempty(entry.get("featureArtifactId"))
            and nonempty(entry.get("providerVersion"))
            and nonempty(entry.get("calibrationArtifactId")),
            "MISSING_PROVENANCE",
        )
        require(
            sha(entry.get("featureSha256")),
            "INVALID_HASH",
        )
        require(
            timestamp(entry.get("featureAvailableAtUtc"))
            <= cutoff,
            "FUTURE_FEATURE",
        )
        require(
            timestamp(entry.get("calibrationAvailableAtUtc"))
            <= cutoff,
            "FUTURE_CALIBRATION",
        )
        require(
            entry.get("classification")
            == (SHADOW if model == "C-QB" else RESEARCH),
            "INVALID_CLASSIFICATION",
        )


def validate_provider_result(
    model, result, calibration, features,
    provenance_entry, cutoff_utc
):
    require(model in MODELS, "INVALID_MODEL")
    require(
        all(mapping(x) for x in (
            result, calibration, features, provenance_entry
        )),
        "MALFORMED_PROVIDER",
    )
    expected = SHADOW if model == "C-QB" else RESEARCH
    require(
        result.get("classification") == expected,
        "INVALID_CLASSIFICATION",
    )
    require(
        features.get("model") == model
        and features.get("gameId")
        == result.get("gameId"),
        "FEATURE_IDENTITY_MISMATCH",
    )
    require(
        nonempty(features.get("sourceId"))
        and type(features.get("sampleSize")) is int
        and features["sampleSize"] >= 2,
        "INSUFFICIENT_FEATURES",
    )
    require(
        timestamp(features.get("availableAtUtc"))
        <= timestamp(cutoff_utc),
        "FUTURE_FEATURE",
    )
    require(
        features.get("availableAtUtc")
        == provenance_entry.get("featureAvailableAtUtc"),
        "FEATURE_PROVENANCE_MISMATCH",
    )
    require(
        features.get("artifactId")
        == provenance_entry.get("featureArtifactId")
        and features.get("sha256")
        == provenance_entry.get("featureSha256"),
        "FEATURE_PROVENANCE_MISMATCH",
    )
    margin = result.get("expectedHomeMargin")
    total = result.get("expectedTotal")
    require(
        finite(margin) and finite(total),
        "INVALID_ESTIMATE",
    )
    require(
        total > 0 and abs(margin) <= total,
        "IMPOSSIBLE_SCORES",
    )
    require(
        finite((total + margin) / 2)
        and finite((total - margin) / 2),
        "IMPOSSIBLE_SCORES",
    )

    probability = calibration.get("winnerProbability")
    require(
        finite(probability) and 0 <= probability <= 1,
        "INVALID_CONFIDENCE",
    )
    require(
        calibration.get("artifactId")
        == provenance_entry.get("calibrationArtifactId"),
        "CALIBRATION_MISMATCH",
    )
    require(
        calibration.get("model") == model
        and calibration.get("gameId")
        == result.get("gameId"),
        "CALIBRATION_MISMATCH",
    )
    require(
        type(calibration.get("trainingCount")) is int
        and calibration["trainingCount"] >= 30,
        "INSUFFICIENT_CALIBRATION",
    )
    require(
        type(calibration.get("validationCount")) is int
        and calibration["validationCount"] >= 20,
        "INSUFFICIENT_CALIBRATION",
    )

    train_end = timestamp(calibration.get("trainingEndUtc"))
    val_start = timestamp(calibration.get("validationStartUtc"))
    val_end = timestamp(calibration.get("validationEndUtc"))
    available = timestamp(
        provenance_entry.get("calibrationAvailableAtUtc")
    )
    require(
        train_end < val_start <= val_end
        <= available <= timestamp(cutoff_utc),
        "CALIBRATION_LEAKAGE",
    )

    if model == "C-QB":
        require(
            features.get("qbStatus") == SHADOW
            and nonempty(features.get("qbSourceId"))
            and timestamp(features.get("qbAvailableAtUtc"))
            <= timestamp(cutoff_utc),
            "INVALID_QB_SHADOW",
        )
    if model == "C":
        require(
            nonempty(features.get("modelCDraftId")),
            "MISSING_MODEL_C_DRAFT",
        )


def assemble_synthetic_candidate(
    game, original_picks, provider_results,
    calibration_results, features_by_model,
    market, provenance, *, cutoff_utc
):
    try:
        require(mapping(game), "INVALID_GAME")
        require(
            all(nonempty(game.get(k)) for k in
                ("id", "home", "away", "kickoffUtc")),
            "INVALID_GAME",
        )
        require(
            game["home"] != game["away"],
            "INVALID_GAME",
        )
        require(
            all(keys(x) for x in (
                original_picks, provider_results,
                calibration_results, features_by_model
            )),
            "INCOMPLETE_MODELS",
        )
        require(mapping(market), "INVALID_MARKET")
        require(
            finite(market.get("homeSpread"))
            and finite(market.get("total"))
            and market["total"] > 0,
            "INVALID_MARKET",
        )

        validate_provenance(
            provenance, game, MODELS, cutoff_utc
        )
        for model in MODELS:
            require(
                original_picks[model]
                in (game["home"], game["away"]),
                "INVALID_WINNER",
            )
            result = provider_results[model]
            require(
                mapping(result)
                and result.get("gameId") == game["id"],
                "PROVIDER_GAME_MISMATCH",
            )
            validate_provider_result(
                model, result, calibration_results[model],
                features_by_model[model],
                provenance["modelEvidence"][model],
                cutoff_utc,
            )
            margin = result["expectedHomeMargin"]
            require(
                margin != 0
                and (
                    game["home"] if margin > 0
                    else game["away"]
                ) == original_picks[model],
                "SCORE_WINNER_INCONSISTENCY",
            )

        # Pure arithmetic is repeated here intentionally.
        # The existing adapter is not imported or modified.
        outputs = {}
        for model in MODELS:
            result = provider_results[model]
            margin = result["expectedHomeMargin"]
            total = result["expectedTotal"]
            edge = margin + market["homeSpread"]
            total_edge = total - market["total"]
            require(
                finite(edge) and finite(total_edge),
                "INVALID_CALCULATION",
            )
            outputs[model] = {
                "winner": original_picks[model],
                "projectedHomeScore": (total + margin) / 2,
                "projectedAwayScore": (total - margin) / 2,
                "projectedMargin": margin,
                "projectedTotal": total,
                "confidence":
                    calibration_results[model]["winnerProbability"],
                "spreadPick": (
                    game["home"] if edge > 0
                    else game["away"] if edge < 0
                    else "Push"
                ),
                "totalPick": (
                    "Over" if total_edge > 0
                    else "Under" if total_edge < 0
                    else "Push"
                ),
                "classification":
                    SHADOW if model == "C-QB" else RESEARCH,
            }
        return {
            "status": "RESEARCH_ONLY_NOT_DELIVERABLE",
            "gameId": game["id"],
            "models": outputs,
            "published": False,
        }
    except ContractError as exc:
        return blocked(str(exc))
    except (TypeError, ValueError, KeyError,
            AttributeError, OverflowError):
        return blocked("MALFORMED_INPUT")
