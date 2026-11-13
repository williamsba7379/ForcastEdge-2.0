"""Run the real NFL engines in a temporary directory before Wednesday's cutoff."""
import argparse
import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

import model_c_engine
import model_c_qb_shadow

from nfl_operational_readiness import parse, rehearse_handoff

ET = ZoneInfo("America/New_York")
ENGINE_INPUTS = (
    "nfl-schedule.json",
    "nfl-historical-results.json",
    "model-c-qb-starters.json",
    "model-c-historical-qb-games.json",
)


def wednesday_cutoff(now):
    local = now.astimezone(ET)
    cutoff = local.replace(hour=11, minute=0, second=0, microsecond=0)
    if local.weekday() != 2 or local >= cutoff:
        raise ValueError("Start the rehearsal on Wednesday before 11 AM Eastern")
    return cutoff


def rehearsal(input_dir):
    started = dt.datetime.now(dt.timezone.utc)
    cutoff = wednesday_cutoff(started)

    def load(name):
        return json.loads((input_dir / name).read_text())

    schedule = load(ENGINE_INPUTS[0])
    history = load(ENGINE_INPUTS[1])
    midnight = cutoff.replace(hour=0)
    if not midnight <= parse(schedule["updatedAt"]) <= started:
        raise ValueError("Schedule snapshot must have been captured this Wednesday")
    if parse(history["updatedAt"]) > started:
        raise ValueError("Historical results snapshot is dated in the future")
    week = model_c_engine.choose_week(schedule, cutoff)
    thursday = cutoff.date() + dt.timedelta(days=1)
    monday = thursday + dt.timedelta(days=4)
    if any(not thursday <= parse(g["date"]).astimezone(ET).date() <= monday for g in week["games"]):
        raise ValueError("Schedule includes a game outside the upcoming Thursday–Monday slate")

    from nfl_market_totals_compare import compare

    with TemporaryDirectory(prefix="nfl-wednesday-rehearsal-") as tmp:
        staging = Path(tmp)
        inputs = {ENGINE_INPUTS[0]: schedule, ENGINE_INPUTS[1]: history}
        inputs.update({name: load(name) for name in ENGINE_INPUTS[2:]})
        for name, payload in inputs.items():
            (staging / name).write_text(json.dumps(payload))
        with patch.object(model_c_engine, "DATA", staging), patch.object(model_c_qb_shadow, "DATA", staging):
            model_c_engine.main()
            model_c_qb_shadow.main()
        draft = json.loads((staging / "model-c-automated-draft.json").read_text())
        shadow = json.loads((staging / "model-c-qb-shadow.json").read_text())

    card = rehearse_handoff(schedule, draft, shadow, history, cutoff.isoformat())
    market_path = input_dir / "nfl-market-totals.json"
    market = load(market_path.name) if market_path.exists() else {
        "season": card["season"], "week": card["week"], "games": [],
    }
    research = {
        "season": card["season"], "week": card["week"],
        "sourceComparisonFrozenAt": started.isoformat(),
        "games": [{"id": game["id"], "date": game["date"], "models": {}} for game in card["games"]],
    }
    lines = compare(research, market)["marketLinesAvailable"]
    declarations = inputs["model-c-qb-starters.json"].get("teams", {})
    verified = sum(
        model_c_engine.official_starter_valid(declarations.get(game[side]), game, game[side], started)
        and game["quarterbacks"][side]["verification"] == "OFFICIAL_GAME_SPECIFIC"
        for game in draft["games"] for side in ("home", "away")
    )
    games = len(card["games"])
    if dt.datetime.now(dt.timezone.utc) > cutoff:
        raise ValueError("Rehearsal finished after the Wednesday cutoff")
    return {
        "status": "RESEARCH_REHEARSAL_ONLY",
        "week": card["week"], "games": games,
        "models": list(card["models"]), "cutoff": cutoff.isoformat(),
        "modelCGeneratedAt": draft["generatedAt"], "modelCQBGeneratedAt": shadow["generatedAt"],
        "verifiedQbSides": verified, "expectedQbSides": 2 * games,
        "gamesWithValidatedMarketTotals": lines,
        "productionReady": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Directory with independently captured input snapshots")
    args = parser.parse_args()
    try:
        print(json.dumps(rehearsal(args.input_dir), indent=2))
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Rehearsal blocked: {error}\n")
