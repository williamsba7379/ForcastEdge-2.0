"""Research-only NFL final evidence intake. No network calls, disk writes, or backfills.

The caller supplies freshly retrieved raw bytes, a trusted retrieval timestamp and
a pre-existing kickoff. Capture only the first *observed* final, not the game's
actual finalization time. Persist externally only in an append-only store after
independent review. A prior record is never overwritten.
"""
import datetime as dt
import hashlib
import json
from urllib.parse import urlsplit

HOST = "site.api.espn.com"

def utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(dt.timezone.utc)

def iso(value):
    return utc(value).isoformat().replace("+00:00", "Z")

def capture(*, game_id, kickoff_at, source, raw_response, retrieved_at,
            previous=None, now=None):
    """Return immutable-intent evidence or (None, reason). Never writes files."""
    try:
        if previous is not None:
            return None, "EXISTING_FIRST_OBSERVATION_IMMUTABLE"
        if not isinstance(game_id, str) or not game_id.isdecimal():
            return None, "INVALID_GAME_ID"
        url = urlsplit(source)
        if url.scheme != "https" or url.hostname != HOST or url.username or url.password or url.port:
            return None, "UNTRUSTED_SOURCE"
        if not url.path.endswith("/scoreboard"):
            return None, "UNEXPECTED_ENDPOINT"
        if not isinstance(raw_response, bytes) or not raw_response or len(raw_response) > 2_000_000:
            return None, "INVALID_RAW_RESPONSE"
        retrieved = utc(retrieved_at)
        observed = utc(now)
        kickoff = utc(kickoff_at)
        if retrieved > observed or (observed - retrieved) > dt.timedelta(minutes=5):
            return None, "STALE_OR_FUTURE_RETRIEVAL"
        if observed <= kickoff:
            return None, "BEFORE_KICKOFF"
        payload = json.loads(raw_response)
        events = payload.get("events")
        if not isinstance(events, list):
            return None, "MISSING_EVENTS"
        matches = [event for event in events if str(event.get("id")) == game_id]
        if len(matches) != 1:
            return None, "GAME_ID_NOT_UNIQUE"
        event = matches[0]
        if event.get("status", {}).get("type", {}).get("completed") is not True:
            return None, "NOT_FINAL"
        competitions = event.get("competitions")
        if not isinstance(competitions, list) or len(competitions) != 1:
            return None, "INVALID_COMPETITION"
        teams = competitions[0].get("competitors")
        if not isinstance(teams, list) or len(teams) != 2:
            return None, "INVALID_COMPETITORS"
        if {t.get("homeAway") for t in teams} != {"home", "away"}:
            return None, "INVALID_COMPETITORS"
        for team in teams:
            score = team.get("score")
            if not isinstance(score, str) or not score.isdecimal():
                return None, "MISSING_FINAL_SCORE"
        evidence = {
            "gameId": game_id, "source": source, "kickoffAt": iso(kickoff),
            "observedFinalAt": iso(retrieved), "retrievedAt": iso(retrieved),
            "contentSha256": hashlib.sha256(raw_response).hexdigest(),
            "rawResponse": raw_response.decode("utf-8"),
            "observationType": "FIRST_SEEN_FINAL_NOT_OFFICIAL_FINALIZATION",
        }
        return evidence, "FIRST_FINAL_OBSERVED"
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "UNVERIFIABLE_RESPONSE"
