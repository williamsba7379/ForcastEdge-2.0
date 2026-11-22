"""ForecastEdge NFL synthetic scoring bridge v1.

Research-only compatibility layer. No filesystem, network,
production engines, workflows, or publication operations.
"""
import copy

from research import nfl_synthetic_scoring_contract_v1 as contract
from research import nfl_synthetic_projection_adapter as adapter

MODELS = ("A", "B", "C", "C-QB")
RESEARCH = "SYNTHETIC_RESEARCH_ONLY"
SHADOW = "EXPERIMENTAL_SHADOW_ONLY"
SUCCESS = "RESEARCH_ONLY_NOT_DELIVERABLE"

OUTPUT_FIELDS = frozenset({
    "winner",
    "projectedHomeScore",
    "projectedAwayScore",
    "projectedMargin",
    "projectedTotal",
    "spreadPick",
    "totalPick",
    "confidence",
    "classification",
})


def blocked(reason):
    return {
        "status": "DELIVERY_BLOCKED",
        "reason": reason,
        "published": False,
    }


def is_dict(value):
    return type(value) is dict


def exact_models(value):
    return is_dict(value) and set(value) == set(MODELS)


def translate_for_adapter(
    game, original_picks, provider_results,
    calibration_results, market, provenance
):
    """Construct fresh adapter inputs; never alter originals.

    Must be called only after successful Contract v1
    validation by bridge_synthetic_scoring.
    """
    inputs = {}
    calibration = {}

    for model in MODELS:
        provider = provider_results[model]
        cal = calibration_results[model]

        inputs[model] = {
            "expectedHomeMargin":
                provider["expectedHomeMargin"],
            "expectedTotal":
                provider["expectedTotal"],
            "classification":
                provider["classification"],
        }
        calibration[model] = {
            "winnerProbability":
                cal["winnerProbability"],
        }

    return (
        {
            "id": game["id"],
            "home": game["home"],
            "away": game["away"],
        },
        dict(original_picks),
        inputs,
        {
            "homeSpread": market["homeSpread"],
            "total": market["total"],
        },
        calibration,
        {"syntheticOnly": True},
    )


def outputs_match(expected, actual, original_picks):
    """Require exact research status, keys and model values."""
    if not all(is_dict(x) for x in (
        expected, actual, original_picks
    )):
        return False

    if set(expected) != {
        "status", "gameId", "models", "published"
    }:
        return False

    if set(actual) != set(expected):
        return False

    if (
        expected["status"] != SUCCESS
        or actual["status"] != SUCCESS
        or expected["published"] is not False
        or actual["published"] is not False
        or type(expected["gameId"]) is not str
        or actual["gameId"] != expected["gameId"]
    ):
        return False

    em = expected["models"]
    am = actual["models"]

    if not (
        exact_models(em)
        and exact_models(am)
        and exact_models(original_picks)
    ):
        return False

    for model in MODELS:
        e = em[model]
        a = am[model]

        if not (is_dict(e) and is_dict(a)):
            return False

        if (
            set(e) != OUTPUT_FIELDS
            or set(a) != OUTPUT_FIELDS
        ):
            return False

        classification = (
            SHADOW if model == "C-QB" else RESEARCH
        )

        if (
            type(e["winner"]) is not str
            or type(a["winner"]) is not str
            or e["winner"] != original_picks[model]
            or a["winner"] != original_picks[model]
            or e["classification"] != classification
            or a["classification"] != classification
        ):
            return False

        for field in OUTPUT_FIELDS:
            ev = e[field]
            av = a[field]

            # No tolerance or coercion. NaN never matches.
            if type(ev) is not type(av) or ev != av:
                return False

    return True


def bridge_synthetic_scoring(
    game, original_picks, provider_results,
    calibration_results, features_by_model,
    market, provenance, *, cutoff_utc
):
    """Return a non-deliverable research card or block."""
    try:
        if not all(is_dict(x) for x in (
            game, original_picks, provider_results,
            calibration_results, features_by_model,
            market, provenance
        )):
            return blocked("MALFORMED_INPUT")

        if not exact_models(original_picks):
            return blocked("INCOMPLETE_MODELS")

        if (
            provenance.get("syntheticOnly") is not True
            or provenance.get(
                "independentVerification"
            ) is not False
            or provenance.get("published") is not False
        ):
            return blocked("UNSAFE_PROVENANCE")

        # Isolate both modules from caller-owned objects.
        evidence = copy.deepcopy((
            game, original_picks, provider_results,
            calibration_results, features_by_model,
            market, provenance, cutoff_utc
        ))
        (
            g, picks, providers, calibrations,
            features, lines, proof, cutoff
        ) = evidence

        expected = contract.assemble_synthetic_candidate(
            g, picks, providers, calibrations,
            features, lines, proof, cutoff_utc=cutoff
        )

        if not is_dict(expected):
            return blocked("INVALID_CONTRACT_OUTPUT")

        if expected.get("status") == "DELIVERY_BLOCKED":
            if (
                set(expected)
                != {"status", "reason", "published"}
                or type(expected.get("reason")) is not str
                or not expected["reason"]
                or expected.get("published") is not False
            ):
                return blocked("INVALID_CONTRACT_OUTPUT")
            return blocked(expected["reason"])

        if (
            expected.get("status") != SUCCESS
            or expected.get("published") is not False
        ):
            return blocked("INVALID_CONTRACT_OUTPUT")

        adapter_args = translate_for_adapter(
            g, picks, providers, calibrations,
            lines, proof
        )

        actual = adapter.project_four_models(
            *adapter_args
        )

        if not outputs_match(expected, actual, picks):
            return blocked("ADAPTER_PARITY_MISMATCH")

        if expected["gameId"] != g["id"]:
            return blocked("CONTRACT_GAME_MISMATCH")

        # Never return a module-owned mutable result.
        return copy.deepcopy(expected)

    except Exception:
        # Research-only fail-closed boundary. Exceptions
        # are not reported as successful deliveries.
        return blocked("BRIDGE_EXCEPTION")
