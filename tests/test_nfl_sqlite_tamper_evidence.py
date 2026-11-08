"""Offline tamper-evidence limitations and independently anchored digest fixtures."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from nfl_sqlite_evidence_store import SQLiteAppendOnlyEvidence
from test_nfl_sqlite_evidence_store import fixture

def anchored_digest(record):
    return hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def coordinated_replacement(path, record):
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER reject_evidence_update")
        db.execute("UPDATE first_final_evidence SET evidence_json=?,raw_response=?,content_sha256=? WHERE game_id=?",
            (json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=False),
             record["rawResponse"],record["contentSha256"],record["gameId"]))

class TamperEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=str(Path(temp.name)/"evidence.sqlite3")
        self.store=SQLiteAppendOnlyEvidence(self.path)
        self.record,self.schedule=fixture()
        self.assertTrue(self.store.submit(self.record,self.schedule)[0])

    def test_raw_only_change_detected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER reject_evidence_update")
            db.execute("UPDATE first_final_evidence SET raw_response='altered' WHERE game_id=?",(self.record["gameId"],))
        with self.assertRaisesRegex(ValueError,"STORED_EVIDENCE_INTEGRITY_FAILURE"):
            self.store.get(self.record["gameId"])

    def test_coordinated_internal_hash_replacement_is_not_detected(self):
        altered=dict(self.record)
        altered["rawResponse"]=self.record["rawResponse"]+" "
        altered["contentSha256"]=hashlib.sha256(altered["rawResponse"].encode()).hexdigest()
        coordinated_replacement(self.path,altered)
        # Demonstrates the security gap; does not claim this is protected.
        self.assertEqual(self.store.get(self.record["gameId"]),altered)

    def test_independent_external_anchor_detects_coordinated_replacement(self):
        # Anchor is outside the SQLite file, and is never rewritten by the attacker.
        anchor_path=Path(self.path).with_suffix(".anchor")
        anchor_path.write_text(anchored_digest(self.record),encoding="ascii")
        altered=dict(self.record)
        altered["rawResponse"]=self.record["rawResponse"]+" "
        altered["contentSha256"]=hashlib.sha256(altered["rawResponse"].encode()).hexdigest()
        coordinated_replacement(self.path,altered)
        self.assertNotEqual(anchored_digest(self.store.get(self.record["gameId"])),anchor_path.read_text(encoding="ascii"))
        # This is an unsigned test anchor, NOT a production signed or remote archive.

if __name__=="__main__": unittest.main()
