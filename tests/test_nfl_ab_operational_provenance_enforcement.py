"""Offline operational provenance gates. No GitHub API or live NFL calls."""
import datetime as dt
import hashlib
import unittest
from scripts.nfl_ab_review_provenance_guard import (
    validate_capture_review_chain,validate_artifact_expiry,verify_archive_digest
)
CAPTURE="a"*40
REVIEW="b"*40
RUN={"updated_at":"2026-11-18T16:01:00Z"}
COMMIT={"sha":REVIEW,"commit":{"committer":{"date":"2026-11-18T16:02:00Z"}}}
NOW="2026-11-19T00:00:00Z"
ARCHIVE=b"synthetic zip archive bytes"
ART={"id":99,"name":"nfl-ab-raw-capture","expired":False,
     "workflow_run":{"id":123},"created_at":"2026-11-18T16:01:00Z",
     "expires_at":"2026-12-18T16:01:00Z",
     "digest":"sha256:"+hashlib.sha256(ARCHIVE).hexdigest()}
class OperationalGuardTests(unittest.TestCase):
    def test_commit_lineage(self):
        self.assertTrue(validate_capture_review_chain(RUN,CAPTURE,REVIEW,COMMIT,True))
    def test_reject_unrelated_commit(self):
        with self.assertRaisesRegex(ValueError,"INVALID_COMMIT_LINEAGE"):
            validate_capture_review_chain(RUN,CAPTURE,REVIEW,COMMIT,False)
    def test_reject_early_manifest(self):
        early={"sha":REVIEW,"commit":{"committer":{"date":"2026-11-18T16:00:59Z"}}}
        with self.assertRaisesRegex(ValueError,"REVIEW_NOT_AFTER_CAPTURE"):
            validate_capture_review_chain(RUN,CAPTURE,REVIEW,early,True)
    def test_reject_wrong_review_sha(self):
        with self.assertRaisesRegex(ValueError,"MANIFEST_COMMIT_MISMATCH"):
            validate_capture_review_chain(RUN,CAPTURE,REVIEW,{**COMMIT,"sha":CAPTURE},True)
    def test_artifact_retention_and_id(self):
        self.assertTrue(validate_artifact_expiry(ART,"123",NOW))
    def test_reject_expired(self):
        with self.assertRaises(ValueError):
            validate_artifact_expiry(ART,"123","2026-12-18T16:01:00Z")
    def test_reject_short_retention(self):
        with self.assertRaisesRegex(ValueError,"ARTIFACT_EXPIRED_OR_RETENTION_MISMATCH"):
            validate_artifact_expiry({**ART,"expires_at":"2026-11-25T16:01:00Z"},"123",NOW)
    def test_reject_missing_digest(self):
        with self.assertRaisesRegex(ValueError,"MISSING_ARTIFACT_DIGEST"):
            validate_artifact_expiry({**ART,"digest":None},"123",NOW)
    def test_reject_wrong_artifact_id(self):
        with self.assertRaisesRegex(ValueError,"INVALID_ARTIFACT_ID"):
            validate_artifact_expiry({**ART,"id":0},"123",NOW)
    def test_verify_archive_digest(self):
        self.assertTrue(verify_archive_digest(ARCHIVE,ART))
    def test_reject_archive_tamper(self):
        with self.assertRaisesRegex(ValueError,"ARTIFACT_ARCHIVE_DIGEST_MISMATCH"):
            verify_archive_digest(ARCHIVE+b"x",ART)
if __name__=="__main__":
    unittest.main()
