"""Read-only replay of pinned real November 4 Week 9 research artifact."""
import hashlib
import io
import json
import zipfile
from nfl_real_artifact_shadow import parse_time, NotReady

RUN=41876281307
ARTIFACT=13346712960
COMMIT="9a0c8af1b786c32fb4df6421553be32fc623f660"
DIGEST="6b74de78645bd17f910f5f0e5b51679b324c4f452aafb8e199f1ba3a4c32c250"
MEMBER="data/four-model-head-to-head/2026-week-9-refresh-20261104T171826Z.json"
WORKFLOW=".github/workflows/nfl-week9-freeze-isolated.yml"

def replay(run, artifact, zip_bytes, schedule):
    try:
        if (run.get("id"),run.get("head_sha"),run.get("path"),run.get("status"),run.get("conclusion")) != (
            RUN,COMMIT,WORKFLOW,"completed","success"):
            raise NotReady("RUN_PROVENANCE_MISMATCH")
        if (artifact.get("id")!=ARTIFACT or artifact.get("expired") is not False
            or artifact.get("workflow_run",{}).get("id")!=RUN
            or artifact.get("workflow_run",{}).get("head_sha")!=COMMIT):
            raise NotReady("ARTIFACT_PROVENANCE_MISMATCH")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            if MEMBER not in z.namelist():raise NotReady("SNAPSHOT_MISSING")
            raw=z.read(MEMBER)
            readiness=json.loads(z.read("week9-readiness.json"))
        if hashlib.sha256(raw).hexdigest()!=DIGEST:
            raise NotReady("PAYLOAD_DIGEST_MISMATCH")
        snapshot=json.loads(raw)
        if (readiness.get("mode")!="READ_ONLY_NO_FREEZE" or snapshot.get("status")!="FRESH_PREKICKOFF_SNAPSHOT"
            or (snapshot.get("season"),snapshot.get("week"))!=(2026,9)):
            raise NotReady("RESEARCH_STATUS_MISMATCH")
        actual=snapshot["games"]
        expected=schedule["games"]
        if (schedule.get("season"),schedule.get("week"))!=(2026,9) or len(actual)!=15 or len(expected)!=15:
            raise NotReady("INCOMPLETE_WEEK9")
        idx={str(g["id"]):g for g in expected}
        if len(idx)!=15 or len({str(g["id"]) for g in actual})!=15 or {str(g["id"]) for g in actual}!=set(idx):
            raise NotReady("GAME_ID_MISMATCH")
        for g in actual:
            e=idx[str(g["id"])]
            if (g["home"],g["away"],parse_time(g["date"]))!=(e["home"],e["away"],parse_time(e["date"])):
                raise NotReady("SCHEDULE_MISMATCH")
        snapshot_at=parse_time(snapshot["frozenAt"])
        first=min(parse_time(g["date"]) for g in expected)
        if snapshot_at>=first:raise NotReady("POST_KICKOFF_SNAPSHOT")
        if parse_time(snapshot["modelCGeneratedAt"])>snapshot_at or parse_time(snapshot["modelCQBGeneratedAt"])>snapshot_at:
            raise NotReady("INPUT_GENERATED_AFTER_SNAPSHOT")
        return {"status":"VERIFIED_RESEARCH_ONLY","productionReady":False,"productionFreezeVerified":False,
                "sourceRunId":RUN,"artifactId":ARTIFACT,"games":15,"sha256":DIGEST,
                "snapshotAt":snapshot["frozenAt"],
                "warning":"After 11 AM ET cutoff; historical research snapshot only"}
    except (NotReady,KeyError,ValueError,TypeError,zipfile.BadZipFile) as exc:
        return {"status":"NOT_READY","productionReady":False,"productionFreezeVerified":False,"reason":str(exc)}
