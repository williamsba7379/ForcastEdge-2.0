"""Read-only A/B archive adapter; never regenerate or overwrite frozen picks."""
import datetime as dt

def parse_time(value):
    stamp=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp missing offset")
    return stamp.astimezone(dt.timezone.utc)

def inspect_ab_archive(archive, expected_ids=None):
    issues=[]
    if archive.get("status")!="frozen_pre_kickoff":
        issues.append("NOT_FROZEN_PREKICKOFF")
    try:
        frozen=parse_time(archive["frozenAt"])
    except (KeyError,TypeError,ValueError):
        return ["MISSING_OR_INVALID_FREEZE_TIME"]
    games=archive.get("games")
    if not isinstance(games,list) or not games:
        return ["MISSING_AB_GAMES"]
    ids=[str(g.get("id","")) for g in games]
    if len(ids)!=len(set(ids)):
        issues.append("DUPLICATE_AB_GAME_IDS")
    if expected_ids is not None and set(ids)!=set(map(str,expected_ids)):
        issues.append("AB_SCHEDULE_MISMATCH")
    for game in games:
        ident=str(game.get("id","UNKNOWN"))
        try:
            if frozen>=parse_time(game["date"]):
                issues.append(ident+" AB_FROZEN_AFTER_KICKOFF")
        except (KeyError,TypeError,ValueError):
            issues.append(ident+" INVALID_KICKOFF")
        for model,field in (("A","baseline30Pick"),("B","experimental0Pick")):
            if game.get(field) not in (game.get("home"),game.get("away")):
                issues.append(ident+" "+model+" MISSING_OR_INVALID_PICK")
        if game.get("method")!="model":
            issues.append(ident+" UNVERIFIED_MODEL_METHOD")
    return issues

def adapt(archive):
    """Use only source selections; preserve both A and B even if equal."""
    return [{"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],
             "picks":{"A":g["baseline30Pick"],"B":g["experimental0Pick"]},
             "source_status":"EXPERIMENTAL_NO_BET","frozenAt":archive["frozenAt"]}
            for g in archive["games"]]
