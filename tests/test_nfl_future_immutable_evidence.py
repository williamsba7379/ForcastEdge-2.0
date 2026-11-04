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

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=10"
def command(root,*args,env=None):
    return subprocess.check_output(["git","-C",str(root),*args],env=env).decode().strip()
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        command(self.root,"init","-q")
        command(self.root,"config","user.email","research@example.invalid")
        command(self.root,"config","user.name","Offline Fixture")
        self.report={"season":2026,"week":10,"status":"COMPLETE","gamesCompleted":2,"gamesRemaining":0,"scoreSource":URL,
          "results":[{"gameId":str(i),"date":"2026-11-15T18:00Z","home":"Home"+str(i),"away":"Away"+str(i),"homeScore":21,"awayScore":10,"winner":"Home"+str(i),"scoreSource":URL} for i in (101,102)]}
        raw={"provider":"ESPN","sourceUrl":URL,"season":2026,"week":10,"results":[{k:v for k,v in g.items() if k!="scoreSource"} for g in self.report["results"]]}
        self.raw=json.dumps(raw,sort_keys=True).encode()
        (self.root/"source.json").write_bytes(self.raw)
        command(self.root,"add","source.json")
        env=os.environ.copy();env["GIT_AUTHOR_DATE"]="2026-11-16T02:30:00+00:00";env["GIT_COMMITTER_DATE"]="2026-11-16T02:30:00+00:00"
        command(self.root,"commit","-qm","fixture",env=env)
        self.manifest={"provider":"ESPN","sourceUrl":URL,"rawResponseSha256":hashlib.sha256(self.raw).hexdigest(),
          "archiveCommit":command(self.root,"rev-parse","HEAD"),"archivePath":"source.json",
          "archiveBlob":command(self.root,"rev-parse","HEAD:source.json"),
          "retrievedAt":"2026-11-16T02:00Z","archivedAt":"2026-11-16T03:00Z","reportSha256":sha(self.report)}
        self.history={"games":[]};self.cutoff="2026-11-18T17:00Z";self.ids=["101","102"]
    def check(self,expected="BLOCKED"):
        r,c=verify(self.root,self.history,self.report,self.manifest,self.cutoff,self.ids)
        self.assertEqual(r["status"],expected)
        self.assertFalse(r["promotionAuthorized"])
        self.assertEqual(self.history,{"games":[]})
        if expected=="BLOCKED":self.assertEqual(c,self.history)
        return r
    def test_verified_bytes_and_commit(self):
        r=self.check("RESEARCH_READY");self.assertEqual(r["addedCount"],2)
    def test_bad_raw_sha(self):
        self.manifest["rawResponseSha256"]="a"*64;self.check()
    def test_wrong_blob(self):
        self.manifest["archiveBlob"]="a"*40;self.check()
    def test_unknown_commit(self):
        self.manifest["archiveCommit"]="a"*40;self.check()
    def test_path_traversal(self):
        self.manifest["archivePath"]="../source.json";self.check()
    def test_wrong_archive_path(self):
        self.manifest["archivePath"]="missing.json";self.check()
    def test_spoofed_archive_time(self):
        self.manifest["archivedAt"]="2026-11-16T01:00Z";self.check()
    def test_stale_archive_after_cutoff(self):
        self.cutoff="2026-11-16T02:15Z";self.check()
    def test_late_retrieval(self):
        self.manifest["retrievedAt"]="2026-11-16T04:00Z";self.check()
    def test_spoofed_report_hash(self):
        self.manifest["reportSha256"]="f"*64;self.check()
    def test_score_tampering_with_rehashed_report(self):
        self.report["results"][0]["homeScore"]=22;self.manifest["reportSha256"]=sha(self.report);self.check()
    def test_id_tampering_with_rehashed_report(self):
        self.report["results"][0]["gameId"]="999";self.manifest["reportSha256"]=sha(self.report);self.check()
    def test_missing_final_with_rehashed_report(self):
        self.report["results"].pop();self.report["gamesCompleted"]=1;self.manifest["reportSha256"]=sha(self.report);self.check()
    def test_duplicate_final_with_rehashed_report(self):
        self.report["results"][1]["gameId"]="101";self.manifest["reportSha256"]=sha(self.report);self.check()
    def test_conflicting_existing_score(self):
        self.history["games"].append({"season":2026,"week":10,"id":"101","date":"2026-11-15T18:00Z","home":"Home101","away":"Away101","homeScore":88,"awayScore":10,"winner":"Home101"})
        r,c=verify(self.root,self.history,self.report,self.manifest,self.cutoff,self.ids)
        self.assertEqual(r["status"],"BLOCKED");self.assertEqual(c,self.history)
    def test_wrong_source(self):
        self.manifest["sourceUrl"]="https://fake.example";self.check()
if __name__=="__main__":unittest.main()
