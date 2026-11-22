"""Synthetic-only integration: verify all claims before atomic replay registration."""
from __future__ import annotations
import hashlib
from .validator import canonical, parse, EvidenceError, MAX_BYTES
from .trusted_contract import _utc, _fail, FIELDS, HEX, cutoff
from .trust_state import SyntheticTrustStore, SQLiteReplayRegistry, TrustStateError
from cryptography.exceptions import InvalidSignature
import re

def verify_and_register(envelope_bytes, payload_bytes, schedule_bytes, trust_store, replay_registry, expected_context):
    try:
        if not isinstance(trust_store, SyntheticTrustStore) or not isinstance(replay_registry, SQLiteReplayRegistry) or not isinstance(expected_context, dict):
            return _fail('E101_INPUT_INVALID')
        if any(type(x) is not bytes or len(x)>MAX_BYTES for x in (envelope_bytes,payload_bytes,schedule_bytes)):
            return _fail('E101_INPUT_INVALID')
        env=parse(envelope_bytes)
        if not isinstance(env,dict) or set(env)!={'evidence','signature'} or not isinstance(env['evidence'],dict):
            return _fail('E101_INPUT_INVALID')
        e=env['evidence']
        if set(e)!=FIELDS or any(type(e[k]) is not str for k in FIELDS) or type(env['signature']) is not str or not re.fullmatch('[0-9a-f]{128}',env['signature']):
            return _fail('E101_INPUT_INVALID')
        if canonical(env)!=envelope_bytes or e['contractVersion']!='1.0-SYNTHETIC' or e['signatureAlgorithm']!='Ed25519':
            return _fail('E101_INPUT_INVALID')
        if not all(HEX.fullmatch(e[k]) for k in ('payloadSha256','scheduleSha256')):
            return _fail('E101_INPUT_INVALID')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',e['captureId']) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,256}',e['sourceIdentity']) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',e['signerKeyId']):
            return _fail('E101_INPUT_INVALID')
        if any(e[k]!=expected_context.get(k) for k in ('season','week','freezeDate','sourceIdentity')):
            return _fail('E105_CONTEXT_MISMATCH')
        # Trust-store authorization and signature verification precede any state mutation.
        try:
            key=trust_store.authorize(e['signerKeyId'],'capture',e['trustedTimestampUtc'])
        except TrustStateError as exc:
            return _fail(exc.code)
        try:
            key.verify(bytes.fromhex(env['signature']),canonical(e))
        except InvalidSignature:
            return _fail('E102_SIGNATURE_INVALID')
        if hashlib.sha256(payload_bytes).hexdigest()!=e['payloadSha256'] or hashlib.sha256(schedule_bytes).hexdigest()!=e['scheduleSha256']:
            return _fail('E103_CONTENT_MISMATCH')
        completed=_utc(e['captureCompletedUtc']); stamped=_utc(e['trustedTimestampUtc'])
        if completed>stamped or stamped>cutoff(e['freezeDate']):
            return _fail('E104_CUTOFF_INVALID')
        # The durable unique INSERT is the replay check; never check-then-insert.
        try:
            replay_registry.register(e['captureId'],hashlib.sha256(envelope_bytes).hexdigest())
        except TrustStateError as exc:
            return _fail(exc.code)
        return {'passed':True,'errors':[],'syntheticOnly':True,'historicalCertification':False}
    except (EvidenceError, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        return _fail('E101_INPUT_INVALID')
