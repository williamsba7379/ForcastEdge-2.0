"""Offline-only durable evidence store regression tests; no network calls."""
import hashlib
import json
import multiprocessing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from nfl_sqlite_evidence_store import SQLiteAppendOnlyEvidence

K='2026-11-08T18:00:00Z'
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
def fixture():
    schedule={'gameId':'401123456','season':2026,'week':10,'homeTeamId':'1','awayTeamId':'2','kickoffAt':K}
    event={'id':'401123456','season':{'year':2026},'week':{'number':10},'date':K,'status':{'type':{'completed':True}},'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'1'},'score':'21'},{'homeAway':'away','team':{'id':'2'},'score':'17'}]}]}
    raw=json.dumps({'events':[event]},sort_keys=True)
    record={'gameId':'401123456','source':URL,'kickoffAt':K,'observedFinalAt':'2026-11-08T22:00:00Z','retrievedAt':'2026-11-08T22:01:00Z','rawResponse':raw,'contentSha256':hashlib.sha256(raw.encode()).hexdigest()}
    return record,schedule

def submit_process(path,record,schedule,output):
    output.put(SQLiteAppendOnlyEvidence(path).submit(record,schedule))

class SQLiteEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=str(Path(self.tmp.name)/'evidence.sqlite3')
        self.store=SQLiteAppendOnlyEvidence(self.path)
        self.record,self.schedule=fixture()

    def test_restart_persistence(self):
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])
        self.assertEqual(SQLiteAppendOnlyEvidence(self.path).get(self.record['gameId']),self.record)

    def test_duplicate_submission_rejected(self):
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])
        self.assertEqual(SQLiteAppendOnlyEvidence(self.path).submit(self.record,self.schedule),(False,'EXISTING_FIRST_OBSERVATION_IMMUTABLE'))

    def test_cross_process_concurrency(self):
        ctx=multiprocessing.get_context('spawn')
        q=ctx.Queue()
        processes=[ctx.Process(target=submit_process,args=(self.path,self.record,self.schedule,q)) for _ in range(8)]
        for p in processes:p.start()
        results=[q.get(timeout=20) for _ in processes]
        for p in processes:
            p.join(20)
            self.assertEqual(p.exitcode,0)
        self.assertEqual(sum(ok for ok,_ in results),1)
        self.assertEqual(sum(reason=='EXISTING_FIRST_OBSERVATION_IMMUTABLE' for _,reason in results),7)

    def test_hash_mismatch_rejected(self):
        self.record['rawResponse']+='changed'
        self.assertEqual(self.store.submit(self.record,self.schedule)[1],'CONTENT_HASH_MISMATCH')
        self.assertIsNone(self.store.get(self.record['gameId']))

    def test_raw_response_roundtrip_and_hash(self):
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])
        saved=self.store.get(self.record['gameId'])
        self.assertEqual(saved['rawResponse'],self.record['rawResponse'])
        self.assertEqual(hashlib.sha256(saved['rawResponse'].encode()).hexdigest(),saved['contentSha256'])

    def test_immutable_first_observation(self):
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])
        original=self.store.get(self.record['gameId'])
        self.record['observedFinalAt']='2026-11-08T22:02:00Z'
        self.assertFalse(self.store.submit(self.record,self.schedule)[0])
        self.assertEqual(self.store.get(self.record['gameId']),original)

    def test_sql_update_delete_blocked(self):
        self.store.submit(self.record,self.schedule)
        db=sqlite3.connect(self.path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('UPDATE first_final_evidence SET raw_response=? WHERE game_id=?',('bad',self.record['gameId']))
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('DELETE FROM first_final_evidence WHERE game_id=?',(self.record['gameId'],))
        finally:
            db.close()
        self.assertEqual(self.store.get(self.record['gameId']),self.record)

    def test_tampered_database_detected_on_read(self):
        self.store.submit(self.record,self.schedule)
        db=sqlite3.connect(self.path)
        try:
            db.execute('DROP TRIGGER reject_evidence_update')
            db.execute('UPDATE first_final_evidence SET raw_response=? WHERE game_id=?',('tampered',self.record['gameId']))
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(ValueError,'STORED_EVIDENCE_INTEGRITY_FAILURE'):
            self.store.get(self.record['gameId'])

    def test_invalid_schedule_fail_closed(self):
        self.assertFalse(self.store.submit(self.record,{})[0])
        self.assertIsNone(self.store.get(self.record['gameId']))

    def test_reject_memory_database(self):
        with self.assertRaises(ValueError):
            SQLiteAppendOnlyEvidence(':memory:')

if __name__=='__main__': unittest.main()
