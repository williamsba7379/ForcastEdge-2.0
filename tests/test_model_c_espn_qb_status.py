#!/usr/bin/env python3
"""ESPN structured QB injury extraction remains review-only."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_injuries import qb_report

teams=[{"team":"Example Team","players":[
    {"name":"Player A","position":"QB","status":"Questionable","description":"Ankle"},
    {"name":"Player B","position":"WR","status":"Out","description":"Knee"},
    {"name":"Player C","position":"QB","status":"Active","description":""}]}]
report=qb_report(teams,"2026-10-23T12:00:00+00:00")
assert len(report["items"])==2
assert all(x["starterConfirmed"] is False and x["reviewRequired"] for x in report["items"])
assert report["automaticConfirmations"]==0
assert report["items"][0]["reportedStatus"]=="Questionable"
print("PASS: structured ESPN QB statuses are informational, never starter confirmations")
