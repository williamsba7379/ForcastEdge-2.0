#!/usr/bin/env python3
"""Regression tests: historical starter loss is escalated, backups are not guessed."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model_c_qb_injury_audit_v2 import build
D=ROOT/"data"
draft=json.loads((D/"model-c-automated-draft.json").read_text())
shadow=json.loads((D/"model-c-qb-shadow.json").read_text())
history=json.loads((D/"model-c-historical-qb-games.json").read_text())
result=build(draft,shadow,history)
assert len(draft["games"])>0
assert result["reviewCount"]>=0
if draft["season"]==2026 and draft["week"]==8:
    eagles=[a for a in result["alerts"] if a["team"]=="Philadelphia Eagles"]
    assert len(eagles)==1
    assert eagles[0]["priority"]=="P1_ESTABLISHED_PRIMARY_PASSER_ABSENT"
    assert eagles[0]["priorPrimaryPasserGames"].get("Jalen Hurts",0)>=2
    assert eagles[0]["pointsAdjustment"]==0
assert all(a["status"]=="UNMODELED_HUMAN_REVIEW_REQUIRED" for a in result["alerts"])
assert all(a["pointsAdjustment"]==0 for a in result["alerts"])
assert len(shadow["games"])==len(draft["games"])
print("PASS: QB audit regression; no speculative score changes")
