#!/usr/bin/env python3
"""Regression tests: historical starter loss is escalated, backups are not guessed."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model_c_qb_injury_audit_v2 import build
D=ROOT/"data"
draft=json.loads((D/"model-c-automated-draft.json").read_text())
shadow=json.loads((D/"model-c-qb-shadow.json").read_text())
history=json.loads((D/"model-c-historical-qb-games.json").read_text())
result=build(draft,shadow,history)
assert len(draft["games"])>0
assert result["reviewCount"]>=0
# Live injury reports change: never require a named player to remain OUT.
# Check any flagged established passer without fabricating an injury.
for alert in result["alerts"]:
    assert alert["priority"] in ("P1_ESTABLISHED_PRIMARY_PASSER_ABSENT", "P1_CURRENT_QB_CANDIDATE_ABSENT", "P2_ROLE_REVIEW_REQUIRED")
    assert alert["reportedUnavailable"]
    assert alert["pointsAdjustment"] == 0
assert all(a["status"]=="UNMODELED_HUMAN_REVIEW_REQUIRED" for a in result["alerts"])
assert all(a["pointsAdjustment"]==0 for a in result["alerts"])
assert len(shadow["games"])==len(draft["games"])
print("PASS: QB audit regression; no speculative score changes")

# Synthetic fixtures: exercise build() without writing repository data.
def synthetic_case(records):
    draft_fixture = {
        "season": 2026,
        "week": 11,
        "games": [{
            "id": "synthetic-qb-001",
            "date": "2026-11-22T18:00:00Z",
            "home": "Test Home",
            "away": "Test Away",
            "quarterbacks": {
                "home": {
                    "reportedQuarterbacks": [{"name": "Test QB", "status": "out"}],
                    "depthChartQB1Candidate": None,
                    "recentPrimaryPasser": None,
                },
                "away": {"reportedQuarterbacks": []},
            },
        }],
    }
    shadow_fixture = {
        "games": [{
            "id": "synthetic-qb-001",
            "qbAdjustments": {
                "home": {"status": "NO_ADJUSTMENT"},
                "away": {"status": "NO_ADJUSTMENT"},
            },
        }],
    }
    return build(draft_fixture, shadow_fixture, {"records": records})


null_passer = synthetic_case([{
    "team": "Test Home",
    "primaryPasser": None,
    "gameDate": "2026-11-15T18:00:00Z",
}])
assert null_passer["reviewCount"] == 1
assert null_passer["urgentCount"] == 0
assert null_passer["alerts"][0]["priority"] == "P2_ROLE_REVIEW_REQUIRED"
assert null_passer["alerts"][0]["priorPrimaryPasserGames"] == {"Test QB": 0}
assert null_passer["alerts"][0]["pointsAdjustment"] == 0

established = synthetic_case([
    {"team": "Test Home", "primaryPasser": "Test QB",
     "gameDate": "2026-11-01T18:00:00Z"},
    {"team": "Test Home", "primaryPasser": "Test QB",
     "gameDate": "2026-11-08T18:00:00Z"},
])
assert established["alerts"][0]["priority"] == "P1_ESTABLISHED_PRIMARY_PASSER_ABSENT"
assert established["alerts"][0]["priorPrimaryPasserGames"] == {"Test QB": 2}
assert established["alerts"][0]["pointsAdjustment"] == 0
print("PASS: synthetic nullable QB and established passer")
