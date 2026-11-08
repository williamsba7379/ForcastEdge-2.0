"""Eight offline OpenSSL probe regression tests; never touch production.

Test-only CA and TSA keys are generated inside a temporary directory, never
committed. Tests require a locally installed OpenSSL 3.x; no downloads.
"""
from pathlib import Path
import time
import shutil
import subprocess
import tempfile
import unittest

from nfl_offline_rfc3161_openssl_probe import verify_timestamp


class OfflineOpenSSLProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = shutil.which("openssl")
        if cls.exe is None:
            raise RuntimeError("OpenSSL 3 required; missing executable is a test failure")
        cls.exe = str(Path(cls.exe).resolve())
        version = subprocess.run([cls.exe, "version"], capture_output=True, text=True, timeout=10, check=True).stdout
        if not version.startswith("OpenSSL 3."):
            raise RuntimeError("OpenSSL 3 required; unsupported version")

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
        self.request = self.root / "stamp.tsq"
        self.kw = dict(openssl=self.exe, response=str(self.response),
                       evidence=str(self.evidence), roots=str(self.roots),
                       signer=str(self.signer), crl=str(self.crl),
                       workdir=str(self.root), request=str(self.request),
                       verification_time=int(time.time()))
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
        request = self.request
        self.cmd("ts", "-query", "-data", self.evidence, "-sha256",
                 "-cert", "-out", request)
        tsa_config = self.root / "tsa.cnf"
        tsa_config.write_text("[tsa]\ndefault_tsa = local_tsa\n[local_tsa]\n"
                              "serial = " + str(self.root / "tsa-serial") + "\n"
                              "crypto_device = builtin\nsigner_digest = sha256\n"
                              "default_policy = 1.2.3.4.5\ndigests = sha256\n"
                              "accuracy = secs:1\nordering = yes\n")
        (self.root / "tsa-serial").write_text("01\n")
        self.cmd("ts", "-reply", "-config", tsa_config, "-section", "local_tsa",
                 "-queryfile", request, "-signer", self.signer,
                 "-inkey", self.root / "tsa.key", "-chain", self.roots,
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
        # Walk the DER RFC3161 response -> ContentInfo -> SignedData ->
        # signerInfos -> SignerInfo, rather than matching arbitrary bytes.
        def tlv(pos):
            if pos >= len(data):
                raise ValueError("truncated DER")
            tag = data[pos]
            length_octet = data[pos + 1]
            if length_octet < 128:
                length, header = length_octet, 2
            else:
                n = length_octet & 127
                if not 1 <= n <= 4:
                    raise ValueError("unsupported DER length")
                length = int.from_bytes(data[pos + 2:pos + 2 + n], "big")
                header = 2 + n
            body = pos + header
            end = body + length
            if end > len(data):
                raise ValueError("truncated DER body")
            return tag, body, end

        def children(pos, expected):
            tag, body, end = tlv(pos)
            if tag != expected:
                raise ValueError("unexpected ASN.1 tag")
            result = []
            while body < end:
                result.append(body)
                body = tlv(body)[2]
            if body != end:
                raise ValueError("invalid DER structure")
            return result

        response_parts = children(0, 0x30)
        self.assertEqual(tlv(0)[2], len(data))
        self.assertEqual(len(response_parts), 2)
        content_info = children(response_parts[1], 0x30)
        self.assertEqual(bytes(data[tlv(content_info[0])[1]:tlv(content_info[0])[2]]),
                         bytes.fromhex("2a864886f70d010702"))  # signedData OID
        signed_data = children(children(content_info[1], 0xa0)[0], 0x30)
        signer_sets = [p for p in signed_data if tlv(p)[0] == 0x31]
        self.assertEqual(len(signer_sets), 1)
        signer_infos = children(signer_sets[0], 0x31)
        self.assertEqual(len(signer_infos), 1)
        signer_fields = children(signer_infos[0], 0x30)
        # Signature is the OCTET STRING immediately after signatureAlgorithm.
        algorithms = [i for i, p in enumerate(signer_fields) if tlv(p)[0] == 0x30]
        self.assertGreaterEqual(len(algorithms), 2)
        signature_index = algorithms[-1] + 1
        self.assertLess(signature_index, len(signer_fields))
        signature_tag, signature_body, signature_end = tlv(signer_fields[signature_index])
        self.assertEqual(signature_tag, 0x04)
        self.assertEqual(signature_end - signature_body, 256)
        data[signature_body + 128] ^= 1
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
        self.cmd("req", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", self.root / "wrong.key", "-out", self.root / "wrong.csr",
                 "-subj", "/CN=Wrong Purpose TSA")
        wrong_config = self.root / "wrong.cnf"
        config = (self.root / "ca.cnf").read_text()
        wrong_config.write_text(config.replace("extendedKeyUsage = critical,timeStamping",
                                               "extendedKeyUsage = critical,serverAuth"))
        self.cmd("ca", "-batch", "-config", wrong_config, "-in",
                 self.root / "wrong.csr", "-out", other, "-notext")
        # OpenSSL should refuse issuance by a signer without timeStamping EKU.
        # If issuance unexpectedly succeeds, the probe must reject that token.
        wrong_response = self.root / "wrong-purpose.tsr"
        issued = subprocess.run([self.exe, "ts", "-reply", "-config",
                                 str(self.root / "tsa.cnf"), "-section", "local_tsa",
                                 "-queryfile", str(self.request), "-signer", str(other),
                                 "-inkey", str(self.root / "wrong.key"),
                                 "-chain", str(self.roots), "-out", str(wrong_response)],
                                cwd=self.root, capture_output=True, timeout=10)
        if issued.returncode == 0:
            self.assertEqual(self.deny(signer=str(other), response=str(wrong_response)),
                             "CERTIFICATE_OR_REVOCATION_REJECTED")
        else:
            self.assertFalse(wrong_response.exists(), "Unexpected rejected-response artifact")
            self.assertIn(b"invalid", issued.stderr.lower() + issued.stdout.lower(),
                          "Wrong-EKU issuance must fail for an identified reason")

    def test_missing_or_invalid_revocation_evidence(self):
        self.deny(crl=str(self.root / "missing.crl"))
        self.crl.write_text("invalid crl")
        self.deny()

    def test_malformed_input_or_execution_failure(self):
        self.response.write_bytes(b"not an RFC3161 token")
        self.deny()
        self.assertEqual(self.deny(openssl="relative/openssl"), "UNAPPROVED_OPENSSL")
        self.assertEqual(self.deny(request=None),
                         "ORIGINAL_REQUEST_REQUIRED_FOR_NONCE_AND_POLICY")
        self.assertEqual(self.deny(verification_time=None),
                         "EXPLICIT_VERIFICATION_TIME_REQUIRED")

    def test_production_authorization_rejected(self):
        self.assertEqual(self.deny(production_requested=True),
                         "PRODUCTION_AUTHORIZATION_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
