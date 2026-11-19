"""Synthetic-only durable policy gate; SQLite is not tamper-proof or a trusted clock."""
import hashlib
import sqlite3
from contextlib import closing
from .policy_version import VersionedPolicyGate
from .trust_state import TrustStateError

class DurablePolicyGate(VersionedPolicyGate):
    def __init__(self, root_public_key, path, manifest, signature):
        if not isinstance(path, str) or not path or path == ':memory:':
            raise TrustStateError('E401_STATE_INVALID')
        self._path = path
        self._root = root_public_key
        import threading
        self._lock = threading.RLock()
        self._version = 0
        self._store = None
        self._digest = None
        try:
            with closing(sqlite3.connect(path, timeout=5)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, manifest BLOB NOT NULL, signature BLOB NOT NULL, digest TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS revoked_ids (key_id TEXT PRIMARY KEY)')
            self._recover(manifest, signature)
        except sqlite3.Error as exc:
            raise TrustStateError('E401_STATE_INVALID') from exc

    def _recover(self, manifest, signature):
        with closing(sqlite3.connect(self._path, timeout=5)) as db:
            row = db.execute('SELECT version,manifest,signature,digest FROM policy WHERE id=1').fetchone()
        if row is None:
            self.update(manifest, signature)
            return
        version, saved, sig, digest = row
        if hashlib.sha256(saved+sig).hexdigest() != digest:
            raise TrustStateError('E402_STATE_TAMPERED')
        decoded, store = self._decode(saved, sig)
        if version != decoded:
            raise TrustStateError('E402_STATE_TAMPERED')
        self._version, self._store, self._digest = version, store, digest
        if manifest != saved or signature != sig:
            # Reopening with an old/different policy must not silently accept it.
            candidate, _ = self._decode(manifest, signature)
            if candidate <= version:
                raise TrustStateError('E304_POLICY_ROLLBACK')
            self.update(manifest, signature)

    def update(self, manifest, signature):
        version, store = self._decode(manifest, signature)
        digest = hashlib.sha256(manifest+signature).hexdigest()
        with self._lock:
            try:
                with closing(sqlite3.connect(self._path, timeout=5, isolation_level=None)) as db:
                    db.execute('BEGIN IMMEDIATE')
                    row = db.execute('SELECT version,manifest,signature,digest FROM policy WHERE id=1').fetchone()
                    if row is not None:
                        prior, saved, sig, stored_digest = row
                        if hashlib.sha256(saved+sig).hexdigest()!=stored_digest:
                            raise TrustStateError('E402_STATE_TAMPERED')
                        verified, previous = self._decode(saved, sig)
                        if prior != verified:
                            raise TrustStateError('E402_STATE_TAMPERED')
                        if version <= prior:
                            raise TrustStateError('E304_POLICY_ROLLBACK')
                        for key_id, record in previous._keys.items():
                            if record.revoked_at is not None and key_id in store._keys:
                                raise TrustStateError('E306_REVOKED_KEY_REUSE')
                    tombstones={r[0] for r in db.execute('SELECT key_id FROM revoked_ids')}
                    if any(key_id in store._keys for key_id in tombstones):
                        raise TrustStateError('E306_REVOKED_KEY_REUSE')
                    for key_id, record in store._keys.items():
                        if record.revoked_at is not None:
                            db.execute('INSERT OR IGNORE INTO revoked_ids (key_id) VALUES (?)',(key_id,))
                    db.execute('INSERT INTO policy (id,version,manifest,signature,digest) VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,manifest=excluded.manifest,signature=excluded.signature,digest=excluded.digest', (version,manifest,signature,digest))
                    db.commit()
            except sqlite3.Error as exc:
                raise TrustStateError('E401_STATE_INVALID') from exc
            self._version, self._store, self._digest = version, store, digest
