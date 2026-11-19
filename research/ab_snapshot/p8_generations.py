"""Synthetic-only generation publication. External expected digest is caller controlled."""
import hashlib
import json
import os
import pathlib
import sqlite3
from contextlib import closing

class PublicationError(Exception):
    pass

def digest(b):
    return hashlib.sha256(b).hexdigest()

def encode(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()

class GenerationStore:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS generations (id INTEGER PRIMARY KEY, policy BLOB NOT NULL, anchor BLOB NOT NULL, signature BLOB NOT NULL, anchor_digest TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS active (singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation INTEGER NOT NULL)')

    def stage(self, generation, policy, anchor, signature):
        if type(generation) is not int or generation < 1 or not all(type(x) is bytes for x in (policy, anchor, signature)):
            raise PublicationError('E801_INVALID')
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('INSERT INTO generations VALUES (?,?,?,?,?)', (generation,policy,anchor,signature,digest(anchor)))

    def activate(self, generation):
        with closing(sqlite3.connect(self.path,timeout=10,isolation_level=None)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                old=db.execute('SELECT generation FROM active WHERE singleton=1').fetchone()
                if old and generation <= old[0]:
                    raise PublicationError('E802_ROLLBACK')
                if not db.execute('SELECT 1 FROM generations WHERE id=?',(generation,)).fetchone():
                    raise PublicationError('E803_MISSING_GENERATION')
                db.execute('INSERT INTO active VALUES (1,?) ON CONFLICT(singleton) DO UPDATE SET generation=excluded.generation',(generation,))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def read(self, expected_generation, expected_anchor_digest, verifier):
        with closing(sqlite3.connect(self.path,timeout=10,isolation_level=None)) as db:
            db.execute('BEGIN')
            try:
                row=db.execute('SELECT generation FROM active WHERE singleton=1').fetchone()
                if not row or row[0] != expected_generation:
                    raise PublicationError('E804_EXTERNAL_VERSION_MISMATCH')
                record=db.execute('SELECT policy,anchor,signature,anchor_digest FROM generations WHERE id=?',(row[0],)).fetchone()
                if not record or digest(record[1]) != expected_anchor_digest or record[3] != expected_anchor_digest:
                    raise PublicationError('E805_EXTERNAL_ANCHOR_MISMATCH')
                verifier(record[0],record[1],record[2])
                return row[0]
            finally:
                db.rollback()
