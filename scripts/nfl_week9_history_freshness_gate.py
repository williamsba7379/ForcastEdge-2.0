#!/usr/bin/env python3
"""Read-only fail-closed Week 9 history freshness gate. Never changes predictions."""
import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

EVIDENCE_COMMIT = "29ec2e1516a4e625717d2fc929c351ae8a07b65a"
EVIDENCE_PATH = "data/four-model-head-to-head/2026-week-8-results-report.json"
FROZEN_PATH = "data/four-model-head-to-head/2026-week-9-refresh-20261104T171826Z.json"
HISTORY_PATH = "data/nfl-historical-results.json"

def from_commit(commit=EVIDENCE_COMMIT, path=EVIDENCE_PATH):
    return json.loads(subprocess.check_output(["git", "show", f"{commit}:{path}"], text=True))

def check(report, history, frozen):
    errors = []
    if (report.get("season"), report.get("week"), report.get("status")) != (2026, 8, "COMPLETE"):
        errors.append("SOURCE_REPORT_NOT_COMPLETE")
    if (frozen.get("season"), frozen.get("week")) != (2026, 9):
        errors.append("FROZEN_WEEK_MISMATCH")
    freeze = dt.datetime.fromisoformat(frozen["frozenAt"].replace("Z", "+00:00"))
    if freeze.tzinfo is None:
        errors.append("FREEZE_TIME_NO_TIMEZONE")
    results = report.get("results", [])
    if report.get("gamesCompleted") != 14 or len(results) != 14:
        errors.append("EXPECTED_14_VERIFIED_FINALS")
    ids = [str(g["gameId"]) for g in results]
    if len(set(ids)) != 14:
        errors.append("DUPLICATE_VERIFIED_GAME_ID")
    eligible = []
    for g in results:
        kickoff = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        if kickoff >= freeze:
            errors.append("RESULT_NOT_PRE_FREEZE_" + str(g["gameId"]))
        else:
            eligible.append(g)
        if not g.get("scoreSource", "").startswith("https://site.api.espn.com/"):
            errors.append("UNVERIFIED_SCORE_SOURCE_" + str(g["gameId"]))
    rows = [g for g in history.get("games", []) if g.get("season") == 2026]
    by_id = {}
    for row in rows:
        by_id.setdefault(str(row.get("id")), []).append(row)
    missing, mismatched = [], []
    for g in eligible:
        id_ = str(g["gameId"])
        matches = by_id.get(id_, [])
        if not matches:
            missing.append(id_)
        elif len(matches) != 1 or matches[0].get("homeScore") != g.get("homeScore") or matches[0].get("awayScore") != g.get("awayScore") or matches[0].get("winner") != g.get("winner"):
            mismatched.append(id_)
    if missing: errors.append("MISSING_ELIGIBLE_FINALS")
    if mismatched: errors.append("MISMATCHED_ELIGIBLE_FINALS")
    # A score's kickoff time is not its observed-final time. Proven input availability
    # requires immutable historical evidence, not today's network response.
    return {"status": "BLOCKED" if errors else "HISTORY_IDS_AND_SCORES_MATCH",
            "promotionAuthorized": False,
            "evidenceCommit": EVIDENCE_COMMIT,
            "freezeAt": frozen["frozenAt"],
            "eligibleFinalCount": len(eligible),
            "historyMatchedCount": len(eligible)-len(missing)-len(mismatched),
            "missingIds": sorted(missing), "mismatchedIds": sorted(mismatched),
            "errors": errors,
            "historicalHttpRetrievalTimestamps": "NOT_PRESERVED",
            "historicalFinalizationTimestamps": "NOT_PRESERVED",
            "historicalInputAvailabilityProven": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-blocked", action="store_true")
    args = ap.parse_args()
    result = check(from_commit(), json.loads(Path(HISTORY_PATH).read_text()),
                   json.loads(Path(FROZEN_PATH).read_text()))
    print(json.dumps(result, indent=2))
    if args.expect_blocked:
        if result["status"] != "BLOCKED" or len(result["missingIds"]) != 14:
            raise SystemExit("Expected exact 14-game missing-history failure; investigate")
    elif result["status"] == "BLOCKED":
        raise SystemExit("Historical input freshness gate blocked")
if __name__ == "__main__":
    main()
