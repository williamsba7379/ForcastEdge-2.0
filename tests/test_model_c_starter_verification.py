#!/usr/bin/env python3
"""Offline synthetic fixtures. URLs are examples, not verified real announcements."""
import datetime as dt
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_engine import official_starter_valid

now=dt.datetime(2026,10,23,16,0,tzinfo=dt.timezone.utc)
game={"id":"fixture-001","date":"2026-10-25T17:00:00Z"}
team="Example Team"
good={"status":"CONFIRMED_STARTER","sourceType":"TEAM_ANNOUNCEMENT",
      "reviewed":True,"evidenceText":"Team explicitly names Alex Example starting quarterback for fixture-001.",
      "team":team,"gameId":game["id"],"starter":"Alex Example",
      "source":"https://example.com/team-announcement",
      "asOf":"2026-10-23T15:00:00Z"}
assert official_starter_valid(good,game,team,now)
cases={
    "missing declaration":None,
    "depth chart":dict(good,sourceType="DEPTH_CHART"),
    "official inactives":dict(good,sourceType="OFFICIAL_INACTIVES"),
    "not reviewed":dict(good,reviewed=False),
    "no evidence":dict(good,evidenceText=""),
    "too-short evidence":dict(good,evidenceText="Starter."),
    "wrong game":dict(good,gameId="fixture-002"),
    "wrong team":dict(good,team="Other Team"),
    "missing starter":dict(good,starter=""),
    "unsecured URL":dict(good,source="http://example.com"),
    "future report":dict(good,asOf="2026-10-24T15:00:00Z"),
    "after kickoff":dict(good,asOf="2026-10-25T18:00:00Z"),
    "stale report":dict(good,asOf="2026-10-01T15:00:00Z"),
    "naive timestamp":dict(good,asOf="2026-10-23T15:00:00"),
    "malformed timestamp":dict(good,asOf="not-a-date"),
    "not confirmed":dict(good,status="EXPECTED_STARTER"),
}
for name,record in cases.items():
    assert not official_starter_valid(record,game,team,now),name
print("PASS: synthetic official QB declaration accepted; %d invalid declarations rejected."%len(cases))
