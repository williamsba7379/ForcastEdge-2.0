"""Research-only in-memory historical data proposal. No filesystem writes."""
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from scripts.nfl_week9_history_sync_provenance import validate
from scripts.nfl_week9_history_freshness_gate import EVIDENCE_COMMIT,EVIDENCE_PATH,FROZEN_PATH,HISTORY_PATH

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def prepare(report, history, frozen, commit_timestamp, blob_id):
    from scripts.nfl_week9_history_sync_provenance import timestamp
    errors=[]
    if not blob_id or len(blob_id)!=40: errors.append("MISSING_SOURCE_BLOB_ID")
    if timestamp(commit_timestamp)>timestamp(frozen["frozenAt"]): errors.append("SOURCE_COMMIT_AFTER_FREEZE")
    initial=validate(report,history,frozen)
    errors.extend(e for e in initial["failures"] if e!="MISSING_HISTORY_GAMES")
    candidate=deepcopy(history)
    ids={(g["season"],str(g["id"])) for g in candidate["games"]}
    added=[]
    if not errors:
        for g in report["results"]:
            key=(2026,str(g["gameId"]))
            if key in ids: continue
            candidate["games"].append({"season":2026,"week":8,"id":str(g["gameId"]),**{k:g[k] for k in ("date","home","away","homeScore","awayScore","winner")}})
            added.append(str(g["gameId"]))
    final=validate(report,candidate,frozen)
    errors.extend(final["failures"])
    return {"status":"RESEARCH_READY" if not errors else "BLOCKED","promotionAuthorized":False,
        "sourceCommit":EVIDENCE_COMMIT,"sourceBlobId":blob_id,
        "originalHistorySha256":digest(history),"candidateSha256":digest(candidate),
        "rollback":"discard candidate; original input unchanged",
        "addedIds":sorted(added),"addedCount":len(added),
        "validation":final,"errors":sorted(set(errors))},candidate

def main():
    report=json.loads(subprocess.check_output(["git","show",EVIDENCE_COMMIT+":"+EVIDENCE_PATH],text=True))
    timestamp=subprocess.check_output(["git","show","-s","--format=%cI",EVIDENCE_COMMIT],text=True).strip()
    blob=subprocess.check_output(["git","rev-parse",EVIDENCE_COMMIT+":"+EVIDENCE_PATH],text=True).strip()
    history=json.loads(Path(HISTORY_PATH).read_text())
    frozen=json.loads(Path(FROZEN_PATH).read_text())
    result,_=prepare(report,history,frozen,timestamp,blob)
    print(json.dumps(result,indent=2))
    assert result["status"]=="RESEARCH_READY" and result["addedCount"]==14
    assert result["validation"]["status"]=="CONSISTENT_NOT_PROMOTABLE"
if __name__=="__main__": main()
