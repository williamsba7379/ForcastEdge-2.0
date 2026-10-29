#!/usr/bin/env python3
"""Controlled grading checks: winner/total outcomes, pushes, pending, and immutability."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from nfl_four_model_totals_grade import grade, MODELS

def game(id, home, away, score=None, market=45, predicted=47, picks=None):
    row={"id":str(id),"home":home,"away":away,
         "models":{m:{"projectedTotal":predicted,"marketTotal":market,
                       "overUnderPick":(picks or {}).get(m,"OVER")} for m in MODELS}}
    final={"id":str(id),"home":home,"away":away,"completed":True,
           "homeScore":score[0],"awayScore":score[1]} if score else None
    return row,final

def test():
    a,fa=game(1,"Home A","Away A",(28,21))
    b,fb=game(2,"Home B","Away B",(21,20),picks={"B":"UNDER"})
    c,fc=game(3,"Home C","Away C",(24,21))
    d,fd=game(4,"Home D","Away D")
    source={"games":[a,b,c,d]}
    original=copy.deepcopy(source)
    history={"games":[fa,fb,fc]}
    result=grade(copy.deepcopy(source),history)
    stats=result["gradingSummary"]
    assert stats["A"]["totalsWins"]==1,stats
    assert stats["A"]["totalsLosses"]==1,stats
    assert stats["A"]["totalsPushes"]==1,stats
    assert stats["B"]["totalsWins"]==2,stats
    assert stats["B"]["totalsPushes"]==1,stats
    assert stats["A"]["totalsAccuracyPct"]==50.0
    assert stats["A"]["totalErrorGames"]==3
    assert result["games"][3]["models"]["A"].get("totalCorrect") is None
    assert source==original,"Original frozen picks mutated"
    assert grade(copy.deepcopy(source),history)["gradingSummary"]==stats,"Nondeterministic grading"
    print("PASS: win/loss/push/pending, accuracy, total error, frozen source, deterministic replay")
if __name__=="__main__":test()
