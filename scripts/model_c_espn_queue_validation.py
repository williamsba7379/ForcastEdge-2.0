#!/usr/bin/env python3
"""Check ESPN quarterback flags against game-specific review queue."""
import json
import pathlib
from collections import Counter

data=pathlib.Path(__file__).resolve().parents[1]/"data"
feed=json.loads((data/"model-c-espn-qb-status.json").read_text())
queue=json.loads((data/"model-c-qb-review-queue.json").read_text())
statuses={"active","healthy","available"}
by_team={}
for row in feed["items"]:
    if row["reportedStatus"].strip().lower() not in statuses:
        by_team.setdefault(row["team"],[]).append(row)
matched=0
for row in queue["items"]:
    expected=by_team.get(row["team"],[])
    actual=row["espnQuarterbackInjuryFlags"]
    assert Counter((x["player"],x["reportedStatus"]) for x in actual)==Counter((x["player"],x["reportedStatus"]) for x in expected)
    assert all(x.get("starterConfirmed") is False for x in actual)
    matched+=len(actual)
assert queue["automaticConfirmations"]==0
print("PASS: ESPN QB injury flags match teams; matched flags:",matched)
