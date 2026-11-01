#!/usr/bin/env python3
"""Fail-closed fixtures for depth-chart date evidence."""
import importlib.util
import pathlib
root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("date_evidence", root / "scripts/model_c_official_qb_date_evidence.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def check(html, expected):
    result = mod.evidence(html)
    assert result["dates"] == expected, result
check("<h1>Depth Chart</h1><p>Updated as of 10/30/26</p><h2>Offense</h2>", ["10/30/26"])
check("<h1>Depth Chart</h1><p>As of Oct 30, 2026</p><h2>Offense</h2>", ["Oct 30, 2026"])
check("<meta content='2026-10-31'><h1>Depth Chart</h1><h2>Offense</h2><p>Updated as of 10/30/26</p>", [])
check("<h1>Depth Chart</h1><h2>Offense</h2><article>Updated as of 10/30/26</article>", [])
check("<h1>Depth Chart</h1><script>Updated as of 10/30/26</script><h2>Offense</h2>", [])
check("<h1>Depth Chart</h1><p>Updated as of 10/30/26; Updated as of 10/29/26</p><h2>Offense</h2>", ["10/30/26", "10/29/26"])
assert mod.evidence("<p>Updated as of 10/30/26</p>")["dates"] == []
print("PASS: bounded date evidence and metadata/news exclusion")
