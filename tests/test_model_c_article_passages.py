#!/usr/bin/env python3
"""Offline test of review-only QB article passages."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_article_passages import extract,collect

sample="<p>Lamar Jackson was limited at practice.</p><p>Josh Allen is questionable.</p><p>Lamar Jackson met fans.</p>"
assert extract(sample,["Lamar Jackson"])==["Lamar Jackson was limited at practice."]
assert extract(sample,["Tyler Huntley"])==[]
assert extract("<p>Quarterback Lamar Jackson is seen during practice on Thursday.</p>",["Lamar Jackson"])==[]
print("PASS: own-QB passage extraction and photo-caption exclusion")

ranked={"items":[{"gameId":"g1","team":"Baltimore Ravens","rankedLinks":[{"url":"https://www.baltimoreravens.com/news/old"},{"url":"https://www.baltimoreravens.com/news/new"}]}]}
discovery={"teams":[{"team":"Baltimore Ravens","officialNewsIndex":"https://www.baltimoreravens.com/news/"}]}
queue={"items":[{"gameId":"g1","team":"Baltimore Ravens","recentPrimaryPasserCandidate":"Lamar Jackson","reportedInjuryFlags":[]}]}
audit={"items":[{"gameId":"g1","team":"Baltimore Ravens","url":"https://www.baltimoreravens.com/news/old","publicationWindow":"OLDER_THAN_SEVEN_DAYS"},{"gameId":"g1","team":"Baltimore Ravens","url":"https://www.baltimoreravens.com/news/new","publicationWindow":"WITHIN_SEVEN_DAYS"}]}
calls=[]
def fake_fetch(url,base):
    calls.append(url)
    return sample
result=collect(discovery,ranked,queue,fetch=fake_fetch,publication_audit=audit)
assert len(calls)==1 and calls[0].endswith("/new")
assert result["items"][0]["fetchStatus"]=="SKIPPED_NOT_RECENT_VERIFIED"
assert result["items"][1]["passages"]==["Lamar Jackson was limited at practice."]
assert result["automaticConfirmations"]==0
print("PASS: verified recency gate skips old articles and preserves review-only mode")
