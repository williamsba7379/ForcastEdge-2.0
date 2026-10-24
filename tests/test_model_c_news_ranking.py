#!/usr/bin/env python3
"""Offline QB news relevance and safety fixtures."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_news_ranking import build

game={"gameId":"test-game","kickoff":"2026-11-01T18:00Z","team":"Baltimore Ravens",
      "opponent":"Buffalo Bills","recentPrimaryPasserCandidate":"Lamar Jackson",
      "depthChartCandidate":None,"reportedInjuryFlags":[]}
news={"teams":[{"team":"Baltimore Ravens","fetchStatus":"OK","candidates":[
    {"url":"https://www.baltimoreravens.com/news/lamar-jackson-injury","headline":"Lamar Jackson injury update Oct 30, 2026"},
    {"url":"https://www.baltimoreravens.com/news/general-update","headline":"General update Oct 01, 2026"},
    {"url":"https://www.baltimoreravens.com/news/starting-quarterback","headline":"Starting quarterback for Buffalo Bills Nov 02, 2026"}]}]}
output=build(news,{"season":2026,"week":8,"items":[game]})
ranked=output["items"][0]["rankedLinks"]
assert ranked[0]["url"].endswith("lamar-jackson-injury"),ranked
assert ranked[-1]["score"]<ranked[0]["score"],ranked
assert output["automaticConfirmations"]==0
assert all(x["status"]=="UNVERIFIED_LINK_FOR_HUMAN_REVIEW" for x in ranked)
assert all("score" in x and "reasons" in x for x in ranked)
assert build({"teams":[]},{"items":[game]})["items"][0]["rankedLinks"]==[]
print("PASS: relevance ranking, game dates and no automatic starter declarations")
