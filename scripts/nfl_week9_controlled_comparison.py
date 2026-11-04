"""Controlled, read-only Week 9 comparison. All candidate data stays in memory."""
import json
import subprocess
from pathlib import Path
from scripts.nfl_week9_in_memory_repair import prepare
from scripts.nfl_week9_history_freshness_gate import EVIDENCE_COMMIT,EVIDENCE_PATH,FROZEN_PATH,HISTORY_PATH
from scripts.nfl_week9_history_sync_provenance import validate
from scripts import nfl_week9_integrity_research as research

def compare(history, candidate, frozen, qb_starters, qb_adjustments):
    if qb_starters.get("teams"):
        raise ValueError("QB starter evidence present: independent C-QB review required")
    if any(g.get("qbHomeEdgeAdjustment")!=0 or any(g.get("qbAdjustments",{}).get(side,{}).get("points",0) not in (0,None) for side in ("home","away")) for g in frozen["games"]):
        raise ValueError("Nonzero frozen QB adjustment: fail closed")
    if qb_adjustments.get("games"):
        raise ValueError("Verified adjustment feed not empty: cannot assume zero delta")
    # Reuse existing audited research arithmetic: A=.30, B=0, C exact round(margin,2).
    from scripts.model_c_engine import extract_history,team_form
    from scripts.nfl_four_model_head_to_head import stamp
    def c(g,h):
        old=extract_history(h,min(stamp(frozen["frozenAt"]),stamp(g["date"])),2026)
        home=team_form(old,g["home"]);away=team_form(old,g["away"])
        return g["home"] if round((home or 0)-(away or 0)+1.5,2)>=0 else g["away"]
    rows=[];baseline=[]
    for g in frozen["games"]:
        oldab=research.pick_ab(g,history,stamp(frozen["frozenAt"]))
        newab=research.pick_ab(g,candidate,stamp(frozen["frozenAt"]))
        oldc=c(g,history);newc=c(g,candidate)
        original={"A":oldab["A"],"B":oldab["B"],"C":oldc,"C-QB":oldc}
        updated={"A":newab["A"],"B":newab["B"],"C":newc,"C-QB":newc}
        if original!=g["picks"]: baseline.append(str(g["id"]))
        rows.append({"id":str(g["id"]),"matchup":g["away"]+" @ "+g["home"],"frozen":g["picks"],"conditional":updated,
                     "changedModels":[m for m in ("A","B","C","C-QB") if updated[m]!=g["picks"][m]],
                     "cQbIsIndependentExecution":False})
    if len(rows)!=15 or len({g["id"] for g in rows})!=15 or baseline:
        raise ValueError("Incomplete replay or frozen baseline mismatch: "+repr(baseline))
    return {"status":"RESEARCH_ONLY","promotionAuthorized":False,"gameCount":15,"baselineMismatches":baseline,
            "changedGameCount":sum(bool(g["changedModels"]) for g in rows),
            "qbAssumption":"ZERO_VERIFIED_ADJUSTMENTS_C_QB_SHADOW_NOT_INDEPENDENT",
            "rows":rows}

def main():
    root=Path(__file__).resolve().parents[1]
    report=json.loads(subprocess.check_output(["git","show",EVIDENCE_COMMIT+":"+EVIDENCE_PATH],text=True))
    commit_time=subprocess.check_output(["git","show","-s","--format=%cI",EVIDENCE_COMMIT],text=True).strip()
    blob=subprocess.check_output(["git","rev-parse",EVIDENCE_COMMIT+":"+EVIDENCE_PATH],text=True).strip()
    history=json.loads((root/HISTORY_PATH).read_text());frozen=json.loads((root/FROZEN_PATH).read_text())
    proposal,candidate=prepare(report,history,frozen,commit_time,blob)
    if proposal["status"]!="RESEARCH_READY" or proposal["addedCount"]!=14:
        raise ValueError("Candidate validation failed")
    qb=json.loads((root/"data/model-c-qb-starters.json").read_text())
    adjustment_path=root/"data/model-c-verified-adjustments.json"
    adj=json.loads(adjustment_path.read_text()) if adjustment_path.exists() else {"games":{}}
    result=compare(history,candidate,frozen,qb,adj)
    print(json.dumps({"proposalOriginalHash":proposal["originalHistorySha256"],
        "proposalCandidateHash":proposal["candidateSha256"],**result},indent=2))
    assert result["changedGameCount"]==2
if __name__=="__main__":main()
