#!/usr/bin/env python3
"""Regression: distinct C total, verified-only C-QB total, frozen winner picks."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from nfl_four_model_totals_research import build

def test():
    history=[]
    for i in range(6):
        for team,opponent in (("Home","Other H"),("Away","Other A")):
            history.append({"season":2026,"date":f"2026-09-{i+1:02d}T12:00:00Z",
                "home":team,"away":opponent,"homeScore":14+i*3,"awayScore":10+i*2})
    card={"season":2026,"week":8,"frozenAt":"2026-10-20T12:00:00Z",
          "games":[{"id":"1","date":"2026-10-29T20:15:00Z","home":"Home","away":"Away",
                    "picks":{m:"Home" for m in ("A","B","C","C-QB")},
                    "modelCHomeEdgePoints":4,"qbHomeEdgeAdjustment":2}]}
    original=copy.deepcopy(card)
    out=build(card,history)["games"][0]["models"]
    assert out["C"]["projectedTotal"]!=out["A"]["projectedTotal"],out
    assert out["C-QB"]["projectedTotal"]==out["C"]["projectedTotal"],out
    assert all(out[m]["winnerPick"]=="Home" for m in out)
    assert card==original,"Frozen input changed"
    card["games"][0]["verifiedQbTotalAdjustment"]=-3
    changed=build(card,history)["games"][0]["models"]
    assert changed["C-QB"]["projectedTotal"]<changed["C"]["projectedTotal"],changed
    assert changed["C"]["projectedTotal"]==out["C"]["projectedTotal"]
    print("PASS: C distinct total; C-QB verified-only impact; frozen input")
if __name__=="__main__":test()
