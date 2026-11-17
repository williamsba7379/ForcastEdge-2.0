#!/usr/bin/env python3
"""Read-only GitHub Actions artifact provenance verifier. No publishing or production authority."""
import datetime as dt
import hashlib
import io
import json
import os
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

class NotReady(ValueError):
    pass

def parse_time(value):
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None: raise ValueError("naive")
        return t.astimezone(dt.timezone.utc)
    except (AttributeError, ValueError, TypeError) as exc:
        raise NotReady("INVALID_TIMESTAMP") from exc

def github_get(path, token=None, api="https://api.github.com"):
    if not path.startswith("/repos/") or ".." in path or "//" in path:
        raise NotReady("INVALID_API_PATH")
    req = urllib.request.Request(api + path, headers={"Accept":"application/vnd.github+json",
        "User-Agent":"ForecastEdge-read-only-shadow",
        **({"Authorization":"Bearer " + token} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200: raise NotReady("GITHUB_FETCH_FAILED")
        return response.read()

def validate_schedule(nfl, espn, season, week):
    if not nfl or not espn: raise NotReady("SCHEDULE_MISSING")
    if any(s.get("season") != season or s.get("week") != week for s in (nfl,espn)):
        raise NotReady("STALE_SCHEDULE")
    def index(s):
        rows=s.get("games")
        if not isinstance(rows,list) or not rows: raise NotReady("EMPTY_SCHEDULE")
        ids=[str(g["id"]) for g in rows]
        if len(ids)!=len(set(ids)): raise NotReady("DUPLICATE_GAME_ID")
        return {str(g["id"]):(g["home"],g["away"],parse_time(g["date"])) for g in rows}
    a,b=index(nfl),index(espn)
    if a!=b: raise NotReady("SCHEDULE_DISAGREEMENT")
    return a

def validate_artifact(fetch, repo, spec, cutoff):
    """Fetch run and artifact metadata independently; validate ZIP member bytes."""
    required=("run_id","artifact_id","commit","workflow_path","member","sha256")
    if any(not spec.get(k) for k in required): raise NotReady("ARTIFACT_FIELDS_MISSING")
    if not all(isinstance(spec[k],int) and spec[k]>0 for k in ("run_id","artifact_id")):
        raise NotReady("INVALID_ARTIFACT_ID")
    if not isinstance(spec["commit"],str) or len(spec["commit"])!=40:
        raise NotReady("INVALID_COMMIT")
    if not isinstance(spec["sha256"],str) or len(spec["sha256"])!=64:
        raise NotReady("INVALID_DIGEST")
    prefix="/repos/"+repo
    run=json.loads(fetch(prefix+"/actions/runs/"+str(spec["run_id"])))
    if (run.get("id")!=spec["run_id"] or run.get("head_sha")!=spec["commit"]
        or run.get("status")!="completed" or run.get("conclusion")!="success"
        or run.get("path")!=spec["workflow_path"]):
        raise NotReady("RUN_IDENTITY_MISMATCH")
    artifact=json.loads(fetch(prefix+"/actions/artifacts/"+str(spec["artifact_id"])))
    if (artifact.get("id")!=spec["artifact_id"] or artifact.get("expired") is not False
        or artifact.get("workflow_run",{}).get("id")!=spec["run_id"]):
        raise NotReady("ARTIFACT_IDENTITY_MISMATCH")
    data=fetch(prefix+"/actions/artifacts/"+str(spec["artifact_id"])+"/zip")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members=archive.namelist()
            if len(members)!=len(set(members)) or spec["member"] not in members:
                raise NotReady("ARTIFACT_MEMBER_MISSING")
            info=archive.getinfo(spec["member"])
            if info.is_dir() or info.file_size>10_000_000 or len(data)>25_000_000:
                raise NotReady("ARTIFACT_SIZE_UNSAFE")
            raw=archive.read(info)
    except (zipfile.BadZipFile,RuntimeError,KeyError) as exc:
        raise NotReady("ARTIFACT_ARCHIVE_INVALID") from exc
    if hashlib.sha256(raw).hexdigest()!=spec["sha256"]:
        raise NotReady("ARTIFACT_DIGEST_MISMATCH")
    payload=json.loads(raw)
    if parse_time(payload["generatedAt"])>cutoff:
        raise NotReady("POST_CUTOFF_ARTIFACT")
    return payload

def shadow(request, fetch):
    """Fail closed; never return productionReady=true, even for authenticated inputs."""
    try:
        season,week=request["season"],request["week"]
        cutoff=parse_time(request["cutoff"])
        local=cutoff.astimezone(ZoneInfo("America/New_York"))
        if local.weekday()!=2 or (local.hour,local.minute)!=(11,0):
            raise NotReady("INVALID_WEDNESDAY_CUTOFF")
        if request.get("nfl_source_id")==request.get("espn_source_id") or not all(
            request.get(k) for k in ("nfl_source_id","espn_source_id","nfl_schedule","espn_schedule")):
            raise NotReady("INDEPENDENT_SCHEDULE_UNVERIFIED")
        games=validate_schedule(request["nfl_schedule"],request["espn_schedule"],season,week)
        repo=request["repo"]
        if repo!="williamsba7379/ForcastEdge-2.0": raise NotReady("REPOSITORY_NOT_APPROVED")
        result={}
        for model in ("model_c","model_c_qb"):
            spec=request["artifacts"][model]
            payload=validate_artifact(fetch,repo,spec,cutoff)
            if (payload.get("season"),payload.get("week"))!=(season,week):
                raise NotReady("STALE_MODEL")
            rows=payload.get("games",[])
            if len(rows)!=len(games) or {str(g["id"]) for g in rows}!=set(games):
                raise NotReady("MODEL_GAME_COVERAGE_MISMATCH")
            for row in rows:
                if (row["home"],row["away"],parse_time(row["date"]))!=games[str(row["id"])]:
                    raise NotReady("MODEL_SCHEDULE_MISMATCH")
            result[model]={"run_id":spec["run_id"],"artifact_id":spec["artifact_id"],
                           "sha256":spec["sha256"]}
        return {"status":"VERIFIED_RESEARCH_ONLY","productionReady":False,
                "season":season,"week":week,"games":len(games),"artifacts":result}
    except (NotReady,KeyError,TypeError,ValueError,IndexError,zipfile.BadZipFile) as exc:
        return {"status":"NOT_READY","productionReady":False,"reason":str(exc)}
