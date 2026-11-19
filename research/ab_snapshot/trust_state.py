"""Research-only synthetic trust policy and durable SQLite replay state; no production imports."""
from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass
from contextlib import closing
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

class TrustStateError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', value):
        raise TrustStateError('E201_POLICY_INVALID')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise TrustStateError('E201_POLICY_INVALID') from exc

@dataclass(frozen=True)
class KeyRecord:
    key_id: str
    public_key: Ed25519PublicKey
    purpose: str
    active_from: str
    active_until: str
    revoked_at: str | None = None

class SyntheticTrustStore:
    """Locally configured policy; not an authenticated CA, timestamp authority or key-status feed."""
    def __init__(self, records):
        if not isinstance(records, (tuple, list)) or not records:
            raise TrustStateError('E201_POLICY_INVALID')
        keys = {}
        for record in records:
            if not isinstance(record, KeyRecord) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', record.key_id) or record.key_id in keys:
                raise TrustStateError('E201_POLICY_INVALID')
            if not isinstance(record.public_key, Ed25519PublicKey) or record.purpose not in ('capture', 'schedule'):
                raise TrustStateError('E201_POLICY_INVALID')
            if _time(record.active_from) >= _time(record.active_until):
                raise TrustStateError('E201_POLICY_INVALID')
            if record.revoked_at is not None:
                _time(record.revoked_at)
            keys[record.key_id] = record
        self._keys = MappingProxyType(keys)

    def authorize(self, key_id, purpose, signed_at):
        record = self._keys.get(key_id) if isinstance(key_id, str) else None
        if record is None or purpose not in ('capture', 'schedule') or record.purpose != purpose:
            raise TrustStateError('E202_KEY_UNAUTHORIZED')
        instant = _time(signed_at)
        if not (_time(record.active_from) <= instant < _time(record.active_until)):
            raise TrustStateError('E202_KEY_UNAUTHORIZED')
        # Fail closed even for evidence purportedly signed before revocation.
        if record.revoked_at is not None:
            raise TrustStateError('E203_KEY_REVOKED')
        return record.public_key

class SQLiteReplayRegistry:
    """SQLite unique constraint is the atomic cross-process replay boundary."""
    def __init__(self, path):
        if not isinstance(path, (str, Path)) or str(path) == ':memory:':
            raise TrustStateError('E204_STORAGE_INVALID')
        self.path = str(path)
        try:
            with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS captures (capture_id TEXT PRIMARY KEY, digest TEXT NOT NULL)')
        except sqlite3.Error as exc:
            raise TrustStateError('E204_STORAGE_INVALID') from exc

    def register(self, capture_id, digest):
        if not isinstance(capture_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', capture_id) or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise TrustStateError('E205_CAPTURE_INVALID')
        try:
            with closing(sqlite3.connect(self.path, timeout=5, isolation_level='IMMEDIATE')) as db, db:
                db.execute('INSERT INTO captures (capture_id, digest) VALUES (?, ?)', (capture_id, digest))
            return True
        except sqlite3.IntegrityError as exc:
            raise TrustStateError('E206_REPLAY') from exc
        except sqlite3.Error as exc:
            raise TrustStateError('E204_STORAGE_INVALID') from exc
