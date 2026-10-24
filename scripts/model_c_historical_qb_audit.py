#!/usr/bin/env python3
"""Offline integrity audit of game-level QB research data; no prediction changes."""
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def validate(qb, history):
    historical={str(g["id"]):g for g in history.get("games",[])}
    records=qb.get("records",[])
    grouped={}
    errors=[]
    unmatched=[]
    for r in records:
        gid=str(r.get("gameId",""))
        team=r.get("team")
        grouped.setdefault(gid,[]).append(r)
        g=historical.get(gid)
        if g is None:
            unmatched.append(gid)
        elif team not in (g.get("home"),g.get("away")) or r.get("gameDate")!=g.get("date"):
            errors.append({"gameId":gid,"issue":"team_or_date_mismatch"})
        if r.get("starterConfirmed") is not False or r.get("identityType")!="FINAL_GAME_PRIMARY_PASSER_NOT_STARTER":
            errors.append({"gameId":gid,"issue":"unverified_starter_claim"})
        passers=r.get("passers",[])
        if not passers or any(not isinstance(p.get("attempts"),int) or p["attempts"]<0 for p in passers):
            errors.append({"gameId":gid,"issue":"invalid_passing_line"})
        leaders=[p["player"] for p in passers if p.get("attempts")==max((x.get("attempts",-1) for x in passers),default=-1)]
        expected=leaders[0] if len(leaders)==1 else None
        if r.get("primaryPasser")!=expected:
            errors.append({"gameId":gid,"issue":"primary_passer_mismatch"})
    for gid,items in grouped.items():
        if len(items)!=2 or len({x.get("team") for x in items})!=2:
            errors.append({"gameId":gid,"issue":"missing_or_duplicate_team_record"})
    if len(grouped)!=qb.get("gameCount") or len(records)!=qb.get("teamGameRecords"):
        errors.append({"issue":"declared_counts_mismatch"})
    # Missing game IDs may reflect a stale historical results snapshot, not invalid QB data.
    return {"status":"PASS_WITH_UNMATCHED_HISTORY" if not errors and unmatched else ("PASS" if not errors else "FAIL"),
            "teamGameRecords":len(records),"uniqueGames":len(grouped),
            "crossReferencedGames":len(grouped)-len(set(unmatched)),
            "unmatchedHistoryGames":len(set(unmatched)),
            "unmatchedGameIds":sorted(set(unmatched)),
            "errors":errors,
            "starterVerification":"NOT_PROVIDED",
            "note":"Unmatched IDs require refresh of historical scores before cross-source validation; primary passers are not confirmed starters."}

def main():
    qb=json.loads((DATA/"model-c-historical-qb-games.json").read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    out=validate(qb,history)
    (DATA/"model-c-historical-qb-audit.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k not in ("unmatchedGameIds","errors")},indent=2))
    if out["errors"]:raise SystemExit(1)

if __name__=="__main__":main()
