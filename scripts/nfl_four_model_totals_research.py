#!/usr/bin/env python3
"""Experimental projected scores for A/B/C/C-QB; no invented sportsbook lines.
Uses only completed same-season games before the snapshot, never post-kickoff.
This is a research-only companion to the immutable winner cards.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from nfl_four_model_head_to_head import stamp
from model_c_engine import extract_history

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def team_scores(history, team):
    return [(home_score, away_score) if home == team else (away_score, home_score)
            for _, away, home, away_score, home_score in history if team in (home, away)]


def projection(scores, recent_weight):
    return tuple((1 - recent_weight) * mean(values) + recent_weight * mean(values[-3:])
                 for values in zip(*scores))


def tempo_adjustment(home_scores, away_scores):
    """Estimate recent combined scoring relative to the season baseline."""
    adjustments = []
    for scores in (home_scores, away_scores):
        totals = [scored + allowed for scored, allowed in scores]
        adjustments.append(mean(totals[-3:]) - mean(totals))
    return max(-4.0, min(4.0, 0.25 * mean(adjustments)))


def build(card,history):
    now=stamp(card["frozenAt"])
    completed = [game for game in history if game.get("isFinal") is not False and
                 str(game.get("status", "")).upper() in ("", "FINAL", "STATUS_FINAL", "COMPLETED")]
    scores = [row for row in extract_history(completed, now, card["season"])
              if all(math.isfinite(score) and score >= 0 for score in row[3:])]
    out=[]
    for game in card["games"]:
        away_scores = team_scores(scores, game["away"])
        home_scores = team_scores(scores, game["home"])
        if now>=stamp(game["date"]):raise ValueError("Not pregame: "+game["id"])
        models={}
        for model,weight in (("A",.3),("B",0),("C",.3),("C-QB",.3)):
            if min(len(away_scores), len(home_scores)) < 3:
                models[model]={"status":"INSUFFICIENT_HISTORY","projectedTotal":None,
                               "overUnderPick":None,"spreadPick":None}
                continue
            away = projection(away_scores, weight)
            home = projection(home_scores, weight)
            homepts=(home[0]+away[1])/2+0.75
            awaypts=(away[0]+home[1])/2-0.75
            if model in ("C","C-QB"):
                tempo = tempo_adjustment(home_scores, away_scores)
                # C changes the combined total using recent game scoring environment.
                homepts+=tempo/2
                awaypts+=tempo/2
                # C-QB changes the combined total only with reviewed QB-specific
                # scoring impact; a home-edge change alone affects margin, not total.
                if model=="C-QB":
                    qb_total=game.get("verifiedQbTotalAdjustment")
                    if type(qb_total) in (int,float):
                        qb_total=max(-6.0,min(6.0,float(qb_total)))
                        homepts+=qb_total/2
                        awaypts+=qb_total/2

                # Preserve the corresponding model's independently computed home-edge
                # while using a historical offense/defense total estimate.
                draft_edge=game.get("modelCHomeEdgePoints")
                if model=="C-QB" and draft_edge is not None:
                    draft_edge+=game.get("qbHomeEdgeAdjustment",0)
                if draft_edge is not None:
                    total=homepts+awaypts
                    homepts=(total+draft_edge)/2
                    awaypts=(total-draft_edge)/2
            models[model]={"status":"EXPERIMENTAL_UNCALIBRATED","projectedHome":round(max(0,homepts),1),
                "projectedAway":round(max(0,awaypts),1),"projectedTotal":round(max(0,homepts)+max(0,awaypts),1),
                "overUnderPick":None,"spreadPick":None,
                "totalMethod":{"A":"RECENCY_WEIGHTED_OFFENSE_DEFENSE","B":"SEASON_OFFENSE_DEFENSE",
                               "C":"RECENCY_PLUS_SCORING_ENVIRONMENT",
                               "C-QB":"SCORING_ENVIRONMENT_PLUS_VERIFIED_QB_TOTAL_ONLY"}[model],
                "note":"Experimental, uncalibrated. C-QB total equals C without verified QB total impact; no sportsbook pick without sourced market line."}
        for model in models:
            models[model]["winnerPick"]=game["picks"][model]
        out.append({"id":game["id"],"date":game["date"],"home":game["home"],"away":game["away"],"models":models})
    return {"season":card["season"],"week":card["week"],"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceComparisonFrozenAt":card["frozenAt"],"status":"RESEARCH_ONLY_NO_MARKET_LINES",
        "warning":"Experimental uncalibrated totals: C uses recent scoring environment; C-QB differs only with verified QB-specific total impact. No sportsbook lines, no O/U or ATS picks.",
        "games":out}

def build_from_draft(card, history, draft):
    edges={str(g["id"]):g["homeEdgePoints"] for g in draft["games"]}
    games = [{**game, "modelCHomeEdgePoints": edges.get(str(game["id"]))}
             for game in card["games"]]
    return build({**card, "games": games}, history["games"])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("comparison", "history", "draft", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    card, history, draft = (json.loads(path.read_text())
                            for path in (args.comparison, args.history, args.draft))
    result = build_from_draft(card, history, draft)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
    print(args.output, len(result["games"]), "games")
if __name__=="__main__":main()
