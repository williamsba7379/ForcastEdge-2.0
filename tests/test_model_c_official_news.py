#!/usr/bin/env python3
"""Offline official team news discovery safety checks."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_official_news import extract_candidates,collect

page='''<a href="/news/quarterback-injury-update">Quarterback injury update</a>
<a href="https://www.philadelphiaeagles.com/news/qb-named-starter">QB named starter</a>
<a href="https://evil.example/news/qb-starting">QB starting</a>
<a href="http://www.baltimoreravens.com/news/qb-starting">QB starting</a>
<a href="/shop/quarterback">Quarterback gear</a>'''
base="https://www.baltimoreravens.com/news/"
links=extract_candidates(page,base)
assert len(links)==1,links
assert links[0]["status"]=="UNVERIFIED_LINK_FOR_HUMAN_REVIEW"
assert links[0]["url"].startswith(base)
result=collect(fetch=lambda url:page)
assert result["automaticConfirmations"]==0
assert len(result["teams"])==32
assert all(t["fetchStatus"]=="OK" for t in result["teams"])
error=collect(fetch=lambda url:(_ for _ in ()).throw(OSError("offline")))
assert all(t["fetchStatus"]=="ERROR" and not t["candidates"] for t in error["teams"])
dynamic=extract_candidates('<a href="/news/bryce-young-update">Bryce Young discusses his status</a>',base,quarterback_names=("Bryce Young",))
assert len(dynamic)==1 and dynamic[0]["url"].endswith("/bryce-young-update")
print("PASS: official-domain isolation, dynamic QB names, review-only discovery and network fail-closed")
