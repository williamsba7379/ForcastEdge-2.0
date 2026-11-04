import copy
import hashlib
import unittest
from scripts.nfl_espn_hardened_mock_boundary import harden
from scripts.nfl_future_history_sync_gate import sha
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_nfl_espn_mock_transport_contract import fixture

def setup():
    response,manifest=fixture()
    response.update(redirectChain=[],tlsVersion="TLSv1.3",certificateValidation="SYSTEM_TRUST_CHAIN_AND_HOSTNAME",
                    transferEncoding="identity",contentEncoding="identity",chunks=[response["raw"]])
    trust={"adapterIdentity":"APPROVED_OFFLINE_TEST_ADAPTER",
           "trustedTransportDigest":hashlib.sha256(response["raw"]).hexdigest(),
           "trustedScheduleDigest":sha({k:v for k,v in manifest.items() if k!="scheduleSha256"}),
           "clockSource":"APPROVED_MONOTONIC_CAPTURE_CLOCK",
           "clockObservedAt":"2026-11-16T02:00:02Z"}
    return response,manifest,trust
def check(change=None):
    response,manifest,trust=setup()
    if change:change(response,manifest,trust)
    return harden(response,manifest,2026,10,"2026-11-18T17:00:00Z",trust)
class HardenedTests(unittest.TestCase):
    def blocked(self,change):
        x=check(change);self.assertEqual(x["status"],"BLOCKED",x)
        self.assertFalse(x["promotionAuthorized"]);self.assertFalse(x["liveRequestMade"])
    def test_success(self):
        x=check();self.assertEqual(x["status"],"OFFLINE_TRANSPORT_VALIDATED",x)
    def test_missing_adapter(self):self.blocked(lambda r,m,t:t.pop("adapterIdentity"))
    def test_fake_adapter(self):self.blocked(lambda r,m,t:t.update(adapterIdentity="UNTRUSTED"))
    def test_missing_transport_digest(self):self.blocked(lambda r,m,t:t.pop("trustedTransportDigest"))
    def test_forged_transport_digest(self):self.blocked(lambda r,m,t:t.update(trustedTransportDigest="f"*64))
    def test_missing_schedule_anchor(self):self.blocked(lambda r,m,t:t.pop("trustedScheduleDigest"))
    def test_schedule_spoof(self):
        def change(r,m,t):
            m["provider"]="FORGED";m["scheduleSha256"]=sha(m["games"])
        self.blocked(change)
    def test_clock_source(self):self.blocked(lambda r,m,t:t.update(clockSource="LOCAL_UNVERIFIED"))
    def test_clock_future(self):self.blocked(lambda r,m,t:t.update(clockObservedAt="2026-11-19T00:00:00Z"))
    def test_clock_before_completion(self):self.blocked(lambda r,m,t:t.update(clockObservedAt="2026-11-16T01:00:00Z"))
    def test_clock_skew(self):self.blocked(lambda r,m,t:t.update(clockObservedAt="2026-11-16T02:00:30Z"))
    def test_redirect_chain(self):self.blocked(lambda r,m,t:r.update(redirectChain=[{"status":302,"location":"https://evil.test"}]))
    def test_tls_version(self):self.blocked(lambda r,m,t:r.update(tlsVersion="TLSv1.0"))
    def test_tls_certificate(self):self.blocked(lambda r,m,t:r.update(certificateValidation="DISABLED"))
    def test_gzip(self):self.blocked(lambda r,m,t:r.update(contentEncoding="gzip"))
    def test_chunked(self):self.blocked(lambda r,m,t:r.update(transferEncoding="chunked"))
    def test_oversize_stream(self):self.blocked(lambda r,m,t:r.update(chunks=[b"x"*2000001]))
    def test_chunk_mismatch(self):self.blocked(lambda r,m,t:r.update(chunks=[b"tampered"]))
    def test_malformed_status(self):self.blocked(lambda r,m,t:r.update(status="200"))
    def test_malformed_content_length(self):self.blocked(lambda r,m,t:r.update(contentLength="100"))
    def test_untrusted_tls_flags(self):self.blocked(lambda r,m,t:r.update(certificateValidation="FLAGS_ONLY"))
if __name__=="__main__":unittest.main()
