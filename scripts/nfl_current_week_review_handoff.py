#!/usr/bin/env python3
"""Prepare a nonpublishing, review-only current-week four-model artifact.
Only calls the existing authentic A/B/C/C-QB freeze engine with supplied
pre-existing input files. Never runs model generators or invents missing picks.
No output is written unless explicitly given an output path.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from nfl_four_model_head_to_head import freeze
from nfl_four_model_review_report import build, render

EASTERN = ZoneInfo("America/New_York")


def prepare(schedule, draft, shadow, history, now):
    local = now.astimezone(EASTERN)
    if local.weekday() != 2:
        raise ValueError("Wednesday review handoff only")
    cutoff = local.replace(hour=11, minute=0, second=0, microsecond=0)
    if local.hour != 11:
        raise ValueError("Outside Wednesday 11 AM Eastern review window")
    weeks = schedule.get("weeks", [])
    candidates = [w for w in weeks if w.get("games") and
                  min(dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
                      for g in w["games"]) > now]
    if not candidates:
        raise ValueError("No complete future week in schedule")
    selected = min(candidates, key=lambda w: min(
        dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00")) for g in w["games"]))
    season, week = schedule["season"], selected["week"]
    if any(x.get("season") != season or x.get("week") != week for x in (draft, shadow)):
        raise ValueError("Model C and C-QB source week mismatch")
    if shadow.get("status") != "EXPERIMENTAL_SHADOW_ONLY":
        raise ValueError("C-QB shadow status not review-only")
    expected = {str(g["id"]): g for g in selected["games"]}
    for label, obj in (("C", draft), ("C-QB", shadow)):
        generated = dt.datetime.fromisoformat(obj["generatedAt"].replace("Z", "+00:00"))
        if generated.tzinfo is None or not dt.timedelta(0) <= now-generated <= dt.timedelta(hours=8):
            raise ValueError(label + " source stale, future-dated or unverified")
        actual = {str(g["id"]): g for g in obj["games"]}
        if len(actual) != len(obj["games"]) or set(actual) != set(expected):
            raise ValueError(label + " game coverage mismatch")
        for gid, game in actual.items():
            source = expected[gid]
            if any(game.get(k) != source.get(k) for k in ("date", "home", "away")):
                raise ValueError(label + " matchup/kickoff mismatch " + gid)
    card = freeze(draft, shadow, history, now)
    if len(card["games"]) != len(expected):
        raise ValueError("Four-model coverage incomplete")
    # Never represent the comparison as a production freeze or official card.
    card["status"] = "REVIEW_ONLY_UNPUBLISHED"
    card["warning"] = "Synthetic-free authentic-engine review; NOT an official Wednesday frozen card."
    report = build(card)
    report["sourceStatus"] = "REVIEW_ONLY_UNPUBLISHED"
    report["sourceFrozenAt"] = None
    report["sourceGeneratedAt"] = now.isoformat()
    report["deliveryTiming"] = "AT_CUTOFF" if now == cutoff else "AFTER_11AM_NOT_ON_TIME"
    report["notice"] += " Actual generation time retained; after-11 AM output is not an on-time freeze."
    report["status"] = "REVIEW_ONLY_INCOMPLETE"
    return report


def main():
    p = argparse.ArgumentParser()
    for name in ("schedule", "draft", "shadow", "history"):
        p.add_argument("--"+name, required=True, type=Path)
    p.add_argument("--as-of", required=True, help="Actual offset-aware ISO 8601 evaluation timestamp")
    p.add_argument("--json", required=True, type=Path)
    p.add_argument("--html", required=True, type=Path)
    args = p.parse_args()
    now = dt.datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise SystemExit("BLOCKED: as-of timestamp must include timezone")
    read = lambda path: json.loads(path.read_text())
    report = prepare(read(args.schedule), read(args.draft),
                     read(args.shadow), read(args.history), now)
    for path in (args.json, args.html):
        if path.exists():
            raise SystemExit("BLOCKED: refusing to overwrite an existing artifact")
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.html.write_text(render(report), encoding="utf-8")
    print("REVIEW ONLY: local artifacts prepared; nothing published")


if __name__ == "__main__":
    main()
