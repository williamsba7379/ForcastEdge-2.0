"""Read-only GitHub evidence collector for draft-only Model C/C-QB delivery review.

Uses GitHub REST with read-only token. Never dispatches workflows or writes files.
A successful workflow alone is not proof that the output commit was pushed.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "williamsba7379/ForcastEdge-2.0"
WORKFLOW = "model-c-draft.yml"
PATHS = {"C": "data/model-c-automated-draft.json", "C-QB": "data/model-c-qb-shadow.json"}
SHA = re.compile(r"^[0-9a-f]{40}$")
API = "https://api.github.com/repos/" + REPO

class EvidenceError(Exception):
    pass

def get(path, *, token=None):
    """GET only, constrained to this repository's GitHub API."""
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise EvidenceError("UNSAFE_PATH")
    request = urllib.request.Request(API + path, headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"ForecastEdge-read-only-evidence",
        **({"Authorization":"Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError) as exc:
        raise EvidenceError("GITHUB_READ_FAILED") from exc

def _iso(s):
    try:
        t = dt.datetime.fromisoformat(s.replace("Z","+00:00"))
        if t.tzinfo is None: raise ValueError("naive")
        return t.astimezone(dt.timezone.utc)
    except (AttributeError, ValueError, TypeError) as exc:
        raise EvidenceError("INVALID_TIMESTAMP") from exc

def verify(run, jobs, commits, files):
    """All data must be independently fetched from GitHub; fail closed on missing linkage."""
    if run.get("event") != "schedule" or run.get("name") != "Generate Model C review-only draft":
        raise EvidenceError("WRONG_WORKFLOW")
    checkout = run.get("head_sha")
    if not isinstance(checkout,str) or not SHA.fullmatch(checkout):
        raise EvidenceError("MISSING_CHECKOUT_SHA")
    if len(jobs) != 1 or jobs[0].get("run_id") != run.get("id"):
        raise EvidenceError("JOB_RUN_MISMATCH")
    job = jobs[0]
    steps = {s.get("name"):s.get("conclusion") for s in job.get("steps",[])}
    required = ("Generate independent Model C review draft","Generate separate Model C-QB experimental shadow",
                "Validate generated Model C review draft","Commit draft only")
    if run.get("conclusion") != "success" or job.get("conclusion") != "success":
        raise EvidenceError("FAILED_RUN")
    if any(steps.get(s) != "success" for s in required):
        raise EvidenceError("SKIPPED_REQUIRED_STEP")
    # No-op git commit is allowed in production workflow; require independently fetched output commit.
    if len(commits) != 1:
        raise EvidenceError("MISSING_OUTPUT_COMMIT")
    commit = commits[0]
    output = commit.get("sha")
    if not isinstance(output,str) or not SHA.fullmatch(output) or output == checkout:
        raise EvidenceError("UNCOMMITTED_OUTPUT")
    if checkout not in commit.get("parents",[]):
        raise EvidenceError("COMMIT_NOT_DESCENDED_FROM_CHECKOUT")
    if commit.get("message") != "Update Model C review-only draft":
        raise EvidenceError("UNEXPECTED_OUTPUT_COMMIT")
    start = _iso(run.get("run_started_at"))
    finished = _iso(run.get("updated_at"))
    committed = _iso(commit.get("committed_at"))
    if not start <= committed <= finished:
        raise EvidenceError("COMMIT_OUTSIDE_RUN")
    if not commit.get("on_main"):
        raise EvidenceError("OUTPUT_COMMIT_NOT_ON_MAIN")
    result = {}
    for model,path in PATHS.items():
        item=files.get(model)
        if not isinstance(item,dict) or item.get("path") != path or item.get("ref") != output:
            raise EvidenceError("MISSING_SAVED_ARTIFACT:"+model)
        raw=item.get("raw")
        if not isinstance(raw,str):
            raise EvidenceError("MISSING_CONTENT:"+model)
        digest=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if digest != item.get("sha256"):
            raise EvidenceError("TAMPERED_ARTIFACT:"+model)
        try: data=json.loads(raw)
        except ValueError as exc: raise EvidenceError("INVALID_JSON:"+model) from exc
        if data.get("season") != 2026 or data.get("week") != 10:
            raise EvidenceError("STALE_ARTIFACT:"+model)
        if path not in commit.get("changed_paths",[]):
            raise EvidenceError("ARTIFACT_NOT_IN_OUTPUT_COMMIT:"+model)
        generated=_iso(data.get("generatedAt"))
        if not start <= generated <= committed:
            raise EvidenceError("GENERATED_OUTSIDE_RUN:"+model)
        result[model]={"path":path,"sha256":digest,"commitSha":output,"generatedAt":data["generatedAt"]}
    return {"status":"PASS","runId":run["id"],"checkoutSha":checkout,"outputCommitSha":output,"artifacts":result}

def collect(run_id, token=None):
    """Read GitHub metadata, commit and content; never trust local workspace artifacts."""
    if not isinstance(run_id,int) or run_id <= 0: raise EvidenceError("INVALID_RUN_ID")
    token = token or os.environ.get("GITHUB_TOKEN")
    run=get("/actions/runs/"+str(run_id),token=token)
    if run.get("id") != run_id or run.get("path","").split("@")[0] != ".github/workflows/"+WORKFLOW:
        raise EvidenceError("RUN_ID_OR_WORKFLOW_MISMATCH")
    jobs=get("/actions/runs/"+str(run_id)+"/jobs?per_page=100",token=token).get("jobs",[])
    # A workflow run may contain multiple jobs; this production workflow requires exactly one.
    commits=get("/commits?path=data/model-c-automated-draft.json&per_page=30",token=token)
    candidates=[]
    for item in commits:
        detail=get("/commits/"+item["sha"],token=token)
        if detail.get("commit",{}).get("message") != "Update Model C review-only draft":continue
        sha=detail.get("sha")
        if not isinstance(sha,str) or not SHA.fullmatch(sha):continue
        paths=[f.get("filename") for f in detail.get("files",[])]
        if not all(p in paths for p in PATHS.values()):continue
        candidates.append({"sha":sha,"parents":[p["sha"] for p in detail.get("parents",[])],
                           "message":detail["commit"]["message"],
                           "committed_at":detail["commit"]["committer"]["date"],
                           "changed_paths":paths,"on_main":False})
    # We cannot prove the push/branch ancestry using commit-list proximity alone.
    # Fail closed until independent main ancestry and run-to-commit evidence are supplied.
    raise EvidenceError("UNVERIFIED_RUN_TO_OUTPUT_COMMIT_LINKAGE")

if __name__=="__main__":
    try:
        rid=int(sys.argv[1])
        print(json.dumps(collect(rid),indent=2))
    except (EvidenceError,IndexError,ValueError) as exc:
        print(json.dumps({"status":"FAIL","reason":str(exc)}))
        sys.exit(1)
