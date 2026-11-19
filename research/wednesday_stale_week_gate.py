"""Research-only, no I/O. Authority is an external prerequisite, not authenticated here."""
import hashlib, json
from datetime import datetime, timezone
class GateError(ValueError):
    def __init__(self, code): self.code=code; super().__init__(code)
def timestamp(value):
    try:
        x=datetime.fromisoformat(value.replace("Z","+00:00"))
        if x.tzinfo is None: raise ValueError("naive")
        return x.astimezone(timezone.utc)
    except (ValueError,AttributeError,TypeError,OverflowError): raise GateError("INVALID_TIMESTAMP")
def schedule_digest(schedule):
    return hashlib.sha256(json.dumps(schedule,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def check(target,schedule,draft,shadow,authority=None):
    """Fail closed; does not freeze, grade, write, or publish."""
    if target.get("operation")!="WEDNESDAY_FREEZE": raise GateError("INVALID_OPERATION")
    if not isinstance(authority,dict) or authority.get("status")!="VERIFIED_EXTERNAL": raise GateError("MISSING_SCHEDULE_AUTHORITY")
    if any(authority.get(k)!=target.get(k) for k in ("season","week","cutoff_at")): raise GateError("UNTRUSTED_TARGET_WEEK")
    if target.get("season")!=schedule.get("season"): raise GateError("TARGET_SCHEDULE_MISMATCH")
    if authority.get("schedule_sha256")!=schedule_digest(schedule): raise GateError("SCHEDULE_PROVENANCE_MISMATCH")
    cutoff=timestamp(target.get("cutoff_at"))
    if timestamp(schedule.get("updatedAt"))>cutoff or timestamp(authority.get("verified_at"))>cutoff: raise GateError("POST_CUTOFF_SCHEDULE")
    weeks=schedule.get("weeks",[])
    selected=[w for w in weeks if w.get("week")==target.get("week")]
    if len(selected)!=1: raise GateError("DUPLICATE_OR_MISSING_WEEK")
    nums=[w.get("week") for w in weeks]
    if len(nums)!=len(set(nums)): raise GateError("DUPLICATE_SCHEDULE_WEEK")
    games=selected[0].get("games",[])
    ids=[str(g.get("id")) for g in games]
    if not ids or any(x in ("None","") for x in ids) or len(ids)!=len(set(ids)): raise GateError("INVALID_SCHEDULE_IDS")
    for g in games:
        if timestamp(g.get("date"))<=cutoff: raise GateError("GAME_NOT_FUTURE_AT_CUTOFF")
        if not g.get("home") or not g.get("away") or g["home"]==g["away"]: raise GateError("INVALID_GAME_METADATA")
    for source in (draft,shadow):
        if (source.get("season"),source.get("week"))!=(target.get("season"),target.get("week")): raise GateError("STALE_WEEK_INPUT")
        if timestamp(source.get("generatedAt"))>cutoff: raise GateError("POST_CUTOFF_INPUT")
        sg=source.get("games",[]); sid=[str(g.get("id")) for g in sg]
        if len(sid)!=len(ids) or len(set(sid))!=len(sid) or set(sid)!=set(ids): raise GateError("GAME_ID_MISMATCH")
        by_id={str(g["id"]):g for g in sg}
        for g in games:
            e=by_id[str(g["id"])]
            if any(e.get(k)!=g.get(k) for k in ("home","away")) or timestamp(e.get("date"))!=timestamp(g.get("date")): raise GateError("GAME_METADATA_MISMATCH")
    if shadow.get("status")!="EXPERIMENTAL_SHADOW_ONLY": raise GateError("INVALID_SHADOW_STATUS")
    return tuple(ids)
