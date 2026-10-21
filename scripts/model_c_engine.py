#!/usr/bin/env python3
"""ForecastEdge Model C: independent, reproducible, review-only weekly engine.
Never edits frozen predictions, Model C Week 7 pilot, or pool selections.
QB/injury inputs must be verified and manually supplied; missing data are explicit.
"""
import datetime as dt
import json
import math
import pathlib
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ET = zoneinfo.ZoneInfo("America/New_York")

def load(name):
    return json.loads((DATA / name).read_text())

def choose_week(schedule, now):
    utc = now.astimezone(dt.timezone.utc)
    future = []
    for week in schedule["weeks"]:
        dates = [dt.datetime.fromisoformat(g["date"].replace("Z","+00:00")) for g in week["games"]]
        if dates and max(dates) > utc:
            future.append((min(dates),week))
    if not future:
        raise RuntimeError("No upcoming week in schedule. Refusing to publish.")
    upcoming = [pair for pair in future if pair[0] > utc]
    return min(upcoming or future,key=lambda pair:pair[0])[1]

def extract_history(raw, before, season):
    """Use completed games strictly before each target kickoff; no future leakage."""
    games = raw.get("games",[]) if isinstance(raw,dict) else raw
    output = []
    for game in games:
        try:
            if int(game.get("season",-1)) != season: continue
            date = dt.datetime.fromisoformat(game["date"].replace("Z","+00:00"))
            if date >= before: continue
            away = game["away"];home=game["home"]
            sa = float(game.get("scoreAway",game.get("awayScore")))
            sh = float(game.get("scoreHome",game.get("homeScore")))
            output.append((date,away,home,sa,sh))
        except (KeyError,TypeError,ValueError,AttributeError):
            continue
    return sorted(output)

def team_form(history, team):
    diffs=[]
    for _,away,home,sa,sh in history:
        if team==home: diffs.append(sh-sa)
        elif team==away: diffs.append(sa-sh)
    if not diffs:return None
    season=sum(diffs)/len(diffs)
    recent=sum(diffs[-3:])/min(3,len(diffs))
    return .7*season+.3*recent

def qb_performance_comparison(team, declaration, stats, now, kickoff):
    """Compare sourced final-game passing stats using AYA, without untested points."""
    out={"status":"INSUFFICIENT_DATA","starter":None,"replacement":None,"differenceAYA":None,
         "estimatedPoints":None,"note":"No verified starter/replacement performance comparison available."}
    starter=declaration.get("starter")
    backup=declaration.get("expectedReplacement")
    if not starter or not backup or starter==backup or not declaration.get("source") or declaration.get("status")!="CONFIRMED_STARTER":
        return out
    def stamp(value):
        try:
            value=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
            return value if value.tzinfo else None
        except (ValueError,TypeError,AttributeError):
            return None
    declared=stamp(declaration.get("asOf"))
    if declared is None or declared>now or declared>=kickoff:
        return out
    records=stats.get("teams",{}).get(team,{})
    values=[]
    for name in (starter,backup):
        record=records.get(name,{})
        observed=stamp(record.get("asOf"))
        fields=("passYards","passTD","interceptions","passAttempts")
        if not record.get("source") or observed is None or observed>now or observed>=kickoff:
            return out
        if any(type(record.get(k)) not in (int,float) or record[k]<0 for k in fields):
            return out
        attempts=record["passAttempts"]
        if attempts<=0:return out
        anya=(record["passYards"]+20*record["passTD"]-45*record["interceptions"])/attempts
        values.append((round(anya,2),record["passAttempts"],record["source"]))
    return {"status":"DESCRIPTIVE_ONLY","starter":starter,"replacement":backup,
        "starterAYA":values[0][0],"replacementAYA":values[1][0],
        "differenceAYA":round(values[0][0]-values[1][0],2),
        "sampleAttempts":{"starter":values[0][1],"replacement":values[1][1]},
        "sources":{"declaration":declaration["source"],"starter":values[0][2],"replacement":values[1][2]},
        "estimatedPoints":None,
        "note":"Adjusted yards/pass attempt (AYA), excludes sacks, rushing, opponent adjustment and calibrated points. Review required."}

