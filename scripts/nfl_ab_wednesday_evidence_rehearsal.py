"""Research-only NFL/ESPN evidence rehearsal. Never publishes or freezes picks."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from scripts.nfl_ab_archive_adapter import parse_time
from scripts.nfl_ab_official_html_capture import fetch_official_html, verify_reviewed_normalization
from scripts.nfl_ab_wednesday_schedule_collector import collect_wednesday_schedule

def normalize_name(value):
    return " ".join(value.strip().casefold().split())

def game_key(row):
    return (parse_time(row["date"]).astimezone(dt.timezone.utc).isoformat(),
            normalize_name(row["home"]), normalize_name(row["away"]))

def compare_captures(nfl_capture, reviewed_games, espn_capture, cutoff):
    """Verify independent raw source evidence and create auditable ESPN-ID mapping."""
    nfl=verify_reviewed_normalization(nfl_capture, reviewed_games, cutoff)
    if nfl_capture["sourceUrl"].startswith("https://site.api.espn.com"):
        raise ValueError("INDEPENDENT_NFL_SOURCE_REQUIRED")
    from scripts.nfl_ab_schedule_provenance import verify_schedule_evidence
    espn_games=espn_capture["expectedSchedule"]
    verify_schedule_evidence(espn_capture["scheduleEvidence"], cutoff, espn_games)
    for proof in (nfl_capture, espn_capture["scheduleEvidence"]):
        observed=parse_time(proof["retrievedAt"])
        deadline=parse_time(cutoff)
        if not deadline-dt.timedelta(hours=24)<=observed<=deadline:
            raise ValueError("CAPTURE_OUTSIDE_24H_WINDOW")
    nfl_rows=nfl["games"]
    nfl_keys=[game_key(g) for g in nfl_rows]
    espn_keys=[game_key(g) for g in espn_games]
    if len(set(nfl_keys))!=len(nfl_keys) or len(set(espn_keys))!=len(espn_keys):
        raise ValueError("DUPLICATE_MATCHUP")
    if set(nfl_keys)!=set(espn_keys):
        raise ValueError("INDEPENDENT_SCHEDULE_MISMATCH")
    mapping={game_key(g):str(g["id"]) for g in espn_games}
    return {"status":"SCHEDULE_EVIDENCE_PASS","productionReady":False,
            "officialFrozen":False,"publishable":False,
            "season":espn_capture["season"],"week":espn_capture["week"],
            "gameCount":len(nfl_keys),
            "nflSourceSha256":nfl["responseSha256"],
            "espnSourceSha256":espn_capture["scheduleEvidence"]["responseSha256"],
            "nflCapturedAt":nfl["retrievedAt"],
            "espnCapturedAt":espn_capture["scheduleEvidence"]["retrievedAt"],
            "verifiedEspnIds":[mapping[k] for k in nfl_keys],
            "normalizedGames":[{"id":mapping[game_key(g)],"date":g["date"],
                                "home":g["home"],"away":g["away"]} for g in nfl_rows]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--season",type=int,required=True)
    parser.add_argument("--week",type=int,required=True)
    parser.add_argument("--cutoff",required=True)
    parser.add_argument("--reviewed-games",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError("REFUSE_OVERWRITE_EVIDENCE")
    # No output is published until both independent responses validate.
    nfl=fetch_official_html(args.season,args.week,args.cutoff)
    espn=collect_wednesday_schedule(args.season,args.week,args.cutoff)
    reviewed=json.loads(args.reviewed_games.read_text())
    result=compare_captures(nfl,reviewed,espn,args.cutoff)
    result["sourceEvidence"]={"nfl":nfl,"espn":espn["scheduleEvidence"]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("RESEARCH ONLY:",result["status"],result["gameCount"])

if __name__=="__main__":
    main()
