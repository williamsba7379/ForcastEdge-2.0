"""Draft-only rehearsal: run real engines on isolated copied inputs, never publish."""
import datetime as dt
import json
import pathlib
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import model_c_engine
import model_c_qb_shadow
import nfl_four_model_head_to_head as four
from research.nfl_delivery_failclosed import validate, parse

ET = ZoneInfo("America/New_York")
FILES = ("nfl-schedule.json", "nfl-historical-results.json",
         "model-c-qb-starters.json", "model-c-historical-qb-games.json")
OPTIONAL = ("model-c-verified-adjustments.json", "model-c-injury-snapshot.json",
            "model-c-qb-performance.json", "model-c-qb-candidates.json",
            "model-c-qb-depthcharts.json")

def rehearse(input_dir, now):
    now = parse(now) if isinstance(now, str) else now.astimezone(dt.timezone.utc)
    if now.astimezone(ET).weekday() != 2:
        raise ValueError("WEDNESDAY_REHEARSAL_ONLY")
    schedule = json.loads((input_dir / FILES[0]).read_text())
    if not schedule.get("updatedAt") or parse(schedule["updatedAt"]) > now:
        raise ValueError("INVALID_SCHEDULE_CAPTURE_TIMESTAMP")
    history = json.loads((input_dir / FILES[1]).read_text())
    if isinstance(history, dict) and history.get("updatedAt") and parse(history["updatedAt"]) > now:
        raise ValueError("FUTURE_HISTORY_CAPTURE")
    local = now.astimezone(ET)
    thursday = local.date() + dt.timedelta(days=1)
    monday = thursday + dt.timedelta(days=4)
    weeks = [w for w in schedule["weeks"] if any(
        thursday <= parse(g["date"]).astimezone(ET).date() <= monday for g in w["games"])]
    if len(weeks) != 1 or any(not thursday <= parse(g["date"]).astimezone(ET).date() <= monday for g in weeks[0]["games"]):
        raise ValueError("AMBIGUOUS_OR_INCOMPLETE_WEEK")
    selected = weeks[0]
    if len(selected["games"]) < 10 or len({str(g["id"]) for g in selected["games"]}) != len(selected["games"]):
        raise ValueError("INVALID_SCHEDULE_COVERAGE")
    with TemporaryDirectory(prefix="nfl-shadow-only-") as tmp:
        data = pathlib.Path(tmp)
        for name in FILES:
            (data / name).write_bytes((input_dir / name).read_bytes())
        for name in OPTIONAL:
            if (input_dir / name).exists():
                (data / name).write_bytes((input_dir / name).read_bytes())
        with patch.object(model_c_engine, "DATA", data), patch.object(model_c_qb_shadow, "DATA", data), patch.object(four, "DATA", data):
            # Real Model C and C-QB engines run; no repository files are modified.
            model_c_engine.main()
            model_c_qb_shadow.main()
            draft = json.loads((data / "model-c-automated-draft.json").read_text())
            shadow = json.loads((data / "model-c-qb-shadow.json").read_text())
            # Real A/B calculation from existing comparison engine, not a new surrogate.
            card = four.freeze(draft, shadow, history, now)
    if (draft["season"], draft["week"]) != (schedule["season"], selected["week"]):
        raise ValueError("STALE_MODEL_C_WEEK")
    if len(card["games"]) != len(selected["games"]) or any(set(g["picks"]) != {"A", "B", "C", "C-QB"} for g in card["games"]):
        raise ValueError("INCOMPLETE_FOUR_MODEL_HANDOFF")
    # No independent schedule confirmation, frozen source hashes, calibrated scores or
    # complete official QB evidence is supplied by this runner. Do not mark delivery ready.
    result = validate(schedule, card, now)
    return {"status": "RESEARCH_ONLY_NOT_DELIVERABLE", "season": draft["season"],
            "week": draft["week"], "games": len(card["games"]),
            "winnerRows": sum(len(g["picks"]) for g in card["games"]),
            "realEngines": ["model_c_engine", "model_c_qb_shadow", "nfl_four_model_head_to_head.freeze"],
            "readiness": result, "published": False}

if __name__ == "__main__":
    try:
        print(json.dumps(rehearse(ROOT / "data", dt.datetime.now(dt.timezone.utc)), indent=2))
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED", "reason":str(exc)}))
        sys.exit(1)
