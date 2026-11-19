"""Research-only synthetic Ed25519 evidence contract. NOT a historical timestamp authority."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .validator import canonical, parse, EvidenceError, cutoff, MAX_BYTES

HEX = re.compile(r'^[0-9a-f]{64}$')
FIELDS = {'contractVersion','captureId','season','week','freezeDate','payloadSha256','scheduleSha256',
          'sourceIdentity','captureCompletedUtc','trustedTimestampUtc','signerKeyId','signatureAlgorithm'}

def _fail(code):
    return {'passed': False, 'errors': [code], 'syntheticOnly': True, 'historicalCertification': False}

def _utc(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',value):
        raise ValueError('timestamp format')
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def verify(envelope_bytes, payload_bytes, schedule_bytes, trusted_keys, seen_captures, expected_context):
    """Caller supplies trusted public keys and previously accepted capture IDs; no I/O."""
    try:
        if any(not isinstance(x,bytes) or len(x)>MAX_BYTES for x in (envelope_bytes,payload_bytes,schedule_bytes)):
            return _fail('E101_INPUT_INVALID')
        env=parse(envelope_bytes)
        if not isinstance(env,dict) or set(env)!={'evidence','signature'} or not isinstance(env['evidence'],dict):
            return _fail('E101_INPUT_INVALID')
        e=env['evidence']
        if set(e)!=FIELDS or any(not isinstance(e[k],str) for k in FIELDS):
            return _fail('E101_INPUT_INVALID')
        if env['signature'] is None or not isinstance(env['signature'],str) or not re.fullmatch('[0-9a-f]{128}',env['signature']):
            return _fail('E101_INPUT_INVALID')
        if canonical(env)!=envelope_bytes or canonical(e)!=canonical(e):
            return _fail('E101_INPUT_INVALID')
        if e['contractVersion']!='1.0-SYNTHETIC' or e['signatureAlgorithm']!='Ed25519':
            return _fail('E101_INPUT_INVALID')
        if not all(HEX.fullmatch(e[k]) for k in ('payloadSha256','scheduleSha256')):
            return _fail('E101_INPUT_INVALID')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',e['captureId']) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,256}',e['sourceIdentity']):
            return _fail('E101_INPUT_INVALID')
        if not isinstance(trusted_keys,dict) or not isinstance(seen_captures,(set,frozenset)) or not isinstance(expected_context,dict):
            return _fail('E101_INPUT_INVALID')
        if any(e.get(k)!=expected_context.get(k) for k in ('season','week','freezeDate','sourceIdentity')):
            return _fail('E105_CONTEXT_MISMATCH')
        if e['captureId'] in seen_captures:
            return _fail('E106_REPLAY')
        key=trusted_keys.get(e['signerKeyId'])
        if not isinstance(key,Ed25519PublicKey):
            return _fail('E102_SIGNATURE_INVALID')
        try: key.verify(bytes.fromhex(env['signature']),canonical(e))
        except InvalidSignature: return _fail('E102_SIGNATURE_INVALID')
        if hashlib.sha256(payload_bytes).hexdigest()!=e['payloadSha256'] or hashlib.sha256(schedule_bytes).hexdigest()!=e['scheduleSha256']:
            return _fail('E103_CONTENT_MISMATCH')
        limit=cutoff(e['freezeDate'])
        completed=_utc(e['captureCompletedUtc']); stamped=_utc(e['trustedTimestampUtc'])
        if completed>stamped or stamped>limit:
            return _fail('E104_CUTOFF_INVALID')
        return {'passed':True,'errors':[],'syntheticOnly':True,'historicalCertification':False}
    except (EvidenceError,ValueError,TypeError,KeyError,AttributeError,RecursionError,OverflowError):
        return _fail('E101_INPUT_INVALID')
