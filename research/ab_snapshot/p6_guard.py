"""Synthetic-only P6 signed revocation anchors; not an external anti-rollback service."""
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from cryptography.exceptions import InvalidSignature
from .validator import canonical, parse, EvidenceError
from .p5_guard import AnchoredPolicyGate
from .trust_state import TrustStateError
from .trusted_contract import _fail


def tombstone_digest(ids):
    return hashlib.sha256(canonical(sorted(ids))).hexdigest()


class RevocationAnchoredGate(AnchoredPolicyGate):
    """Caller-pinned root signs the external anchor; verification holds a SQLite write lock."""
    def __init__(self, root, path, manifest, signature, anchor_bytes, anchor_signature):
        if not isinstance(anchor_bytes, bytes) or not isinstance(anchor_signature, bytes) or len(anchor_signature) != 64:
            raise TrustStateError('E601_ANCHOR_INVALID')
        try:
            root.verify(anchor_signature, anchor_bytes)
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise TrustStateError('E601_ANCHOR_INVALID') from exc
        try:
            anchor = parse(anchor_bytes)
            if (canonical(anchor) != anchor_bytes or not isinstance(anchor, dict)
                or set(anchor) != {'version', 'digest', 'revocationsSha256'}
                or type(anchor['version']) is not int or anchor['version'] < 1
                or any(not isinstance(anchor[k], str) or not re.fullmatch('[0-9a-f]{64}',anchor[k]) for k in ('digest','revocationsSha256'))):
                raise TrustStateError('E601_ANCHOR_INVALID')
        except (EvidenceError, ValueError, TypeError, RecursionError) as exc:
            raise TrustStateError('E601_ANCHOR_INVALID') from exc
        self._revocation_digest = anchor['revocationsSha256']
        super().__init__(root, path, manifest, signature, {'version':anchor['version'], 'digest':anchor['digest']})
        self._check_revocations()

    def _check_revocations(self, db=None):
        if db is None:
            with closing(sqlite3.connect(self._path, timeout=5)) as conn:
                return self._check_revocations(conn)
        ids = [row[0] for row in db.execute('SELECT key_id FROM revoked_ids')]
        if len(ids) != len(set(ids)) or tombstone_digest(ids) != self._revocation_digest:
            raise TrustStateError('E602_REVOCATION_MISMATCH')

    def verify(self, required_version, envelope, payload, schedule, registry, context):
        # Cross-process SQLite transaction serializes this read with policy writers.
        # It does not synchronize an independently updated external anchor.
        with self._lock:
            try:
                with closing(sqlite3.connect(self._path, timeout=5, isolation_level=None)) as db:
                    db.execute('BEGIN IMMEDIATE')
                    self._check_anchor_in(db)
                    self._check_revocations(db)
                    if self._version != self._anchor['version']:
                        raise TrustStateError('E502_ANCHOR_MISMATCH')
                    result = super(AnchoredPolicyGate, self).verify(required_version, envelope, payload, schedule, registry, context)
                    db.commit()
                    return result
            except (sqlite3.Error, TrustStateError):
                return _fail('E602_REVOCATION_MISMATCH')

    def _check_anchor_in(self, db):
        row = db.execute('SELECT version,manifest,signature FROM policy WHERE id=1').fetchone()
        if row is None or row[0] != self._anchor['version'] or hashlib.sha256(row[1]+row[2]).hexdigest() != self._anchor['digest']:
            raise TrustStateError('E502_ANCHOR_MISMATCH')
