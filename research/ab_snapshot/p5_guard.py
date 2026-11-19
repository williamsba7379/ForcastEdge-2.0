"""Synthetic-only P5 guard; external anchor is a caller-supplied test oracle, not a real authority."""
import hashlib
import sqlite3
from contextlib import closing
from .trust_state import TrustStateError
from .durable_policy import DurablePolicyGate


class AnchoredPolicyGate(DurablePolicyGate):
    def __init__(self, root_public_key, path, manifest, signature, anchor):
        if not isinstance(anchor, dict) or type(anchor.get('version')) is not int or anchor['version'] < 1 or not isinstance(anchor.get('digest'), str) or len(anchor['digest']) != 64:
            raise TrustStateError('E501_ANCHOR_INVALID')
        self._anchor = dict(anchor)
        # Never initialize an empty or older database from a stale manifest.
        try:
            with closing(sqlite3.connect(path)) as db:
                row = db.execute('SELECT version,manifest,signature FROM policy WHERE id=1').fetchone()
        except sqlite3.OperationalError as exc:
            if 'no such table' not in str(exc):
                raise TrustStateError('E401_STATE_INVALID') from exc
            row = None
        except sqlite3.Error as exc:
            raise TrustStateError('E401_STATE_INVALID') from exc
        if row is None:
            version, _ = self._decode_without_instance(root_public_key, manifest, signature)
            if version != anchor['version'] or hashlib.sha256(manifest+signature).hexdigest() != anchor['digest']:
                raise TrustStateError('E502_ANCHOR_MISMATCH')
        else:
            if row[0] != anchor['version'] or hashlib.sha256(row[1]+row[2]).hexdigest() != anchor['digest']:
                raise TrustStateError('E502_ANCHOR_MISMATCH')
        super().__init__(root_public_key, path, manifest, signature)
        self._check_anchor()

    @staticmethod
    def _decode_without_instance(root, manifest, signature):
        from .policy_version import VersionedPolicyGate
        obj = object.__new__(VersionedPolicyGate)
        obj._root = root
        return obj._decode(manifest, signature)

    def _check_anchor(self):
        with closing(sqlite3.connect(self._path, timeout=5)) as db:
            row = db.execute('SELECT version,manifest,signature FROM policy WHERE id=1').fetchone()
        if row is None or row[0] != self._anchor['version'] or hashlib.sha256(row[1]+row[2]).hexdigest() != self._anchor['digest']:
            raise TrustStateError('E502_ANCHOR_MISMATCH')

    def verify(self, required_version, envelope, payload, schedule, registry, context):
        with self._lock:
            try:
                self._check_anchor()
                # Refuse a second process's newer policy until this instance is restarted.
                if self._version != self._anchor['version']:
                    raise TrustStateError('E502_ANCHOR_MISMATCH')
            except (sqlite3.Error, TrustStateError):
                from .trusted_contract import _fail
                return _fail('E502_ANCHOR_MISMATCH')
            return super().verify(required_version, envelope, payload, schedule, registry, context)
