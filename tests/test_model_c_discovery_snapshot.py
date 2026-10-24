#!/usr/bin/env python3
"""Validate the saved official NFL news discovery snapshot against enabled teams."""
import json
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_official_news import OFFICIAL_TEAM_NEWS

data=json.loads((pathlib.Path(__file__).resolve().parents[1]/"data/model-c-official-qb-discovery.json").read_text())
teams=data.get("teams",[])
found={t["team"]:t for t in teams}
expected=set(OFFICIAL_TEAM_NEWS)
assert len(expected)==32, f"Collector configured for {len(expected)} teams, expected 32"
assert set(found)==expected, f"Missing: {sorted(expected-set(found))}; extra: {sorted(set(found)-expected)}"
assert len(teams)==len(found), "Duplicate team entries"
assert data.get("automaticConfirmations")==0, "Discovery must never confirm starters"
for name,record in found.items():
    assert record["officialNewsIndex"]==OFFICIAL_TEAM_NEWS[name], name
    if record["fetchStatus"]=="OK":
        assert isinstance(record["candidates"],list), name
        assert all(c.get("status")=="UNVERIFIED_LINK_FOR_HUMAN_REVIEW" for c in record["candidates"]),name
    else:
        assert record["fetchStatus"]=="ERROR" and not record["candidates"],name
print("PASS: 32-team discovery snapshot complete; failures:",
      [n for n,r in found.items() if r["fetchStatus"]!="OK"])
