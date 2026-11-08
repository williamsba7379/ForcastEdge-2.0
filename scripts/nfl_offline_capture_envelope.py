"""Offline-only evidence envelope for synthetic HTTP response fixtures.

No HTTP client, socket, file writes, or production integration. An injected
clock models a collector-owned timestamp; it is NOT an independently trusted
timestamp authority or proof that a network request happened.
"""
import datetime as dt
import hashlib
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def _utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UNTRUSTED_CAPTURE_CLOCK")
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def capture_envelope(*, game_id, source, response_bytes, clock, request_started_at, max_age_seconds=300):
    """Build a defensive fixture envelope; caller cannot inject capturedAt."""
    if not isinstance(game_id, str) or not game_id.isdecimal():
        raise ValueError("INVALID_GAME_ID")
    if source != SOURCE:
        raise ValueError("INVALID_SOURCE")
    parsed = urlsplit(source)
    if parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("INVALID_SOURCE")
    if not isinstance(response_bytes, bytes) or not 0 < len(response_bytes) <= MAX_BYTES:
        raise ValueError("INVALID_RESPONSE_BYTES")
    if not callable(clock):
        raise ValueError("MISSING_CLOCK")
    captured = dt.datetime.fromisoformat(_utc(clock()).replace("Z", "+00:00"))
    started = dt.datetime.fromisoformat(_utc(request_started_at).replace("Z", "+00:00"))
    age = (captured - started).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise ValueError("STALE_OR_FUTURE_CAPTURE")
    return {
        "schemaVersion": 1,
        "gameId": game_id,
        "source": source,
        "requestStartedAt": _utc(started),
        "capturedAt": _utc(captured),
        "retrievedAt": _utc(captured),
        "observationType": "OFFLINE_FIXTURE_NOT_LIVE_OBSERVATION",
        "contentSha256": hashlib.sha256(response_bytes).hexdigest(),
        "rawResponse": response_bytes.decode("utf-8"),
    }
