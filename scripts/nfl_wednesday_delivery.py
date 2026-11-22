"""Review-only handoff to an injected existing-engine calculation, never publication.

Caller must supply an isolated callable bound to the existing
nfl_four_model_head_to_head.freeze(draft, shadow, history, now).
Do not import that module here: it creates directories at import time.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.nfl_wednesday_freeze import prepare

ET = ZoneInfo("America/New_York")


def handoff(schedule, draft, shadow, history, evidence, *, now=None,
            existing_engine=None, isolated=False, sources=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not isolated or existing_engine is None or not callable(existing_engine):
        return {"status": "DELIVERY_BLOCKED", "reason": "NO_ISOLATED_EXISTING_ENGINE",
                "enginesExecuted": False, "published": False}
    try:
        # Existing function only. Never call its writing/grading main().
        card = existing_engine(draft, shadow, history, now)
        if not isinstance(card, dict):
            raise ValueError("INVALID_ENGINE_RESULT")
        decision = prepare(schedule, card, evidence, now=now, sources=sources)
        return {"status": decision["status"], "candidate": decision,
                "enginesExecuted": True, "published": False,
                "deliveryDeadlineET": now.astimezone(ET).date().isoformat() + "T11:00:00 America/New_York"}
    except Exception:
        return {"status": "DELIVERY_BLOCKED", "reason": "ENGINE_OR_INPUT_FAILURE",
                "enginesExecuted": True, "published": False}


def main():
    # No default execution path: independent isolation and source evidence
    # are required before an existing engine callable can be supplied.
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-only", action="store_true")
    parser.parse_args()
    print(json.dumps({"status": "DELIVERY_BLOCKED", "reason": "NO_APPROVED_ISOLATED_ENGINE_RUN",
                      "published": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
