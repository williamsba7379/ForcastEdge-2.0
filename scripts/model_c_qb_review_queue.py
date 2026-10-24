#!/usr/bin/env python3
"""Build a game-specific QB review queue; never auto-confirm starters."""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def injury_priority(flags, candidate, depth_candidate=None):
    """Review urgency, not a prediction or proof of starting status."""
    if not flags:
        return "ROUTINE"
    severe={"out","injured reserve","ir","doubtful"}
    moderate={"questionable","limited"}
    watched={str(n).casefold() for n in (candidate,depth_candidate) if n}
    matched=[x for x in flags if str(x.get("player","")).casefold() in watched]
    relevant=matched or flags
    statuses={x.get("reportedStatus","").strip().casefold() for x in relevant}
    if statuses & severe:
        return "HIGH" if matched else "ELEVATED"
    if statuses & moderate:
        return "ELEVATED" if matched else "STANDARD"
    return "STANDARD"

def build(draft, reviewed, declarations, espn=None):
    sources=reviewed.get("sources",[])
    confirmed=declarations.get("teams",{})
    espn_items=(espn or {}).get("items",[])
    items=[]
    for game in draft.get("games",[]):
        for side in ("away","home"):
            team=game[side]
            qb=game.get("quarterbacks",{}).get(side,{})
            alert=game.get("qbReviewAlerts",{}).get(side,{})
            # Only attach a source as game-specific when the exact game ID matches.
            # Older team reports remain context, never evidence of this game's starter.
            relevant=[s for s in sources if s.get("team")==team]
            exact=[s for s in relevant if str(s.get("gameId",""))==str(game["id"])]
            historical=[s for s in relevant if str(s.get("gameId",""))!=str(game["id"])]
            candidate=qb.get("recentPrimaryPasser")
            search_queries=[
                f'{team} official site starting quarterback {game["date"][:10]}',
                f'{team} {candidate or "quarterback"} named starter vs {game["home" if side=="away" else "away"]}'
            ]
            flags=alert.get("injuryFlags",[])
            espn_flags=[x for x in espn_items if x.get("team")==team and x.get("reportedStatus","").lower() not in ("active","healthy","available")]
            depth=qb.get("depthChartQB1Candidate")
            priority=injury_priority(espn_flags,candidate,depth)
            agreement=bool(candidate and depth and candidate.casefold()==depth.casefold())
            conflict=bool(candidate and depth and not agreement)
            items.append({
                "gameId":game["id"],"kickoff":game["date"],"team":team,
                "opponent":game["home" if side=="away" else "away"],
                "starterVerification":qb.get("verification","UNCONFIRMED"),
                "reviewRequired":qb.get("verification")!="OFFICIAL_GAME_SPECIFIC" or bool(flags) or bool(espn_flags) or bool(alert.get("candidateMismatch")),
                "reportedInjuryFlags":flags,
                "espnQuarterbackInjuryFlags":espn_flags,
                "espnInjuryReviewPriority":priority,
                "espnPriorityIsPrediction":False,
                "recentPrimaryPasserCandidate":qb.get("recentPrimaryPasser"),
                "depthChartCandidate":depth,
                "tentativeExpectedStarter":candidate if agreement else None,
                "quarterbackIndicatorConflict":conflict,
                "quarterbackReviewPriority":"CONFLICT_REVIEW" if conflict else ("INDICATORS_AGREE" if agreement else "INSUFFICIENT_DATA"),
                "expectedStarterEvidence":"TWO_INDICATORS_AGREE_NOT_CONFIRMED" if agreement else "INSUFFICIENT_OR_CONFLICTING_INDICATORS",
                "confirmedStarter":qb.get("starter") if qb.get("verification")=="OFFICIAL_GAME_SPECIFIC" else None,
                "officialSourcesForManualReview":exact,
                "historicalSourcesForContextOnly":historical,
                "officialSourceSearchQueries":search_queries,
                "sourceEvidenceStatus":"GAME_SPECIFIC_SOURCE_REVIEW_REQUIRED" if not exact else "GAME_SPECIFIC_SOURCE_FOUND_NOT_CONFIRMED",
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
    espn_path=DATA/"model-c-espn-qb-status.json"
    espn=json.loads(espn_path.read_text()) if espn_path.exists() else {}
    out=build(draft,reviewed,declarations,espn)
    (DATA/"model-c-qb-review-queue.json").write_text(json.dumps(out,indent=2)+"\n")
    print("QB review queue:",len(out["items"]),"team-game records; no auto-confirmations")

if __name__=="__main__":main()
