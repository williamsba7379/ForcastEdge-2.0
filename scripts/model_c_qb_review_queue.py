#!/usr/bin/env python3
"""Build a game-specific QB review queue; never auto-confirm starters."""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def build(draft, reviewed, declarations):
    sources=reviewed.get("sources",[])
    confirmed=declarations.get("teams",{})
    items=[]
    for game in draft.get("games",[]):
        for side in ("away","home"):
            team=game[side]
            qb=game.get("quarterbacks",{}).get(side,{})
            alert=game.get("qbReviewAlerts",{}).get(side,{})
            relevant=[s for s in sources if s.get("team")==team]
            flags=alert.get("injuryFlags",[])
            items.append({
                "gameId":game["id"],"kickoff":game["date"],"team":team,
                "opponent":game["home" if side=="away" else "away"],
                "starterVerification":qb.get("verification","UNCONFIRMED"),
                "reviewRequired":qb.get("verification")!="OFFICIAL_GAME_SPECIFIC" or bool(flags) or bool(alert.get("candidateMismatch")),
                "reportedInjuryFlags":flags,
                "recentPrimaryPasserCandidate":qb.get("recentPrimaryPasser"),
                "depthChartCandidate":qb.get("depthChartQB1Candidate"),
                "officialSourcesForManualReview":relevant,
                "sourceMatchNote":"Sources are historical/contextual only; reviewer must check exact game and kickoff.",
                "declarationExists":team in confirmed,
                "action":"Check a dated, game-specific team starter announcement. Do not infer from inactives or depth chart."
            })
    return {"status":"HUMAN_REVIEW_QUEUE_ONLY","season":draft.get("season"),"week":draft.get("week"),
            "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "automaticConfirmations":0,"games":len(draft.get("games",[])),
            "items":items}

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    reviewed=json.loads((DATA/"model-c-official-qb-source-review.json").read_text())
    declarations=json.loads((DATA/"model-c-qb-starters.json").read_text())
    out=build(draft,reviewed,declarations)
    (DATA/"model-c-qb-review-queue.json").write_text(json.dumps(out,indent=2)+"\n")
    print("QB review queue:",len(out["items"]),"team-game records; no auto-confirmations")

if __name__=="__main__":main()
