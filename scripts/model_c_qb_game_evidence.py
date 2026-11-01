#!/usr/bin/env python3
"""Offline, read-only game-specific QB announcement evidence gate. Never confirms a starter."""
from datetime import date

def validate(game, reports, max_age_days=7):
    """Return informational evidence only; any ambiguity fails closed."""
    base = {"starterConfirmed": False, "depthChartFreshnessAffected": False,
            "productionEligible": False}
    required = ("gameId", "team", "opponent", "quarterback", "gameDate")
    if not isinstance(game, dict) or any(not isinstance(game.get(k), str) or not game[k].strip() for k in required):
        return {**base, "status": "INVALID_GAME_CONTEXT"}
    if game["team"] == game["opponent"]:
        return {**base, "status": "INVALID_GAME_CONTEXT"}
    try:
        kickoff = date.fromisoformat(game["gameDate"])
    except ValueError:
        return {**base, "status": "INVALID_GAME_DATE"}
    if not isinstance(reports, list) or not reports:
        return {**base, "status": "NO_VERIFIED_EVIDENCE"}
    accepted = []
    for report in reports:
        if not isinstance(report, dict):
            return {**base, "status": "INVALID_REPORT"}
        if any(report.get(k) != game[k] for k in ("gameId", "team", "opponent", "quarterback")):
            return {**base, "status": "MISMATCHED_GAME_OR_QB"}
        if report.get("sourceType") != "OFFICIAL_TEAM" or not report.get("sourceUrl", "").startswith("https://"):
            return {**base, "status": "UNVERIFIED_SOURCE"}
        try:
            published = date.fromisoformat(report["publicationDate"])
        except (KeyError, ValueError, TypeError):
            return {**base, "status": "INVALID_PUBLICATION_DATE"}
        if published > kickoff or (kickoff - published).days > max_age_days:
            return {**base, "status": "STALE_OR_FUTURE_EVIDENCE"}
        if report.get("evidence") not in ("AVAILABLE", "UNAVAILABLE", "NO_DIRECT_ANNOUNCEMENT"):
            return {**base, "status": "UNVERIFIED_EVIDENCE"}
        accepted.append(report["evidence"])
    if "AVAILABLE" in accepted and "UNAVAILABLE" in accepted:
        return {**base, "status": "CONFLICTING_EVIDENCE"}
    if len(set(accepted) - {"NO_DIRECT_ANNOUNCEMENT"}) == 0:
        return {**base, "status": "NO_DIRECT_QB_ANNOUNCEMENT"}
    return {**base, "status": "READ_ONLY_MATCHED_EVIDENCE",
            "evidence": "UNAVAILABLE" if "UNAVAILABLE" in accepted else "AVAILABLE"}
