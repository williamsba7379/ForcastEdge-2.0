#!/usr/bin/env python3
"""Isolated offline Wednesday delivery gate: research evidence only, never production-ready."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "tests"))
from test_nfl_week9_real_archive_replay import verify

def gate(season, week, snapshot_bytes, schedule, manifest, expected_commit, expected_sha256, expected_ids):
    """Fail closed on stale or unverified evidence; never promote research to production."""
    if (season, week) != (2026, 9):
        raise ValueError("Requested season/week not approved")
    if not expected_commit or not expected_sha256 or not expected_ids:
        raise ValueError("Explicit source commit, digest and game IDs required")
    if manifest.get("sourceCommit") != expected_commit or manifest.get("artifactSha256") != expected_sha256:
        raise ValueError("Requested source provenance differs from manifest")
    snapshot = json.loads(snapshot_bytes)
    ids = [str(g["id"]) for g in snapshot.get("games", [])]
    if len(ids) != len(set(ids)) or len(ids) != 15 or set(ids) != set(expected_ids):
        raise ValueError("Requested game IDs differ from archived card")
    verify(snapshot, schedule, manifest, snapshot_bytes)
    return {"status": "RESEARCH_ONLY_VALIDATED",
            "productionReady": False, "productionFreezeVerified": False,
            "season": season, "week": week, "gameCount": len(ids),
            "sourceRunId": manifest["sourceRunId"],
            "sourceCommit": manifest["sourceCommit"],
            "artifactSha256": manifest["artifactSha256"],
            "warning": "Archived isolated research evidence only; normal Wednesday production freeze unverified."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--expected-ids", required=True, help="Comma-separated exact archived ESPN game IDs")
    args = parser.parse_args()
    raw = (FIX / "nfl_week9_20261104_actual_snapshot.json").read_bytes()
    schedule = json.loads((FIX / "nfl_week9_20261104_espn_schedule.json").read_bytes())
    manifest = json.loads((FIX / "nfl_week9_20261104_artifact_manifest.json").read_bytes())
    try:
        result = gate(args.season, args.week, raw, schedule, manifest,
                      args.source_commit, args.artifact_sha256, args.expected_ids.split(","))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "NOT_READY", "productionReady": False, "reason": str(error)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
