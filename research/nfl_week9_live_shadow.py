#!/usr/bin/env python3
"""Live GitHub API replay of immutable November 4 research evidence; read-only."""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from nfl_week9_real_archive_replay import replay, RUN, ARTIFACT

REPO="williamsba7379/ForcastEdge-2.0"
SCHEDULE_COMMIT="e81ccee600c14dae6efcc57baf8217ac77180319"
SCHEDULE_PATH="tests/fixtures/nfl_week9_20261104_espn_schedule.json"

class SafeArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host=urllib.parse.urlparse(newurl).hostname or ''
        if not (newurl.startswith('https://') and (host.endswith('.actions.githubusercontent.com') or host.endswith('.blob.core.windows.net') or host.endswith('.githubusercontent.com'))):
            raise ValueError('UNTRUSTED_ARTIFACT_REDIRECT')
        # Signed artifact download URLs must not receive GitHub bearer credentials.
        return urllib.request.Request(newurl,headers={'User-Agent':'ForecastEdge-research-only-replay'})

def get(url):
    if not url.startswith("https://api.github.com/repos/"+REPO+"/"):
        raise ValueError("Unexpected API URL")
    token=os.environ.get("GITHUB_TOKEN")
    req=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json",
        "User-Agent":"ForecastEdge-research-only-replay",
        **({"Authorization":"Bearer "+token} if token else {})})
    try:
        with urllib.request.build_opener(SafeArtifactRedirect()).open(req,timeout=30) as response:
            if response.status!=200:raise ValueError("HTTP_FETCH_FAILED")
            return response.read()
    except urllib.error.HTTPError as exc:
        # Fail closed and report endpoint category without exposing tokens or redirect URLs.
        kind = "artifact_zip" if url.endswith("/zip") else ("run_metadata" if "/actions/runs/" in url else "contents_or_artifact_metadata")
        raise ValueError("GITHUB_HTTP_%s_%s" % (exc.code,kind)) from None

def main():
    prefix="https://api.github.com/repos/"+REPO
    run=json.loads(get(prefix+"/actions/runs/"+str(RUN)))
    artifacts=json.loads(get(prefix+"/actions/runs/"+str(RUN)+"/artifacts"))
    matches=[a for a in artifacts.get("artifacts",[]) if a.get("id")==ARTIFACT]
    if len(matches)!=1:raise ValueError("ARTIFACT_NOT_IN_SOURCE_RUN")
    archive=get(prefix+"/actions/artifacts/"+str(ARTIFACT)+"/zip")
    contents=json.loads(get(prefix+"/contents/"+SCHEDULE_PATH+"?ref="+SCHEDULE_COMMIT))
    schedule=json.loads(base64.b64decode(contents["content"]))
    result=replay(run,matches[0],archive,schedule)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="VERIFIED_RESEARCH_ONLY" and result["productionReady"] is False else 1

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print(json.dumps({"status":"NOT_READY","productionReady":False,"reason":str(exc)}))
        sys.exit(1)
