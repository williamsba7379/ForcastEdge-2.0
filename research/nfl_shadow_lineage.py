"""Fail-closed draft-only full-model lineage assessment; never certifies production."""
import datetime as dt
from zoneinfo import ZoneInfo
from nfl_real_artifact_shadow import parse_time

def assess_lineage(manifest):
    reasons=[]
    try:
        cutoff=parse_time(manifest["cutoff"])
        local=cutoff.astimezone(ZoneInfo("America/New_York"))
        if local.weekday()!=2 or (local.hour,local.minute)!=(11,0):
            reasons.append("INVALID_WEDNESDAY_CUTOFF")
    except (KeyError,TypeError,ValueError):
        return {"status":"NOT_READY","productionReady":False,"reasons":["CUTOFF_MISSING"]}
    for name in ("A","B","C","C-QB"):
        item=manifest.get("models",{}).get(name,{})
        if not all(item.get(k) for k in ("run_id","artifact_id","commit","sha256","source_verified","input_times")):
            reasons.append("LINEAGE_MISSING_"+name)
            continue
        if item.get("source_verified") is not True:
            reasons.append("SOURCE_UNVERIFIED_"+name)
        try:
            times=[parse_time(v) for v in item["input_times"]]
            if not times or any(v>cutoff for v in times):
                reasons.append("INPUT_AFTER_CUTOFF_"+name)
        except (ValueError,TypeError,KeyError):
            reasons.append("INPUT_TIMESTAMP_INVALID_"+name)
    if not manifest.get("independent_nfl_schedule_authenticated"):
        reasons.append("NFL_SCHEDULE_UNVERIFIED")
    if not manifest.get("independent_espn_schedule_authenticated"):
        reasons.append("ESPN_SCHEDULE_UNVERIFIED")
    return {"status":"NOT_READY" if reasons else "RESEARCH_LINEAGE_CONTRACT_ONLY",
            "productionReady":False,"reasons":reasons}
