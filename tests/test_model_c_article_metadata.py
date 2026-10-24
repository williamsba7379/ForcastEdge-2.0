#!/usr/bin/env python3
"""Offline official article metadata checks."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_article_metadata import extract_metadata,collect

page='<meta property="article:published_time" content="2026-10-29T14:00:00Z">'
assert extract_metadata(page)["publishedAt"]=="2026-10-29T14:00:00+00:00"
assert extract_metadata('<meta name="date" content="unknown">')["publishedAt"] is None
jsonld='<script type="application/ld+json">{"datePublished":"2026-10-29T14:00:00Z"}</script>'
assert extract_metadata(jsonld)["dateSource"]=="jsonld.datePublished"
ranked={"items":[{"team":"Baltimore Ravens","gameId":"123","rankedLinks":[{"url":"https://www.baltimoreravens.com/news/qb-update"}]}]}
discovery={"teams":[{"team":"Baltimore Ravens","officialNewsIndex":"https://www.baltimoreravens.com/news/"}]}
result=collect(discovery,ranked,fetch=lambda url,base:page)
assert result["automaticConfirmations"]==0
assert result["items"][0]["starterConfirmed"] is False
assert result["items"][0]["fetchStatus"]=="OK"
print("PASS: publication date metadata and no starter confirmation")
