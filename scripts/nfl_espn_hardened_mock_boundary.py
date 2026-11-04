"""Research-only hardened mock evidence boundary. No network or production writes.

Attestations are injected by a hypothetical trusted adapter; strings alone are not proof.
This module fails closed without independently provisioned trust anchors.
"""
import hashlib
import hmac
import json
from datetime import timedelta
from scripts.nfl_espn_mock_transport_contract import evaluate
from scripts.nfl_future_history_sync_gate import time,sha
from scripts.nfl_espn_trusted_capture_offline import MAX_BYTES

def signed_schedule(manifest, trusted_digest):
    if not isinstance(trusted_digest,str) or len(trusted_digest)!=64:
        return False
    return hmac.compare_digest(sha({k:v for k,v in manifest.items() if k!="scheduleSha256"}),trusted_digest)

def harden(response,manifest,season,week,cutoff,trust):
    problems=[]
    # These opaque adapter identities and digests must be provisioned out of band,
    # never accepted as assertions copied from the response itself.
    if trust.get("adapterIdentity")!="APPROVED_OFFLINE_TEST_ADAPTER" or trust.get("trustedTransportDigest") is None:
        problems.append("NO_TRUSTED_TRANSPORT_ADAPTER")
    if not signed_schedule(manifest,trust.get("trustedScheduleDigest")):
        problems.append("UNTRUSTED_SCHEDULE_PROVENANCE")
    if trust.get("clockSource")!="APPROVED_MONOTONIC_CAPTURE_CLOCK":
        problems.append("UNTRUSTED_CLOCK")
    if response.get("redirectChain")!=[] or response.get("redirectCount")!=0:
        problems.append("REDIRECT_CHAIN")
    if response.get("tlsVersion")!="TLSv1.3" or response.get("certificateValidation")!="SYSTEM_TRUST_CHAIN_AND_HOSTNAME":
        problems.append("TLS_ATTESTATION_INCOMPLETE")
    if response.get("transferEncoding") not in ("identity",None) or response.get("contentEncoding") not in ("identity",None):
        problems.append("UNSUPPORTED_ENCODING")
    raw=response.get("raw")
    chunks=response.get("chunks")
    if not isinstance(chunks,list) or any(not isinstance(c,bytes) for c in chunks) or sum(map(len,chunks))>MAX_BYTES or not isinstance(raw,bytes) or b"".join(chunks)!=raw:
        problems.append("STREAM_SIZE_OR_CONTENT_MISMATCH")
    if type(response.get("status")) is not int or type(response.get("contentLength")) is not int or type(response.get("timeoutSeconds")) not in (int,float):
        problems.append("MALFORMED_HTTP_METADATA")
    try:
        start=time(response["startedAt"]);end=time(response["completedAt"]);observed=time(trust["clockObservedAt"])
        if start>end or end>observed or observed-end>timedelta(seconds=2) or observed>time(cutoff):
            problems.append("CLOCK_PROVENANCE_OR_CUTOFF")
    except (KeyError,ValueError,TypeError,AttributeError):
        problems.append("CLOCK_PROVENANCE_OR_CUTOFF")
    if isinstance(raw,bytes):
        expected=hashlib.sha256(raw).hexdigest()
        if not isinstance(trust.get("trustedTransportDigest"),str) or not hmac.compare_digest(expected,trust["trustedTransportDigest"]):
            problems.append("TRANSPORT_BYTES_NOT_ATTESTED")
    if problems:
        return {"status":"BLOCKED","failures":sorted(set(problems)),"promotionAuthorized":False,"liveRequestMade":False}
    result=evaluate(response,manifest,season,week,cutoff)
    result["promotionAuthorized"]=False
    result["liveRequestMade"]=False
    return result