def main():
    now=dt.datetime.now(ET)
    schedule=load("nfl-schedule.json")
    selected=choose_week(schedule,now)
    year=schedule["season"];week=selected["week"]
    try:history_raw=load("nfl-historical-results.json")
    except FileNotFoundError:history_raw=[]
    # Optional verified, pregame adjustment file: explicit team points, source and as-of.
    path=DATA / "model-c-verified-adjustments.json"
    adjustments=json.loads(path.read_text()) if path.exists() else {"games":{}}
    try: injury_snapshot=load("model-c-injury-snapshot.json")
    except FileNotFoundError: injury_snapshot={}
    injury_teams={t.get("team"):t for t in injury_snapshot.get("teams",[])}
    try: qb_declarations=load("model-c-qb-starters.json").get("teams",{})
    except FileNotFoundError: qb_declarations={}
    try: qb_stats=load("model-c-qb-performance.json")
    except FileNotFoundError: qb_stats={}
    try: qb_candidates=load("model-c-qb-candidates.json").get("teams",{})
    except FileNotFoundError: qb_candidates={}
    games=[]
    for g in selected["games"]:
        kickoff=dt.datetime.fromisoformat(g["date"].replace("Z","+00:00"))
        history=extract_history(history_raw,min(kickoff,now.astimezone(dt.timezone.utc)),year)
        away=team_form(history,g["away"]);home=team_form(history,g["home"])
        missing=away is None or home is None
        base=(home or 0)-(away or 0)+1.5
        verified=adjustments.get("games",{}).get(str(g["id"]),{})
        delta=0.0;used=[]
        for side,sign in (("home",1),("away",-1)):
            item=verified.get(side)
            if item and isinstance(item.get("points"),(int,float)) and item.get("source") and item.get("asOf"):
                if abs(item["points"])>12:raise ValueError("Adjustment exceeds safety cap")
                delta+=sign*item["points"]
                used.append({"team":g[side],"points":item["points"],"source":item["source"],"asOf":item["asOf"],"reason":item.get("reason","")})
        margin=round(base+delta,2)
        pick=g["home"] if margin>=0 else g["away"]
        injury_reports={side:injury_teams.get(g[side],{}).get("players",[]) for side in ("away","home")}
        quarterbacks={}
        for side in ("away","home"):
            team=g[side]
            declaration=qb_declarations.get(team,{})
            starter=declaration.get("starter")
            source=declaration.get("source")
            asof=declaration.get("asOf")
            valid=False
            if (declaration.get("status")=="CONFIRMED_STARTER"
                and declaration.get("sourceType") in ("TEAM_ANNOUNCEMENT","OFFICIAL_INACTIVES","OFFICIAL_GAME_REPORT")
                and str(declaration.get("gameId",""))==str(g["id"])
                and isinstance(source,str) and source.startswith("https://")
                and starter and asof):
                try:
                    stamp=dt.datetime.fromisoformat(asof.replace("Z","+00:00"))
                    valid=stamp.tzinfo is not None and stamp<=now.astimezone(dt.timezone.utc) and stamp<kickoff and (kickoff-stamp).total_seconds()<=604800
                except (ValueError,TypeError,AttributeError):
                    pass
            qbs=[p for p in injury_reports[side] if p.get("position","").upper()=="QB"]
            matched=next((p for p in qbs if p.get("name","").casefold()==str(starter).casefold()),None) if valid else None
            candidate=qb_candidates.get(team,{})
            quarterbacks[side]={"recentPrimaryPasser":candidate.get("candidate"),"recentPrimaryPasserGameDate":candidate.get("lastGameDate"),"recentPrimaryPasserSource":candidate.get("source"),"recentPrimaryPasserIsConfirmedStarter":False,"starter":starter if valid else None,
              "starterSource":source if valid else None,"starterAsOf":asof if valid else None,
              "verification":"OFFICIAL_GAME_SPECIFIC" if valid else "UNCONFIRMED",
              "injuryStatus":matched.get("status") if matched else "NOT REPORTED",
              "availability":"REVIEW REQUIRED" if matched else "UNKNOWN",
              "reportedQuarterbacks":qbs}
        qb_comparisons={side:qb_performance_comparison(g[side],(qb_declarations.get(g[side],{}) if quarterbacks[side]["verification"]=="OFFICIAL_GAME_SPECIFIC" else {}),qb_stats,now.astimezone(dt.timezone.utc),kickoff) for side in ("away","home")}
        games.append({"qbPerformanceComparisons":qb_comparisons,"quarterbacks":quarterbacks,"injuryReports":injury_reports,"injurySource":injury_snapshot.get("source"),
          "injuryRetrievedAt":injury_snapshot.get("retrievedAt"),"id":g["id"],"date":g["date"],"away":g["away"],"home":g["home"],"pick":pick,
          "homeEdgePoints":margin,"baseHomeEdgePoints":round(base,2),"verifiedAdjustmentHomeEdgePoints":round(delta,2),
          "confidence":"UNVALIDATED","rating":"NO BET","verifiedAdjustments":used,
          "dataWarnings":(["Missing team history; used neutral rating"] if missing else [])+
          (["No verified quarterback/injury adjustment; NOT an injury-aware pick"] if not used else []),
          "reason":"70% season + 30% last-three scoring differential, +1.5 home points; explicit verified adjustments only. Not calibrated."})
    if len(games)<10:raise RuntimeError("Too few scheduled games; refusing to publish.")
    out={"title":"Model C — Automated Review Draft","season":year,"week":week,"generatedAt":now.isoformat(),
         "status":"AUTOMATED_REVIEW_ONLY","reviewRequired":True,
         "method":"Point-differential baseline plus optional documented quarterback/injury adjustments; no unverified automatic injury claims.",
         "disclaimer":"Not the frozen Week 7 analyst pilot; not official pool picks; not betting recommendations. No calibrated win probabilities.",
         "games":games}
    output=DATA / "model-c-automated-draft.json"
    output.write_text(json.dumps(out,indent=2)+"\n")
    print(f"Generated Model C Week {week} review-only draft: {len(games)} games; {sum(bool(g['verifiedAdjustments']) for g in games)} verified-adjusted.")

if __name__=="__main__":main()
