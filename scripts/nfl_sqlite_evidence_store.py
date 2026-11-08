"""Offline-only SQLite first-final evidence prototype. No network or production integration."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from nfl_future_evidence_safeguards import MemoryAppendOnlyEvidence

_SCHEMA = """
CREATE TABLE IF NOT EXISTS first_final_evidence (
 game_id TEXT PRIMARY KEY NOT NULL,
 evidence_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 raw_response TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS reject_evidence_update
BEFORE UPDATE ON first_final_evidence BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_EVIDENCE'); END;
CREATE TRIGGER IF NOT EXISTS reject_evidence_delete
BEFORE DELETE ON first_final_evidence BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_EVIDENCE'); END;
"""

class SQLiteAppendOnlyEvidence:
    """Research-only file-backed SQLite store. Not a tamper-proof archive."""
    def __init__(self, db_path):
        self.path = str(Path(db_path))
        if self.path == ':memory:':
            raise ValueError('durable file path required')
        with self._connect() as db:
            mode = db.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower()
            if mode != 'delete':
                raise RuntimeError('UNVERIFIED_SQLITE_JOURNAL_MODE')
            db.executescript(_SCHEMA)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=10000')
            db.execute('PRAGMA synchronous=FULL')
            if db.execute('PRAGMA synchronous').fetchone()[0] != 2:
                raise RuntimeError('UNVERIFIED_SQLITE_SYNCHRONOUS_MODE')
            yield db
        finally:
            db.close()

    def submit(self, record, schedule):
        valid, reason = MemoryAppendOnlyEvidence().submit(record, schedule)
        if not valid:
            return False, reason
        try:
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM first_final_evidence WHERE game_id=?', (record['gameId'],)).fetchone():
                    db.execute('ROLLBACK')
                    return False, 'EXISTING_FIRST_OBSERVATION_IMMUTABLE'
                frozen = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
                db.execute('INSERT INTO first_final_evidence (game_id,evidence_json,content_sha256,raw_response) VALUES (?,?,?,?)',
                           (record['gameId'], frozen, record['contentSha256'], record['rawResponse']))
                db.execute('COMMIT')
            return True, 'FIRST_FINAL_OBSERVED'
        except sqlite3.IntegrityError:
            return False, 'EXISTING_FIRST_OBSERVATION_IMMUTABLE'
        except sqlite3.Error:
            return False, 'STORAGE_ERROR'

    def get(self, game_id):
        with self._connect() as db:
            row = db.execute('SELECT evidence_json,content_sha256,raw_response FROM first_final_evidence WHERE game_id=?', (game_id,)).fetchone()
        if row is None:
            return None
        evidence = json.loads(row[0])
        if (evidence.get('rawResponse') != row[2] or
            evidence.get('contentSha256') != row[1] or
            hashlib.sha256(row[2].encode('utf-8')).hexdigest() != row[1]):
            raise ValueError('STORED_EVIDENCE_INTEGRITY_FAILURE')
        return evidence
