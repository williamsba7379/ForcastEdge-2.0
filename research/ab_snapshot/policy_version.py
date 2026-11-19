"""Synthetic P3 root-signed policy snapshots and serialized revocation boundary.

Not a real root of trust: caller supplies the pinned root public key. Policy version
is caller-required, NOT cryptographically bound to the capture evidence envelope.
"""
from __future__ import annotations
import json
import threading
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .validator import canonical, parse, EvidenceError, MAX_BYTES
from .trust_state import SyntheticTrustStore, KeyRecord, TrustStateError
from .trusted_integration import verify_and_register
from .trusted_contract import _fail

class VersionedPolicyGate:
    def __init__(self, root_public_key, initial_manifest, signature):
        if not isinstance(root_public_key, Ed25519PublicKey):
            raise TrustStateError('E301_ROOT_INVALID')
        self._root = root_public_key
        self._lock = threading.RLock()
        self._version = 0
        self._store = None
        self.update(initial_manifest, signature)

    def _decode(self, manifest, signature):
        if type(manifest) is not bytes or len(manifest) > MAX_BYTES or type(signature) is not bytes or len(signature) != 64:
            raise TrustStateError('E302_POLICY_INVALID')
        try:
            obj = parse(manifest)
            if canonical(obj) != manifest or not isinstance(obj, dict) or set(obj) != {'version', 'keys'}:
                raise TrustStateError('E302_POLICY_INVALID')
            if type(obj['version']) is not int or not 1 <= obj['version'] <= 2**63-1 or not isinstance(obj['keys'], list):
                raise TrustStateError('E302_POLICY_INVALID')
            self._root.verify(signature, manifest)
            records = []
            for item in obj['keys']:
                if not isinstance(item, dict) or set(item) != {'id','publicKeyHex','purpose','activeFrom','activeUntil','revokedAt'}:
                    raise TrustStateError('E302_POLICY_INVALID')
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                if type(item['publicKeyHex']) is not str or len(item['publicKeyHex']) != 64:
                    raise TrustStateError('E302_POLICY_INVALID')
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(item['publicKeyHex']))
                records.append(KeyRecord(item['id'], key, item['purpose'], item['activeFrom'], item['activeUntil'], item['revokedAt']))
            store = SyntheticTrustStore(records)
            return obj['version'], store
        except InvalidSignature as exc:
            raise TrustStateError('E303_POLICY_SIGNATURE_INVALID') from exc
        except (EvidenceError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            if isinstance(exc, TrustStateError):
                raise
            raise TrustStateError('E302_POLICY_INVALID') from exc

    def update(self, manifest, signature):
        version, store = self._decode(manifest, signature)
        with self._lock:
            if version <= self._version:
                raise TrustStateError('E304_POLICY_ROLLBACK')
            self._version, self._store = version, store

    def verify(self, required_version, envelope, payload, schedule, registry, context):
        with self._lock:
            if type(required_version) is not int or required_version != self._version:
                return _fail('E305_STALE_POLICY')
            return verify_and_register(envelope, payload, schedule, self._store, registry, context)

    @property
    def version(self):
        with self._lock:
            return self._version
