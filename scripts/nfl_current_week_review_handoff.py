#!/usr/bin/env python3
"""Review-only, fail-closed same-run archive; no publication or Git writes."""
import argparse
import copy
import datetime as dt
import hashlib
import io
import math
import json
import os
from pathlib import Path
import tarfile
import tempfile
from zoneinfo import ZoneInfo
from nfl_four_model_head_to_head import freeze, stamp
from nfl_four_model_totals_research import build_from_draft
from nfl_four_model_review_report import build, render
from nfl_market_totals_compare import compare

EASTERN = ZoneInfo("America/New_York")

def validate_projections(projections, card, draft, shadow, history, now):
    snapshot = stamp(projections["sourceComparisonFrozenAt"])
    generated = stamp(projections["generatedAt"])
    inputs_ready = max(stamp(source["generatedAt"]) for source in (draft, shadow))
    first_kickoff = min(stamp(game["date"]) for game in card["games"])
    if not inputs_ready <= snapshot <= generated <= now < first_kickoff:
        raise ValueError("Projection timestamps outside same-run pregame window")

    expected = build_from_draft({**card, "frozenAt": snapshot.isoformat()}, history, draft)
    expected["generatedAt"] = projections["generatedAt"]
    if projections != expected:
        raise ValueError("Projection report does not match same-run model inputs")
    for game in projections["games"]:
        for model in game["models"].values():
            if model["status"] == "INSUFFICIENT_HISTORY":
                continue
            if any(not math.isfinite(model[key]) or model[key] < 0
                   for key in ("projectedAway", "projectedHome", "projectedTotal")):
                raise ValueError("Invalid projected score")


def prepare(schedule, draft, shadow, history, now, projections=None):
    local = now.astimezone(EASTERN)
    if local.weekday() != 2 or local.hour < 11:
        raise ValueError("Wednesday review handoff cannot precede 11 AM Eastern")
    cutoff = local.replace(hour=11, minute=0, second=0, microsecond=0)
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
    if len(expected) != len(selected["games"]):
        raise ValueError("Duplicate schedule game IDs")
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
    card["status"] = "REVIEW_ONLY_UNPUBLISHED"
    card["warning"] = "Authentic-engine review; NOT an official Wednesday frozen card."
    if projections is not None:
        validate_projections(projections, card, draft, shadow, history, now)
    report = build(card, projections)
    if projections is not None:
        report["projectionGeneratedAt"] = projections["generatedAt"]
        report["notice"] = ("Review only. Score projections are experimental and uncalibrated. "
                            "Market lines, spread and total picks, and calibrated confidence are unavailable.")
    report["sourceStatus"] = "REVIEW_ONLY_UNPUBLISHED"
    report["sourceFrozenAt"] = None
    report["sourceGeneratedAt"] = now.isoformat()
    report["deliveryTiming"] = "AT_CUTOFF" if now == cutoff else "AFTER_11AM_NOT_ON_TIME"
    report["notice"] += " Actual generation time retained; historical eligibility and delivery integrity unverified."
    report["status"] = "REVIEW_ONLY_INCOMPLETE"
    report["deliveryVerification"] = "DELIVERY_UNVERIFIED"
    return report

