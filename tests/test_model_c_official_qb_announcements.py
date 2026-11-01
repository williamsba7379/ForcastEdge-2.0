#!/usr/bin/env python3
"""Offline fail-closed official announcement fixtures."""
import importlib.util
import pathlib
spec = importlib.util.spec_from_file_location("announcements", pathlib.Path(__file__).resolve().parents[1] / "scripts/model_c_official_qb_announcements.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def page(body, date="Oct 30, 2026 at 01:56 PM"):
    return "<html><h1>Official injury report</h1><p>" + date + "</p><p>" + body + "</p></html>"
statement = "Head Coach Jesse Minter announced Friday that Jackson will play against the Buffalo Bills"
r = mod.classify("BAL", page(statement))
assert r["evidence"] == "COACH_ANNOUNCED_AVAILABLE_FOR_MATCHUP"
assert r["starterConfirmed"] is False and r["depthChartFreshnessAffected"] is False
for team in ("BUF", "PIT"):
    r = mod.classify(team, page("Injury report. No quarterback announcement."))
    assert r["evidence"] == "DATED_REPORT_NO_DIRECT_QB_STARTER_ANNOUNCEMENT"
    assert r["starterConfirmed"] is False
assert mod.classify("BAL", page(statement, "Undated"))["evidence"] == "NONE"
assert mod.classify("BAL", "<script>Oct 30, 2026 at 01:56 PM</script>" + statement)["evidence"] == "NONE"
assert mod.classify("BAL", page("Lamar Jackson is listed on the depth chart"))["starterConfirmed"] is False
print("PASS: official announcement classification and fail-closed boundaries")
