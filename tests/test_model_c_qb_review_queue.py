#!/usr/bin/env python3
"""Offline QB review-queue source isolation tests."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_qb_review_queue import build

draft={"season":2026,"week":8,"games":[{"id":"game-new","date":"2026-11-01T18:00Z","away":"Team A","home":"Team B",
"quarterbacks":{"away":{"verification":"UNCONFIRMED","recentPrimaryPasser":"QB A"},"home":{"verification":"UNCONFIRMED"}},
"qbReviewAlerts":{"away":{"injuryFlags":[]},"home":{"injuryFlags":[]}}}]}
reviewed={"sources":[{"team":"Team A","gameId":"game-old","source":"https://example.com/old"},
{"team":"Team A","gameId":"game-new","source":"https://example.com/new"},
{"team":"Team B","source":"https://example.com/undated"}]}
out=build(draft,reviewed,{"teams":{}})
assert out["automaticConfirmations"]==0
assert len(out["items"])==2
a,b=out["items"]
assert len(a["officialSourcesForManualReview"])==1
assert a["officialSourcesForManualReview"][0]["gameId"]=="game-new"
assert len(a["historicalSourcesForContextOnly"])==1
assert len(b["officialSourcesForManualReview"])==0
assert len(b["historicalSourcesForContextOnly"])==1
assert all(x["reviewRequired"] for x in out["items"])
assert all(len(x["officialSourceSearchQueries"])==2 for x in out["items"])
print("PASS: game-specific source filtering, historical isolation, search leads and no auto-confirmations")

espn={"items":[{"team":"Team A","player":"QB A","reportedStatus":"Questionable","starterConfirmed":False},{"team":"Team B","player":"QB B","reportedStatus":"Active","starterConfirmed":False}]}
with_espn=build(draft,reviewed,{"teams":{}},espn)
assert len(with_espn["items"][0]["espnQuarterbackInjuryFlags"])==1
assert with_espn["items"][1]["espnQuarterbackInjuryFlags"]==[]
assert with_espn["automaticConfirmations"]==0
print("PASS: ESPN injury flags assigned only to matching team")

from model_c_qb_review_queue import injury_priority
assert injury_priority([{"player":"QB A","reportedStatus":"Out"}],"QB A")=="HIGH"
assert injury_priority([{"player":"QB A","reportedStatus":"Questionable"}],"QB A")=="ELEVATED"
assert injury_priority([{"player":"Backup","reportedStatus":"Out"}],"QB A")=="ELEVATED"
assert injury_priority([{"player":"Backup","reportedStatus":"Questionable"}],"QB A")=="STANDARD"
assert injury_priority([],"QB A")=="ROUTINE"
assert with_espn["items"][0]["espnInjuryReviewPriority"]=="ELEVATED"
assert with_espn["items"][0]["espnPriorityIsPrediction"] is False
print("PASS: QB injury urgency is review-only and candidate-aware")

assert with_espn["items"][0]["confirmedStarter"] is None
assert with_espn["items"][0]["tentativeExpectedStarter"] is None
matching={"season":2026,"week":8,"games":[{**draft["games"][0],"quarterbacks":{"away":{"recentPrimaryPasser":"QB A","depthChartQB1Candidate":"QB A"},"home":{}}}]}
result=build(matching,reviewed,{"teams":{}},espn)
assert result["items"][0]["tentativeExpectedStarter"]=="QB A"
assert result["items"][0]["confirmedStarter"] is None
print("PASS: matching indicators yield tentative expectation, never official confirmation")
