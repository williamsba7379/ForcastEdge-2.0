#!/usr/bin/env python3
"""Fail closed on structural Model C draft problems; preserve review-only status."""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
def check():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    assert draft.get("status")=="AUTOMATED_REVIEW_ONLY"
    assert draft.get("reviewRequired") is True
    games=draft.get("games",[])
    assert 10<=len(games)<=16
    ids=set()
    for game in games:
        assert game["id"] not in ids
        ids.add(game["id"])
        assert game["pick"] in (game["away"],game["home"])
        assert game.get("rating")=="NO BET"
        assert game.get("confidence")=="UNVALIDATED"
        assert "qbReviewAlerts" in game
        for side in ("home","away"):
            alert=game["qbReviewAlerts"][side]
            assert isinstance(alert["injuryFlags"],list)
            assert isinstance(alert["reportedQbAvailability"],list)
            allowed={"NON_INJURY_INACTIVE","REPORTED_UNAVAILABLE","UNCERTAIN","REPORTED_AVAILABLE","UNKNOWN"}
            for item in alert["reportedQbAvailability"]:
                assert item["category"] in allowed
                assert item["sourceType"]=="UNVERIFIED_REPORTING_FEED"
            for flag in alert["injuryFlags"]:
                assert any(item["name"]==flag["name"] and item["category"] in ("REPORTED_UNAVAILABLE","UNCERTAIN") for item in alert["reportedQbAvailability"])
            assert isinstance(alert["candidateMismatch"],bool)
            assert alert["starterConfirmed"] == (game["quarterbacks"][side]["verification"]=="OFFICIAL_GAME_SPECIFIC")
            qb=game.get("quarterbacks",{}).get(side,{})
            if qb.get("verification")!="OFFICIAL_GAME_SPECIFIC":
                assert qb.get("starter") is None, "Unverified starter presented as confirmed"
            assert qb.get("depthChartIsConfirmedStarter") is False
            assert qb.get("recentPrimaryPasserIsConfirmedStarter") is False
            comparison=game.get("qbPerformanceComparisons",{}).get(side,{})
            if qb.get("verification")!="OFFICIAL_GAME_SPECIFIC":
                assert comparison.get("status")=="INSUFFICIENT_DATA"
            assert comparison.get("estimatedPoints") is None
    print("PASS: Model C review-only output validated:",len(games),"games")

if __name__=="__main__":check()
