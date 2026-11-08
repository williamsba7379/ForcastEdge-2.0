"""Eight offline OpenSSL probe regression tests; never touch production.

Test-only CA and TSA keys are generated inside a temporary directory, never
committed. Tests require a locally installed OpenSSL 3.x; no downloads.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nfl_offline_rfc3161_openssl_probe import verify_timestamp


class OfflineOpenSSLProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = shutil.which("openssl")
        if cls.exe is None:
            raise unittest.SkipTest("Local OpenSSL unavailable; hosted validation required")
        cls.exe = str(Path(cls.exe).resolve())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.evidence = self.root / "evidence.bin"
        self.evidence.write_bytes(b"offline test evidence 401123456")
        self.roots = self.root / "root.pem"
        self.signer = self.root / "tsa.pem"
        self.crl = self.root / "root.crl"
        self.response = self.root / "stamp.tsr"
        self.kw = dict(openssl=self.exe, response=str(self.response),
                       evidence=str(self.evidence), roots=str(self.roots),
                       signer=str(self.signer), crl=str(self.crl),
                       workdir=str(self.root))
        self._make_fixture()

    def cmd(self, *args):
        subprocess.run([self.exe, *map(str, args)], cwd=self.root,
                       stdin=subprocess.DEVNULL, capture_output=True,
                       check=True, timeout=10)

    def _make_fixture(self):
        # Disposable CA, signed TSA certificate and an empty, signed CRL.
        db = self.root / "db"
        db.mkdir()
        (db / "newcerts").mkdir()
        (db / "index.txt").write_text("")
        (db / "serial").write_text("1000\n")
        (db / "crlnumber").write_text("1000\n")
        config = self.root / "ca.cnf"
        config.write_text(f"""[ca]
default_ca = local_ca
[local_ca]
database = {db}/index.txt
new_certs_dir = {db}/newcerts
certificate = {self.roots}
private_key = {self.root}/root.key
serial = {db}/serial
crlnumber = {db}/crlnumber
default_md = sha256
default_days = 2
default_crl_days = 2
policy = permissive
x509_extensions = tsa_ext
[permissive]
commonName = supplied
[tsa_ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,timeStamping
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
""")
        self.cmd("req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", self.root / "root.key", "-out", self.roots,
                 "-days", "2", "-subj", "/CN=Offline Test CA",
                 "-addext", "basicConstraints=critical,CA:true",
                 "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        self.cmd("req", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", self.root / "tsa.key", "-out", self.root / "tsa.csr",
                 "-subj", "/CN=Offline Test TSA")
        self.cmd("ca", "-batch", "-config", config, "-in", self.root / "tsa.csr",
                 "-out", self.signer, "-notext")
        self.cmd("ca", "-gencrl", "-config", config, "-out", self.crl)
        request = self.root / "stamp.tsq"
        self.cmd("ts", "-query", "-data", self.evidence, "-sha256",
                 "-cert", "-out", request)
        self.cmd("ts", "-reply", "-queryfile", request,
                 "-signer", self.signer, "-inkey", self.root / "tsa.key",
                 "-chain", self.roots, "-tspolicy", "1.2.3.4.5",
                 "-out", self.response)

    def result(self, **changes):
        return verify_timestamp(**dict(self.kw, **changes))

    def deny(self, **changes):
        ok, reason, meta = self.result(**changes)
        self.assertFalse(ok, reason)
        self.assertFalse(meta["productionReady"])
        return reason

    def test_valid_locally_signed_rfc3161_evidence(self):
        ok, reason, meta = self.result()
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "OFFLINE_OPENSSL_VERIFIED_RESEARCH_ONLY")
        self.assertFalse(meta["productionReady"])

    def test_tampered_signature(self):
        data = bytearray(self.response.read_bytes())
        data[-10] ^= 1
        self.response.write_bytes(data)
        self.deny()

    def test_changed_evidence(self):
        self.evidence.write_bytes(b"altered offline evidence")
        self.deny()

    def test_untrusted_tsa(self):
        other = self.root / "other-root.pem"
        self.cmd("req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", self.root / "other.key", "-out", other,
                 "-days", "2", "-subj", "/CN=Untrusted CA")
        self.deny(roots=str(other))

    def test_invalid_timestamp_signing_purpose(self):
        other = self.root / "wrong-purpose.pem"
        # A valid CA certificate cannot serve as a timestamp-only TSA signer.
        other.write_bytes(self.roots.read_bytes())
        self.deny(signer=str(other))

    def test_missing_or_invalid_revocation_evidence(self):
        self.deny(crl=str(self.root / "missing.crl"))
        self.crl.write_text("invalid crl")
        self.deny()

    def test_malformed_input_or_execution_failure(self):
        self.response.write_bytes(b"not an RFC3161 token")
        self.deny()
        self.assertEqual(self.deny(openssl="/nonexistent/openssl"), "OFFLINE_EXECUTION_OR_INPUT_FAILURE")

    def test_production_authorization_rejected(self):
        self.assertEqual(self.deny(production_requested=True),
                         "PRODUCTION_AUTHORIZATION_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
