"""Research-only readiness gates for NFL A/B/C/C-QB delivery. No file writes."""
import datetime as dt
from zoneinfo import ZoneInfo

MODELS=("A","B","C","C-QB")
def parse(value):
    t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("NAIVE_TIMESTAMP")
    return t.astimezone(dt.timezone.utc)

def audit(schedule,model_c,model_c_qb,card,now,*,official_qb_evidence=False,source_artifacts=None):
    reasons=[]
    try:
        now=parse(now)
        games=schedule["games"]
        ids={str(g["id"]) for g in games}
        if len(ids)!=len(games) or not games:reasons.append("INVALID_SCHEDULE")
        week=(schedule["season"],schedule["week"])
        if any((item.get("season"),item.get("week"))!=week for item in (model_c,model_c_qb,card)):
            reasons.append("STALE_WEEK")
        if any({str(g["id"]) for g in item["games"]}!=ids or len(item["games"])!=len(games)
               for item in (model_c,model_c_qb,card)):
            reasons.append("INCOMPLETE_OR_MISMATCHED_GAMES")
        if any(set(g.get("picks",{}))!=set(MODELS) for g in card["games"]):
            reasons.append("FOUR_MODEL_PICKS_MISSING")
        local=now.astimezone(ZoneInfo("America/New_York"))
        if local.weekday()!=2 or (local.hour,local.minute)!=(11,0):
            reasons.append("NOT_WEDNESDAY_11_ET")
        for name,item in (("C",model_c),("C-QB",model_c_qb)):
            if parse(item["generatedAt"])>now:reasons.append("POST_CUTOFF_"+name)
        if not official_qb_evidence:reasons.append("QB_VERIFICATION_MISSING")
        for name in MODELS:
            evidence=(source_artifacts or {}).get(name,{})
            if not (evidence.get("artifact_id") and evidence.get("sha256") and evidence.get("run_id")
                    and evidence.get("commit") and evidence.get("verified") is True):
                reasons.append("IMMUTABLE_SOURCE_MISSING_"+name)
        if parse(card["frozenAt"])>now:reasons.append("POST_CUTOFF_CARD")
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        reasons.append("MALFORMED_OR_MISSING_INPUT")
    return {"status":"NOT_READY" if reasons else "RESEARCH_CONTRACT_PASS",
            "productionReady":False,"reasons":sorted(set(reasons))}
