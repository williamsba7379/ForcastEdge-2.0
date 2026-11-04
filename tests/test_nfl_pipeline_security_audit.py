"""Adversarial trust-boundary regression tests for the research-only pipeline."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.nfl_future_immutable_evidence import verify
from scripts.nfl_future_history_sync_gate import sha
from scripts.nfl_offline_capture_archive_sync import run
from scripts.nfl_espn_trusted_capture_offline import inspect_response

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def git(root,*args,env=None):
    return subprocess.check_output(["git","-C",str(root),*args],env=env).decode().strip()
class TrustTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        git(self.root,"init","-q");git(self.root,"config","user.name","Research");git(self.root,"config","user.email","test@example.invalid")
        self.report={"season":2026,"week":10,"status":"COMPLETE","gamesCompleted":1,"gamesRemaining":0,"scoreSource":URL,
          "results":[{"gameId":"101","date":"2026-11-15T18:00:00Z","home":"Home","away":"Away","homeScore":21,"awayScore":10,"winner":"Home","scoreSource":URL}]}
        self.raw=json.dumps({"provider":"ESPN","sourceUrl":URL,"season":2026,"week":10,"results":[{k:v for k,v in self.report["results"][0].items() if k!="scoreSource"}]}).encode()
        self.history={"games":[]};self.cutoff="2026-11-18T17:00:00Z"
    def commit(self,raw,author="2026-11-16T02:30:00+00:00",committer="2026-11-16T02:30:00+00:00"):
        (self.root/"raw.json").write_bytes(raw);git(self.root,"add","raw.json")
        env=os.environ.copy();env["GIT_AUTHOR_DATE"]=author;env["GIT_COMMITTER_DATE"]=committer
        git(self.root,"commit","-qm","fixture",env=env)
        return git(self.root,"rev-parse","HEAD")
    def manifest(self,commit,raw):
        return {"provider":"ESPN","sourceUrl":URL,"rawResponseSha256":hashlib.sha256(raw).hexdigest(),
          "archiveCommit":commit,"archivePath":"raw.json","archiveBlob":git(self.root,"rev-parse",commit+":raw.json"),
          "retrievedAt":"2026-11-16T02:00:00Z","archivedAt":"2026-11-16T03:00:00Z","reportSha256":sha(self.report)}
    def test_legacy_fixture_rejected_in_strict_mode(self):
        commit=self.commit(self.raw)
        r,c=verify(self.root,self.history,self.report,self.manifest(commit,self.raw),self.cutoff,["101"],require_native=True)
        self.assertEqual(r["status"],"BLOCKED");self.assertIn("NATIVE_ESPN_EVENTS_REQUIRED",r["errors"])
        self.assertEqual(c,self.history)
    def test_legacy_fixture_still_supported_only_for_old_regression(self):
        commit=self.commit(self.raw)
        r,c=verify(self.root,self.history,self.report,self.manifest(commit,self.raw),self.cutoff,["101"])
        self.assertEqual(r["status"],"RESEARCH_READY")
        self.assertFalse(r["promotionAuthorized"])
    def test_author_date_later_than_archive_rejected(self):
        commit=self.commit(self.raw,author="2026-11-19T00:00:00+00:00")
        r,c=verify(self.root,self.history,self.report,self.manifest(commit,self.raw),self.cutoff,["101"],require_native=True)
        self.assertIn("COMMIT_AFTER_ARCHIVE_OR_CUTOFF",r["errors"]);self.assertEqual(c,self.history)
    def test_committer_date_later_than_archive_rejected(self):
        commit=self.commit(self.raw,committer="2026-11-19T00:00:00+00:00")
        r,c=verify(self.root,self.history,self.report,self.manifest(commit,self.raw),self.cutoff,["101"],require_native=True)
        self.assertIn("COMMIT_AFTER_ARCHIVE_OR_CUTOFF",r["errors"]);self.assertEqual(c,self.history)
    def test_spoofed_native_metadata_not_accepted(self):
        commit=self.commit(self.raw)
        manifest=self.manifest(commit,self.raw);manifest["provider"]="FAKE"
        r,c=verify(self.root,self.history,self.report,manifest,self.cutoff,["101"],require_native=True)
        self.assertEqual(r["status"],"BLOCKED");self.assertEqual(c,self.history)
    def test_no_live_capture_or_history_write_on_failure(self):
        before=copy.deepcopy(self.history)
        r,c=run(self.root,self.history,b"{}","http://site.api.espn.com/", "2026-11-16T02:00:00Z",
                "2026-11-16T03:00:00Z",self.cutoff,2026,10,["101"],"a"*40,"raw.json")
        self.assertEqual(r["status"],"BLOCKED");self.assertEqual(c,before);self.assertEqual(self.history,before)
if __name__=="__main__":unittest.main()
