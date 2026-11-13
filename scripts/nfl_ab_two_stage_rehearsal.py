"""Two-stage research-only Wednesday evidence; no predictions, freeze or production writes."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_official_html_capture import fetch_official_html, verify_reviewed_normalization
from scripts.nfl_ab_wednesday_schedule_collector import collect_wednesday_schedule
from scripts.nfl_ab_schedule_provenance import verify_schedule_evidence
from scripts.nfl_ab_wednesday_evidence_rehearsal import compare_captures

def validate_bundle(bundle, cutoff=None):
    if not isinstance(bundle,dict) or bundle.get("kind")!="RESEARCH_ONLY_INDEPENDENT_CAPTURE":
        raise ValueError("INVALID_CAPTURE_BUNDLE")
    nfl,espn=bundle["nfl"],bundle["espn"]
    if nfl.get("kind")!="RAW_NFL_HTML_CAPTURE" or espn.get("kind")!="ISOLATED_WEDNESDAY_SCHEDULE_EVIDENCE":
        raise ValueError("INVALID_CAPTURE_SOURCE")
    if bundle["season"]!=espn["season"] or bundle["week"]!=espn["week"]:
        raise ValueError("CAPTURE_WEEK_MISMATCH")
    if cutoff is not None and parse_time(cutoff)!=parse_time(bundle["cutoff"]):
        raise ValueError("CAPTURE_CUTOFF_MISMATCH")
    deadline=parse_time(bundle["cutoff"])
    if deadline.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).weekday()!=2 or deadline.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).strftime("%H:%M")!="11:00":
        raise ValueError("INVALID_WEDNESDAY_CUTOFF")
    for proof in (nfl,espn["scheduleEvidence"]):
        t=parse_time(proof["retrievedAt"])
        if not deadline-dt.timedelta(hours=24)<=t<=deadline:
            raise ValueError("CAPTURE_OUTSIDE_24H_WINDOW")
    # Empty review is rejected after validating NFL source bytes, host and hash.
    try:
        verify_reviewed_normalization(nfl,[],bundle["cutoff"])
    except ValueError as exc:
        if str(exc)!="MISSING_REVIEWED_GAMES":
            raise
    verify_schedule_evidence(espn["scheduleEvidence"],bundle["cutoff"],espn["expectedSchedule"])
    return True

def capture(season,week,cutoff,nfl_fetch=fetch_official_html,espn_fetch=collect_wednesday_schedule):
    # Refuse invalid deadline before any network access.
    from zoneinfo import ZoneInfo
    deadline=parse_time(cutoff)
    local=deadline.astimezone(ZoneInfo("America/New_York"))
    if local.weekday()!=2 or (local.hour,local.minute)!=(11,0):
        raise ValueError("INVALID_WEDNESDAY_CUTOFF")
    nfl=nfl_fetch(season,week,cutoff)
    espn=espn_fetch(season,week,cutoff)
    bundle={"kind":"RESEARCH_ONLY_INDEPENDENT_CAPTURE","schemaVersion":1,
            "season":season,"week":week,"cutoff":deadline.isoformat(),
            "nfl":nfl,"espn":espn,"publishable":False,"officialFrozen":False,
            "productionReady":False}
    validate_bundle(bundle)
    return bundle

def review(bundle,reviewed_games):
    validate_bundle(bundle)
    result=compare_captures(bundle["nfl"],reviewed_games,bundle["espn"],bundle["cutoff"])
    if result["season"]!=bundle["season"] or result["week"]!=bundle["week"]:
        raise ValueError("REVIEW_WEEK_MISMATCH")
    result["captureBundleSha256"]=hashlib.sha256(json.dumps(bundle,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    result["reviewedAfterCapture"]=True
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=("capture","review"))
    p.add_argument("--season",type=int)
    p.add_argument("--week",type=int)
    p.add_argument("--cutoff")
    p.add_argument("--bundle",type=Path)
    p.add_argument("--reviewed-games",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        raise ValueError("REFUSE_OVERWRITE_EVIDENCE")
    if a.stage=="capture":
        if a.season is None or a.week is None or not a.cutoff:
            p.error("capture requires season, week and cutoff")
        obj=capture(a.season,a.week,a.cutoff)
    else:
        if not a.bundle or not a.reviewed_games:
            p.error("review requires immutable capture bundle and reviewed manifest")
        obj=review(json.loads(a.bundle.read_text()),json.loads(a.reviewed_games.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(obj,indent=2)+"\n")
    print("RESEARCH ONLY",a.stage,"complete; never frozen")

if __name__=="__main__":
    main()
