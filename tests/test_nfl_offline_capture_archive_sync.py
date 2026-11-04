import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.nfl_offline_capture_archive_sync import run

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def event(i):
    return {"id":str(i),"date":"2026-11-15T18:00:00Z","status":{"type":{"completed":True,"name":"STATUS_FINAL"}},"competitions":[{"competitors":[{"homeAway":"home","score":"21","team":{"displayName":"Home"+str(i)}},{"homeAway":"away","score":"10","team":{"displayName":"Away"+str(i)}}]}]}
def git(root,*args,env=None):
    return subprocess.check_output(["git","-C",str(root),*args],env=env).decode().strip()
class PipelineTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        git(self.root,"init","-q");git(self.root,"config","user.name","Fixture");git(self.root,"config","user.email","fixture@example.invalid")
        self.events={"events":[event(101),event(102)]}
        self.history={"games":[{"season":2025,"week":1,"id":"old"}]}
        self.retrieved="2026-11-16T02:00:00Z";self.archived="2026-11-16T03:00:00Z";self.cutoff="2026-11-18T17:00:00Z"
        self.ids=["101","102"];self.commit=None
    def archive(self):
        (self.root/"capture.json").write_bytes(json.dumps(self.events).encode())
        git(self.root,"add","capture.json")
        env=os.environ.copy();env["GIT_AUTHOR_DATE"]="2026-11-16T02:30:00+00:00";env["GIT_COMMITTER_DATE"]="2026-11-16T02:30:00+00:00"
        git(self.root,"commit","-qm","immutable capture",env=env)
        self.commit=git(self.root,"rev-parse","HEAD")
    def execute(self,raw=None,commit=None,source=URL,ids=None):
        if self.commit is None:self.archive()
        if raw is None:raw=json.dumps(self.events).encode()
        return run(self.root,self.history,raw,source,self.retrieved,self.archived,self.cutoff,2026,10,self.ids if ids is None else ids,self.commit if commit is None else commit,"capture.json")
    def blocked(self,**kw):
        before=copy.deepcopy(self.history)
        result,candidate=self.execute(**kw)
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertEqual(candidate,before)
        self.assertEqual(self.history,before)
    def test_end_to_end_success(self):
        before=copy.deepcopy(self.history)
        r,c=self.execute()
        self.assertEqual(r["status"],"RESEARCH_READY",r)
        self.assertEqual(r["addedCount"],2)
        self.assertEqual(len(c["games"]),3)
        self.assertEqual(self.history,before)
        self.assertFalse(r["promotionAuthorized"])
    def test_idempotent(self):
        r,c=self.execute()
        self.history=c
        r2,c2=self.execute()
        self.assertEqual(r2["addedCount"],0)
        self.assertEqual(r["candidateSha256"],r2["candidateSha256"])
    def test_modified_raw_bytes(self):
        self.archive()
        changed=copy.deepcopy(self.events);changed["events"][0]["competitions"][0]["competitors"][0]["score"]="22"
        self.blocked(raw=json.dumps(changed).encode())
    def test_missing_final(self):
        self.events["events"][0]["status"]["type"]["completed"]=False
        self.blocked()
    def test_duplicate_event(self):
        self.events["events"][1]["id"]="101"
        self.blocked()
    def test_missing_event(self):
        self.events["events"].pop()
        self.blocked()
    def test_spoofed_host(self):
        self.blocked(source=URL.replace("site.api.espn.com","site.api.espn.com.attacker.test"))
    def test_late_retrieval(self):
        self.retrieved="2026-11-19T00:00:00Z"
        self.blocked()
    def test_late_archive(self):
        self.archived="2026-11-19T00:00:00Z"
        self.blocked()
    def test_unknown_git_commit(self):
        self.blocked(commit="a"*40)
    def test_conflicting_history(self):
        self.history["games"].append({"season":2026,"week":10,"id":"101","date":"2026-11-15T18:00:00Z","home":"Home101","away":"Away101","homeScore":99,"awayScore":10,"winner":"Home101"})
        self.blocked()
    def test_wrong_expected_ids(self):
        self.blocked(ids=["101","999"])
    def test_score_tie(self):
        self.events["events"][0]["competitions"][0]["competitors"][0]["score"]="10"
        self.blocked()
if __name__=="__main__":unittest.main()
