#!/usr/bin/env python3
"""Precommitted, untouched 2021 evaluation of the frozen early-season rule.
Uses 2020 as previous-season input. No tuning or model selection is performed.
2022 was previously inspected and is deliberately excluded.
"""
import json
from pathlib import Path
from nfl_early_season_experiment import season_games, when, score
from nfl_team_strength import team_metrics

def main():
    previous=season_games(2020)
    current=season_games(2021)
    if len(previous)<250 or len(current)<250:
        raise RuntimeError("Incomplete season; do not report a partial evaluation")
    records=[]
    for game in current:
        if game["winner"]=="TIE":
            continue
        earlier=[g for g in current if when(g)<when(game)]
        home=team_metrics(earlier,game["home"])
        away=team_metrics(earlier,game["away"])
        early=home["games"]<2 or away["games"]<2
        source=previous if early else earlier
        edge=score(source,game["home"])-score(source,game["away"])+1.5
        winner=game["home"] if edge>=0 else game["away"]
        records.append({"week":game["week"],"early":early,"correct":winner==game["winner"],"homeCorrect":game["home"]==game["winner"]})
    def stats(rows):
        n=len(rows)
        return {"games":n,"correct":sum(r["correct"] for r in rows),
                "accuracy":round(sum(r["correct"] for r in rows)/n,4) if n else None,
                "homeBaselineCorrect":sum(r["homeCorrect"] for r in rows),
                "homeBaselineAccuracy":round(sum(r["homeCorrect"] for r in rows)/n,4) if n else None}
    output={"status":"One-time historical holdout; precommitted method, no changes after examining 2021 results",
            "testSeason":2021,"priorSeason":2020,
            "frozenMethod":"For each game, use strictly earlier 2021 scores if both teams have >=2 prior games; otherwise use completed 2020 regular season. Strength=0.7*season average point differential+0.3*last-three point differential, home advantage +1.5. Predict home if edge>=0.",
            "cautions":["2021 was not used in the documented 2023-2025 early-season experiment; nevertheless historical tests are not prospective validation.","2020 to 2021 franchise-name changes could cause missing prior-team matches; results should be audited before interpreting.","Ties excluded from accuracy."],
            "all":stats(records),"early":stats([r for r in records if r["early"]]),"established":stats([r for r in records if not r["early"]])}
    target=Path("data/nfl-independent-2021.json")
    target.write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps(output,indent=2))
if __name__=="__main__":main()
