#!/usr/bin/env python3
"""Offline test of review-only QB article passages."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from model_c_article_passages import extract

sample="<p>Lamar Jackson was limited at practice.</p><p>Josh Allen is questionable.</p><p>Lamar Jackson met fans.</p>"
assert extract(sample,["Lamar Jackson"])==["Lamar Jackson was limited at practice."]
assert extract(sample,["Tyler Huntley"])==[]
print("PASS: own-QB passage extraction")
