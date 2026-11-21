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


def rehearse_handoff(schedule, model_c, model_c_qb, history, cutoff):
    """Build an in-memory research card from explicitly supplied model outputs."""
    from model_c_engine import choose_week
    from nfl_four_model_head_to_head import freeze

    cutoff = parse(cutoff)
    local = cutoff.astimezone(ZoneInfo("America/New_York"))
    if local.weekday() != 2 or local.time() != dt.time(11):
        raise ValueError("Expected Wednesday 11 AM Eastern cutoff")

    week = choose_week(schedule, cutoff)
    expected_week = (schedule["season"], week["week"])

    def game_identity(games):
        return [
            (str(game["id"]), game["home"], game["away"], parse(game["date"]))
            for game in games
        ]

    slate = game_identity(week["games"])
    if len({row[0] for row in slate}) != len(slate) or any(row[3] <= cutoff for row in slate):
        raise ValueError("Invalid upcoming schedule")

    previous = local.replace(hour=0).astimezone(dt.timezone.utc)
    for name, output in (("C", model_c), ("C-QB", model_c_qb)):
        if (output["season"], output["week"]) != expected_week:
            raise ValueError(f"{name} week mismatch")
        generated = parse(output["generatedAt"])
        if not previous <= generated <= cutoff:
            raise ValueError(f"{name} timestamp outside Wednesday handoff window")
        if sorted(game_identity(output["games"])) != sorted(slate):
            raise ValueError(f"{name} schedule mismatch")
        previous = generated

    card = freeze(model_c, model_c_qb, history, cutoff)
    card["status"] = "RESEARCH_REHEARSAL_ONLY"
    return card
