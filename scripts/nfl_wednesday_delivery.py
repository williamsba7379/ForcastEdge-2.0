"""Isolated Wednesday handoff contract; does not run engines or publish.

Existing engine entrypoints are deliberately NOT executed by this unvalidated
review-branch scaffold. Their inputs and outputs need separate acceptance tests.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.nfl_wednesday_freeze import prepare

ET = ZoneInfo("America/New_York")


def handoff(schedule, card, evidence, *, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    candidate = prepare(schedule, card, evidence, now=now)
    return {"status": candidate["status"], "candidate": candidate,
            "deliveryDeadlineET": now.astimezone(ET).date().isoformat() + "T11:00:00 America/New_York",
            "enginesExecuted": False, "published": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = handoff(*(json.loads(path.read_text()) for path in
                       (args.schedule, args.card, args.evidence)))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "VERIFIED_RELEASE_CANDIDATE_NOT_PUBLISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
