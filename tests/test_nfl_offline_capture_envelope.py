"""Synthetic-only capture envelope tests; no HTTP or real NFL records."""
import datetime as dt
import hashlib
import unittest
from nfl_offline_capture_envelope import SOURCE, capture_envelope

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 8, 22, 0, tzinfo=UTC)
RAW = b'{"events":[{"id":"123"}]}'

def fixture(**overrides):
    args = dict(game_id="123", source=SOURCE, response_bytes=RAW,
                request_started_at=START, clock=lambda: START + dt.timedelta(seconds=2))
    args.update(overrides)
    return capture_envelope(**args)

class CaptureEnvelopeTests(unittest.TestCase):
    def test_injected_clock_controls_capture_time(self):
        envelope = fixture(clock=lambda: START + dt.timedelta(seconds=7))
        self.assertEqual(envelope["capturedAt"], "2026-11-08T22:00:07Z")

    def test_caller_cannot_override_capture_time(self):
        with self.assertRaises(TypeError):
            fixture(capturedAt="2020-01-01T00:00:00Z")
        self.assertEqual(fixture()["capturedAt"], "2026-11-08T22:00:02Z")

    def test_raw_response_and_source_identity_preserved(self):
        envelope = fixture()
        self.assertEqual(envelope["rawResponse"].encode("utf-8"), RAW)
        self.assertEqual(envelope["source"], SOURCE)
        self.assertEqual(envelope["contentSha256"], hashlib.sha256(RAW).hexdigest())

    def test_invalid_and_stale_capture_fail_closed(self):
        for overrides in (
            {"source": "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"},
            {"response_bytes": b""},
            {"clock": lambda: START - dt.timedelta(seconds=1)},
            {"clock": lambda: START + dt.timedelta(minutes=6)},
            {"clock": lambda: dt.datetime(2026, 11, 8, 22, 0)},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    fixture(**overrides)

    def test_timestamp_convention_is_consistent(self):
        envelope = fixture()
        self.assertEqual(envelope["capturedAt"], envelope["retrievedAt"])
        self.assertLessEqual(envelope["requestStartedAt"], envelope["capturedAt"])
        self.assertEqual(envelope["observationType"], "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION")

if __name__ == "__main__":
    unittest.main()
