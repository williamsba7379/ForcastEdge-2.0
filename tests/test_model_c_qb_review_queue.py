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
