#!/usr/bin/env python3
"""Validate review-only QB passage publication window."""
import json
import pathlib

data=pathlib.Path(__file__).resolve().parents[1]/"data"
audit=json.loads((data/"model-c-article-metadata-audit.json").read_text())
passages=json.loads((data/"model-c-qb-article-passages.json").read_text())
windows={(x["gameId"],x["team"],x["url"]):x["publicationWindow"] for x in audit["items"]}
for item in passages["items"]:
    key=(item["gameId"],item["team"],item["url"])
    if windows.get(key)!="WITHIN_SEVEN_DAYS":
        assert item["passages"]==[],key
        assert item["fetchStatus"]=="SKIPPED_NOT_RECENT_VERIFIED",key
    assert item["starterConfirmed"] is False
assert passages["automaticConfirmations"]==0
print("PASS: no outdated QB passages and no starter confirmations")
