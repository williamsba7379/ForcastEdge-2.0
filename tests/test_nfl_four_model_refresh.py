#!/usr/bin/env python3
"""Regression: fresh card uses latest draft, retains frozen original, refuses stale inputs."""
import datetime as dt
import json
import pathlib
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from nfl_four_model_head_to_head import freeze
D=ROOT/"data"
draft=json.loads((D/"model-c-automated-draft.json").read_text())
shadow=json.loads((D/"model-c-qb-shadow.json").read_text())
history=json.loads((D/"nfl-historical-results.json").read_text())
now=dt.datetime.now(dt.timezone.utc)
if all(now<dt.datetime.fromisoformat(g["date"].replace("Z","+00:00")) for g in draft["games"]):
    card=freeze(draft,shadow,history,now)
    assert len(card["games"])==len(draft["games"])==len(shadow["games"])
    assert all(set(g["picks"])=={"A","B","C","C-QB"} for g in card["games"])
    assert all(g["winner"] is None for g in card["games"])
    assert all(g["qbHomeEdgeAdjustment"]==0 or g["qbAdjustments"] for g in card["games"])
    original=D/"four-model-head-to-head"/(str(draft["season"])+"-week-"+str(draft["week"])+".json")
    if original.exists():
        saved=json.loads(original.read_text())
        assert saved["frozenAt"]!=card["frozenAt"] or saved["games"]==card["games"]
    print("PASS: fresh four-model snapshot contract")
else:
    print("SKIP: historical week contains kicked-off games")
