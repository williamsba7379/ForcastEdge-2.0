"""Synthetic P7 publication verifier: fail closed across independently published artifacts.

No claim of atomicity across two files or of a genuine external anti-rollback authority.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from .validator import canonical, parse

class PublicationError(ValueError):
    def __init__(self, code):
        self.code=code
        super().__init__(code)

def make_anchor(root_private, policy: bytes, version: int):
    doc=canonical({'version':version,'policySha256':hashlib.sha256(policy).hexdigest()})
    return doc,root_private.sign(doc)

def check_publication(policy: bytes, anchor: bytes, signature: bytes, root_public, expected_anchor_digest: str):
    """The expected digest MUST come from outside the two potentially rolled-back files."""
    try:
        if any(type(x) is not bytes for x in (policy,anchor,signature)) or type(expected_anchor_digest) is not str:
            raise ValueError('type')
        if hashlib.sha256(anchor).hexdigest()!=expected_anchor_digest:
            raise PublicationError('E703_EXTERNAL_ANCHOR_MISMATCH')
        root_public.verify(signature,anchor)
        a=parse(anchor);p=parse(policy)
        if (canonical(a)!=anchor or canonical(p)!=policy or not isinstance(a,dict)
            or set(a)!={'version','policySha256'} or type(a['version']) is not int
            or a['version']<1 or not isinstance(p,dict) or p.get('version')!=a['version']
            or a['policySha256']!=hashlib.sha256(policy).hexdigest()):
            raise PublicationError('E702_POLICY_ANCHOR_MISMATCH')
        return a['version']
    except PublicationError:
        raise
    except (InvalidSignature, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as exc:
        raise PublicationError('E701_PUBLICATION_INVALID') from exc

def publish_one(path, data):
    """Atomic single-file replacement only; fsync parent directory for rename durability."""
    path=Path(path)
    tmp=path.with_name(path.name+'.pending.'+str(os.getpid()))
    try:
        with open(tmp,'xb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        try:tmp.unlink()
        except FileNotFoundError:pass
