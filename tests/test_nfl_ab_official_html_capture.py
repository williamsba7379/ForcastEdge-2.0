"""Offline integrity tests for official NFL HTML source, no backfill."""
import base64
import hashlib
import unittest
from scripts.nfl_ab_official_html_capture import verify_reviewed_normalization,official_url

CUTOFF="2026-11-04T16:00:00Z"
RAW=b'<html><body>Jaguars at Ravens, Thursday, November 5th, 8:15 PM</body></html>'
def capture():
    return {"kind":"RAW_NFL_HTML_CAPTURE","sourceUrl":official_url(2026,9),
            "retrievedAt":"2026-11-04T15:58:00Z",
            "responseSha256":hashlib.sha256(RAW).hexdigest(),
            "rawBodyBase64":base64.b64encode(RAW).decode("ascii")}
def games():
    return [{"date":"2026-11-06T01:15:00Z","home":"Baltimore Ravens",
             "away":"Jacksonville Jaguars",
             "sourceSnippet":"Jaguars at Ravens, Thursday, November 5th, 8:15 PM"}]
class OfficialHtmlTests(unittest.TestCase):
    def test_verified_reviewed_manifest(self):
        result=verify_reviewed_normalization(capture(),games(),CUTOFF)
        self.assertFalse(result["publishable"])
        self.assertEqual(len(result["games"]),1)
        self.assertEqual(result["responseSha256"],hashlib.sha256(RAW).hexdigest())
    def test_late_capture(self):
        c=capture();c["retrievedAt"]="2026-11-04T16:00:01Z"
        with self.assertRaisesRegex(ValueError,"OFFICIAL_RESPONSE_AFTER_CUTOFF"):
            verify_reviewed_normalization(c,games(),CUTOFF)
    def test_hash_change(self):
        c=capture();c["responseSha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"OFFICIAL_RAW_HASH_MISMATCH"):
            verify_reviewed_normalization(c,games(),CUTOFF)
    def test_missing_source_snippet(self):
        g=games();g[0]["sourceSnippet"]="Not present in raw HTML"
        with self.assertRaisesRegex(ValueError,"REVIEW_SNIPPET_NOT_IN_RAW_HTML"):
            verify_reviewed_normalization(capture(),g,CUTOFF)
    def test_duplicate_game(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_REVIEWED_GAME"):
            verify_reviewed_normalization(capture(),games()*2,CUTOFF)
    def test_wrong_host(self):
        c=capture();c["sourceUrl"]="https://www.nfl.com.evil.test/schedules/2026/by-week/week-9"
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_OFFICIAL_URL"):
            verify_reviewed_normalization(c,games(),CUTOFF)
    def test_empty_review(self):
        with self.assertRaisesRegex(ValueError,"MISSING_REVIEWED_GAMES"):
            verify_reviewed_normalization(capture(),[],CUTOFF)
if __name__=="__main__":
    unittest.main()