def main():
    p = argparse.ArgumentParser()
    for name in ("schedule", "draft", "shadow", "history", "projections"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--market", type=Path)
    p.add_argument("--as-of")
    p.add_argument("--archive", type=Path)
    p.add_argument("--verify-complete", type=Path)
    args = p.parse_args()
    if args.verify_complete is not None:
        target = args.verify_complete
        marker = target.with_name(target.name + ".incomplete")
        receipt = target.with_name(target.name + ".sha256")
        if marker.exists() or not target.is_file() or not receipt.is_file():
            raise SystemExit("BLOCKED: archive completion evidence missing or incomplete")
        expected = receipt.read_text(encoding="ascii").strip()
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if len(expected) != 64 or expected != actual:
            raise SystemExit("BLOCKED: archive digest mismatch")
        print("LOCAL_ARCHIVE_COMPLETE_REVIEW_ONLY DELIVERY_UNVERIFIED sha256=" + actual)
        return
    if not all((args.schedule, args.draft, args.shadow, args.history, args.projections, args.as_of, args.archive)):
        raise SystemExit("BLOCKED: missing archive inputs")
    now = dt.datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise SystemExit("BLOCKED: as-of timestamp must include timezone")
    identity = {k: os.environ.get(k) for k in
                ("REVIEW_RUN_ID", "REVIEW_RUN_ATTEMPT", "REVIEW_RUN_SHA")}
    if not all(identity.values()) or not identity["REVIEW_RUN_ID"].isdigit() or not identity["REVIEW_RUN_ATTEMPT"].isdigit():
        raise SystemExit("BLOCKED: missing same-run GitHub identity")
    if not os.environ.get("GH_TOKEN") or not os.environ.get("GH_REPOSITORY"):
        raise SystemExit("BLOCKED: missing read-only GitHub run verification access")
    import urllib.request
    url = ("https://api.github.com/repos/" + os.environ["GH_REPOSITORY"] +
           "/actions/runs/" + identity["REVIEW_RUN_ID"])
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=20) as response:
        run = json.load(response)
    if (str(run.get("id")) != identity["REVIEW_RUN_ID"] or
        int(run.get("run_attempt", -1)) != int(identity["REVIEW_RUN_ATTEMPT"]) or
        run.get("head_sha") != identity["REVIEW_RUN_SHA"] or
        run.get("event") not in ("schedule", "workflow_dispatch")):
        raise SystemExit("BLOCKED: GitHub run identity mismatch")
    started = run.get("run_started_at")
    if not started:
        raise SystemExit("BLOCKED: GitHub run start unavailable")
    started_at = dt.datetime.fromisoformat(started.replace("Z", "+00:00"))
    if not started_at.tzinfo or not started_at <= now:
        raise SystemExit("BLOCKED: invalid run start timestamp")
    # GitHub run_started_at is run-level metadata, not an independently
    # attested attempt start. Retries remain DELIVERY_UNVERIFIED.
    if int(identity["REVIEW_RUN_ATTEMPT"]) != 1:
        raise SystemExit("BLOCKED: rerun attempt requires separate start proof")
    sources = {name: getattr(args, name).read_bytes()
               for name in ("schedule", "draft", "shadow", "history", "projections")}
    parsed = {name: json.loads(data) for name, data in sources.items()}
    report = prepare(parsed["schedule"], parsed["draft"], parsed["shadow"], parsed["history"], now,
                     parsed["projections"])
    # These are run-local files after checkout copies are removed; metadata alone is not independent proof.
    for name in ("draft", "shadow"):
        generated = dt.datetime.fromisoformat(parsed[name]["generatedAt"].replace("Z", "+00:00"))
        if not generated.tzinfo or not started_at <= generated <= now:
            raise SystemExit("BLOCKED: generated source outside verified run window")
        if generated.astimezone(EASTERN).date() != now.astimezone(EASTERN).date():
            raise SystemExit("BLOCKED: generated source not from current Wednesday")
    market_comparison = None
    if args.market is not None and args.market.exists():
        sources["market"] = args.market.read_bytes()
        market = json.loads(sources["market"])
        if any(stamp(quote["capturedAt"]) < started_at for quote in market["games"]):
            raise ValueError("Market capture precedes this run")
        market_comparison = compare(copy.deepcopy(parsed["projections"]), market)
    report_bytes = (json.dumps(report, indent=2) + "\n").encode()
    html_bytes = render(report).encode()
    members = {"inputs/" + name + ".json": data for name, data in sources.items()}
    members.update({"report.json": report_bytes, "report.html": html_bytes})
    if market_comparison is not None:
        members["market-comparison.json"] = (json.dumps(market_comparison, indent=2) + "\n").encode()
    manifest = {"status": "REVIEW_ONLY_UNPUBLISHED",
                "deliveryVerification": "DELIVERY_UNVERIFIED",
                "historicalEligibilityVerified": False,
                "artifactIntegrityIndependentlyVerified": False,
                "runIdentitySelfAttested": identity,
                "evaluatedAt": now.isoformat(),
                "githubRunStartedAt": started_at.isoformat(),
                "githubRunIdentityMatched": True,
                "runAttemptStartIndependentlyVerified": False,
                "members": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                            for name, data in sorted(members.items())}}
    members["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    target = args.archive
    incomplete = target.with_name(target.name + ".incomplete")
    receipt = target.with_name(target.name + ".sha256")
    target.parent.mkdir(parents=True, exist_ok=True)
    if incomplete.exists() or target.exists() or receipt.exists():
        raise SystemExit("BLOCKED: archive already exists or prior attempt incomplete")
    markerfd = os.open(incomplete, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(markerfd, "w") as marker:
        marker.write("INCOMPLETE REVIEW ARCHIVE; DELIVERY_UNVERIFIED\\n")
        marker.flush()
        os.fsync(marker.fileno())
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".review-", suffix=".tar.gz", dir=target.parent)
        with os.fdopen(fd, "wb") as out:
            with tarfile.open(fileobj=out, mode="w:gz") as archive:
                for name, data in sorted(members.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = 0o600
                    info.mtime = int(now.timestamp())
                    archive.addfile(info, io.BytesIO(data))
            out.flush()
            os.fsync(out.fileno())
        os.link(tmp, target)
        dirfd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if len(digest) != 64:
            raise SystemExit("BLOCKED: invalid local archive digest")
        fd_receipt = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd_receipt, "w") as out:
            out.write(digest + "\n")
            out.flush()
            os.fsync(out.fileno())
        # The incomplete marker is deliberately retained after any earlier
        # failure. A later verifier must reject that state.
        incomplete.unlink()
        dirfd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        print("REVIEW_ONLY_UNPUBLISHED DELIVERY_UNVERIFIED archive_sha256=" + digest)
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
