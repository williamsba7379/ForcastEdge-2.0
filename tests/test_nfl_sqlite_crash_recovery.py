"""Offline process-crash fixtures; only temporary SQLite databases, never network."""
import multiprocessing as mp
import sqlite3
import tempfile
import unittest
from pathlib import Path
from nfl_sqlite_evidence_store import SQLiteAppendOnlyEvidence
from test_nfl_sqlite_evidence_store import fixture

def interrupted_transaction(path, ready, proceed):
    db=sqlite3.connect(path, isolation_level=None)
    db.execute("BEGIN IMMEDIATE")
    db.execute("INSERT INTO first_final_evidence (game_id,evidence_json,content_sha256,raw_response) VALUES ('999','{}','x','x')")
    ready.set()
    proceed.wait(20)
    # Parent terminates before this commit.

def committed_then_wait(path, record, schedule, ready, proceed):
    result=SQLiteAppendOnlyEvidence(path).submit(record,schedule)
    if result[0]:
        ready.set()
    proceed.wait(20)

class CrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=str(Path(temp.name)/"evidence.sqlite3")
        self.store=SQLiteAppendOnlyEvidence(self.path)
        self.record,self.schedule=fixture()

    def _crash(self, target, args):
        ctx=mp.get_context("spawn")
        ready=ctx.Event()
        proceed=ctx.Event()
        process=ctx.Process(target=target,args=(*args,ready,proceed))
        process.start()
        try:
            self.assertTrue(ready.wait(15),"child failed to reach deterministic crash point")
            process.terminate()
            process.join(15)
            self.assertFalse(process.is_alive())
            self.assertNotEqual(process.exitcode,0)
        finally:
            if process.is_alive():
                process.kill()
                process.join(5)

    def test_crash_before_commit_rolls_back(self):
        self._crash(interrupted_transaction,(self.path,))
        self.assertIsNone(SQLiteAppendOnlyEvidence(self.path).get("999"))
        self.assertEqual(sqlite3.connect(self.path).execute("SELECT COUNT(*) FROM first_final_evidence").fetchone()[0],0)

    def test_crash_after_commit_preserves_record(self):
        self._crash(committed_then_wait,(self.path,self.record,self.schedule))
        self.assertEqual(SQLiteAppendOnlyEvidence(self.path).get(self.record["gameId"]),self.record)

    def test_integrity_after_interrupted_transaction(self):
        self._crash(interrupted_transaction,(self.path,))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        self.assertTrue(SQLiteAppendOnlyEvidence(self.path).submit(self.record,self.schedule)[0])

    def test_duplicate_after_crash_restart_rejected(self):
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])
        # Crash an unrelated uncommitted transaction, then reopen the first observation.
        self._crash(interrupted_transaction,(self.path,))
        reopened=SQLiteAppendOnlyEvidence(self.path)
        self.assertEqual(reopened.submit(self.record,self.schedule),(False,"EXISTING_FIRST_OBSERVATION_IMMUTABLE"))
        self.assertEqual(reopened.get(self.record["gameId"]),self.record)

    def test_explicit_durability_policy(self):
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0].lower(),"delete")
            # synchronous is connection-local: verify the store's own connection policy.
        with self.store._connect() as db:
            self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0],2)

if __name__=="__main__": unittest.main()
