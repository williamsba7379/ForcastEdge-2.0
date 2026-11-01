#!/usr/bin/env python3
"""Offline fail-closed Step 4G fixtures; no network, no prediction writes."""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("gate", Path(__file__).resolve().parents[1] / "scripts/model_c_qb_game_evidence.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
game = dict(gameId="2026-W8-BAL-BUF", team="BAL", opponent="BUF", quarterback="Lamar Jackson", gameDate="2026-11-01")
report = dict(gameId=game["gameId"], team="BAL", opponent="BUF", quarterback="Lamar Jackson",
              publicationDate="2026-10-30", sourceType="OFFICIAL_TEAM",
              sourceUrl="https://www.baltimoreravens.com/news/example", evidence="AVAILABLE")
def status(g=game, r=None):
    return mod.validate(g, [report if r is None else r])["status"]
assert status() == "READ_ONLY_MATCHED_EVIDENCE"
for field, value in (("gameId", "wrong-game"), ("team", "BUF"), ("opponent", "PIT"), ("quarterback", "Other QB")):
    assert status(r={**report, field: value}) == "MISMATCHED_GAME_OR_QB"
assert status(r={**report, "publicationDate": "2026-10-20"}) == "STALE_OR_FUTURE_EVIDENCE"
assert status(r={**report, "publicationDate": "2026-11-02"}) == "STALE_OR_FUTURE_EVIDENCE"
assert status(r={**report, "publicationDate": "bad"}) == "INVALID_PUBLICATION_DATE"
assert status(r={**report, "sourceType": "UNVERIFIED"}) == "UNVERIFIED_SOURCE"
assert status(r={**report, "evidence": "NO_DIRECT_ANNOUNCEMENT"}) == "NO_DIRECT_QB_ANNOUNCEMENT"
assert mod.validate(game, [report, {**report, "evidence": "UNAVAILABLE"}])["status"] == "CONFLICTING_EVIDENCE"
assert mod.validate(game, [])["status"] == "NO_VERIFIED_EVIDENCE"
assert status(g={**game, "gameDate": "bad"}) == "INVALID_GAME_DATE"
assert status(g={**game, "opponent": "BAL"}) == "INVALID_GAME_CONTEXT"
for reports in ([report], [report, {**report, "evidence": "UNAVAILABLE"}]):
    result = mod.validate(game, reports)
    assert result["starterConfirmed"] is False
    assert result["depthChartFreshnessAffected"] is False
    assert result["productionEligible"] is False
print("PASS: game-specific official QB evidence fails closed on mismatch, stale, conflict and invalid context")
