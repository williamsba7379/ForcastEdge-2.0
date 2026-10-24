#!/usr/bin/env python3
"""Validate that QB shadow output is paired with and isolated from Model C."""
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def validate(draft,shadow):
    errors=[]
    if (draft.get("season"),draft.get("week"))!=(shadow.get("season"),shadow.get("week")):
        errors.append("season/week mismatch")
    if shadow.get("status")!="EXPERIMENTAL_SHADOW_ONLY":
        errors.append("shadow status missing")
    original={str(g["id"]):g for g in draft.get("games",[])}
    candidates=shadow.get("games",[])
    if len(candidates)!=len(original) or len({str(g["id"]) for g in candidates})!=len(candidates):
        errors.append("game count or IDs mismatch")
    applied=0
    for row in candidates:
        game=original.get(str(row["id"]))
        if game is None:
            errors.append("unknown game "+str(row["id"]))
            continue
        for field in ("date","home","away"):
            if row.get(field)!=game.get(field):errors.append(str(row["id"])+": "+field+" mismatch")
        if row.get("originalPick")!=game.get("pick") or row.get("originalHomeEdgePoints")!=game.get("homeEdgePoints"):
            errors.append(str(row["id"])+": original prediction changed")
        sides=row.get("qbAdjustments",{})
        if not all(side in sides for side in ("home","away")):
            errors.append(str(row["id"])+": missing QB sides")
            continue
        for side in ("home","away"):
            a=sides[side]
            if a.get("status")=="EXPERIMENTAL_APPLIED":applied+=1
            elif a.get("points")!=0:errors.append(str(row["id"])+": unverified nonzero adjustment")
            if type(a.get("points")) not in (int,float) or abs(a["points"])>3:
                errors.append(str(row["id"])+": adjustment outside cap")
        delta=round(sides["home"]["points"]-sides["away"]["points"],2)
        edge=round(game["homeEdgePoints"]+delta,2)
        if row.get("qbHomeEdgeAdjustment")!=delta or row.get("experimentalHomeEdgePoints")!=edge:
            errors.append(str(row["id"])+": adjusted edge arithmetic mismatch")
        if row.get("experimentalPick")!=(game["home"] if edge>=0 else game["away"]):
            errors.append(str(row["id"])+": adjusted pick mismatch")
        if row.get("rating")!="NO BET":errors.append(str(row["id"])+": unsafe betting rating")
    if shadow.get("eligibleAdjustments")!=applied:
        errors.append("applied adjustment count mismatch")
    return {"status":"PASS" if not errors else "FAIL","season":shadow.get("season"),
            "week":shadow.get("week"),"gamesCompared":len(candidates),
            "eligibleQBAdjustments":applied,"errors":errors,
            "note":"PASS checks structural consistency, not prediction accuracy or starter authenticity."}

def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    shadow=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    report=validate(draft,shadow)
    (DATA/"model-c-qb-shadow-validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if report["errors"]:raise SystemExit(1)

if __name__=="__main__":main()
