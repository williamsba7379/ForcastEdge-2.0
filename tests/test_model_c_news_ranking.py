#!/usr/bin/env python3
"""Offline QB news relevance and safety fixtures."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_news_ranking import build,rank_link

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

# A recent report about the opposing QB must not outrank the home team's own QB.
own=rank_link(game,{"url":"https://www.baltimoreravens.com/news/lamar-jackson-injury",
                    "headline":"Lamar Jackson injury update Oct 30, 2026"})
other=rank_link(game,{"url":"https://www.baltimoreravens.com/news/josh-allen-update",
                      "headline":"Buffalo Bills quarterback Josh Allen injury update Oct 30, 2026"})
assert own["score"]>other["score"],(own,other)
assert "OWN_QB_CANDIDATE" in own["reasons"]
assert "OPPONENT_WITHOUT_OWN_QB" in other["reasons"]
assert own["pregameShortlistEligible"] and not other["pregameShortlistEligible"]

# A date-valid generic injury story cannot become a team QB lead.
generic=rank_link(game,{"url":"https://www.baltimoreravens.com/news/defensive-injury",
    "headline":"Defense injury report Oct 30, 2026"})
assert not generic["pregameShortlistEligible"]
assert "OWN_QB_STATUS_NOT_ESTABLISHED" in generic["reasons"]
