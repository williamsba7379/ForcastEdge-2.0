"""Isolated, offline OpenSSL RFC3161 research probe. NOT production authorization.

Only local, caller-provided files. No shell, package installation, network, or
changes to the ForecastEdge readiness gate. Requires explicit offline CRL
verification; successful timestamp verification alone is insufficient.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import hashlib


_VERSION = re.compile(r"^OpenSSL 3\.[0-9]+\.[0-9]+(?:[ +].*)?$")


def verify_timestamp(*, openssl, response, evidence, roots, signer, crl,
                     workdir, request=None, timeout=10, production_requested=False,
                     verification_time=None):
    """Return (research_verified, reason, metadata); never production-ready."""
    meta = {"productionReady": False, "evidenceClass": "OFFLINE_CRYPTOGRAPHIC_RESEARCH"}
    if production_requested:
        return False, "PRODUCTION_AUTHORIZATION_FORBIDDEN", meta
    try:
        if not isinstance(workdir, (str, os.PathLike)) or not Path(workdir).is_absolute() or Path(workdir).is_symlink():
            return False, "INVALID_WORKDIR", meta
        root = Path(workdir).resolve(strict=True)
        if not root.is_dir():
            return False, "INVALID_WORKDIR", meta
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 30:
            return False, "INVALID_TIMEOUT", meta
        def local_file(value, limit):
            if not isinstance(value, (str, os.PathLike)):
                raise ValueError("invalid path")
            path = Path(value)
            if not path.is_absolute() or path.is_symlink():
                raise ValueError("path must be absolute and not a symlink")
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise ValueError("outside restricted workdir")
            if not 0 < resolved.stat().st_size <= limit:
                raise ValueError("invalid size")
            return str(resolved)
        # Executable must be explicitly approved, absolute, and not inside the
        # evidence directory; never resolve it from PATH.
        if not isinstance(openssl, str) or not Path(openssl).is_absolute() or Path(openssl).is_symlink():
            return False, "UNAPPROVED_OPENSSL", meta
        exe = Path(openssl).resolve(strict=True)
        if not exe.is_file() or not os.access(exe, os.X_OK) or exe.is_relative_to(root) or str(exe) not in ("/usr/bin/openssl", "/bin/openssl"):
            return False, "UNAPPROVED_OPENSSL", meta
        if Path(openssl).resolve() != exe:
            return False, "UNAPPROVED_OPENSSL", meta
        if not isinstance(verification_time, int) or isinstance(verification_time, bool) or verification_time <= 0:
            return False, "EXPLICIT_VERIFICATION_TIME_REQUIRED", meta
        if request is None:
            return False, "ORIGINAL_REQUEST_REQUIRED_FOR_NONCE_AND_POLICY", meta
        request_file = local_file(request, 2_000_000)
        paths = [local_file(p, limit) for p, limit in (
            (response, 2_000_000), (evidence, 20_000_000),
            (roots, 2_000_000), (signer, 2_000_000), (crl, 2_000_000))]
        env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
        def run(args):
            return subprocess.run([str(exe), *args], shell=False,
                                  cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                                  capture_output=True, timeout=timeout, check=False)
        version = run(["version"])
        if version.returncode != 0 or not _VERSION.match(version.stdout.decode("ascii", "replace").strip()):
            return False, "UNSUPPORTED_OPENSSL_VERSION", meta
        response_file, evidence_file, roots_file, signer_file, crl_file = paths
        # Validate supplied TSA signer certificate against explicit roots and
        # locally supplied CRL. Never rely on network or system CA trust.
        # Reject malformed, incorrectly signed, or wrong-issuer CRLs before
        # certificate-path verification. Never fetch revocation data online.
        crl_check = run(["crl", "-in", crl_file, "-noout", "-verify",
                         "-CAfile", roots_file])
        if crl_check.returncode != 0:
            return False, "CRL_SIGNATURE_REJECTED", meta
        chain = run(["verify", "-CAfile", roots_file, "-CRLfile", crl_file,
                     "-crl_check", "-attime", str(verification_time),
                     "-purpose", "timestampsign", signer_file])
        if chain.returncode != 0:
            return False, "CERTIFICATE_OR_REVOCATION_REJECTED", meta
        # The historical availability of this CRL cannot be established by
        # -attime alone. This remains offline research, never production proof.
        # Verify original request (nonce and policy) AND the evidence imprint.
        # OpenSSL ts -verify has no -CRLfile option. CRL checking above is
        # separate; it does not establish identity of an embedded CMS signer.
        for match_arg, match_file in (("-queryfile", request_file), ("-data", evidence_file)):
            ts = run(["ts", "-verify", "-in", response_file,
                      match_arg, match_file, "-CAfile", roots_file,
                      "-untrusted", signer_file])
            if ts.returncode != 0:
                return False, "TIMESTAMP_VERIFICATION_FAILED", meta
        # Extract CMS signer from the verified RFC3161 response. Compare its
        # DER certificate to the separately CRL-checked signer, byte for byte.
        # Temporary files are isolated within the approved local workdir.
        with tempfile.TemporaryDirectory(prefix="rfc3161-", dir=str(root)) as scratch:
            token = str(Path(scratch) / "token.der")
            extracted = str(Path(scratch) / "embedded-signer.pem")
            if run(["ts", "-reply", "-in", response_file, "-token_out", "-out", token]).returncode != 0:
                return False, "TIMESTAMP_SIGNER_EXTRACTION_FAILED", meta
            cms = run(["cms", "-verify", "-inform", "DER", "-in", token,
                       "-CAfile", roots_file, "-signer", extracted,
                       "-out", str(Path(scratch) / "verified-content")])
            if cms.returncode != 0 or not Path(extracted).is_file():
                return False, "TIMESTAMP_CMS_SIGNER_REJECTED", meta
            def certificate_der(path):
                cert = run(["x509", "-in", path, "-outform", "DER"])
                return cert.stdout if cert.returncode == 0 else None
            expected = certificate_der(signer_file)
            actual = certificate_der(extracted)
            if not expected or not actual or hashlib.sha256(expected).digest() != hashlib.sha256(actual).digest():
                return False, "TIMESTAMP_SIGNER_IDENTITY_MISMATCH", meta
        return True, "OFFLINE_OPENSSL_VERIFIED_RESEARCH_ONLY", meta
    except (OSError, ValueError, subprocess.TimeoutExpired, UnicodeError):
        return False, "OFFLINE_EXECUTION_OR_INPUT_FAILURE", meta
