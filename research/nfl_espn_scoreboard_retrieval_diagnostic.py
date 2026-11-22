#!/usr/bin/env python3
"""Manual-only, read-only ESPN NFL historical scoreboard diagnostic.

No repository writes, no model imports, no historical mutations.
Output to stdout; GitHub Actions may retain stdout logs.
"""
import datetime as dt
import hashlib
import json
import sys
import urllib.error
import urllib.request

YEAR = 2026
WEEKS = {8: 14, 9: 15}
TIMEOUT = 12
MAX_BYTES = 3_000_000

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ForecastEdge-Research-Diagnostic/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return {"url": url, "httpStatus": response.status, "error": "RESPONSE_TOO_LARGE"}
            result = {"url": url, "httpStatus": response.status, "bytes": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest()}
    except urllib.error.HTTPError as e:
        return {"url": url, "httpStatus": e.code, "error": "HTTP_ERROR"}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"url": url, "httpStatus": None, "error": type(e).__name__}
    try:
        result["payload"] = json.loads(raw)
    except (UnicodeError, ValueError):
        result["error"] = "NON_JSON_RESPONSE"
    return result

def events(payload):
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("events"), list):
        return payload["events"]
    for key in ("sbData", "scoreboard", "page", "content"):
        item = payload.get(key)
        if isinstance(item, dict):
            found = events(item)
            if found is not None:
                return found
    return None

def normalize(event):
    competitions = event.get("competitions") or []
    competitors = competitions[0].get("competitors", []) if competitions and isinstance(competitions[0], dict) else []
    teams = {}
    for c in competitors:
        side = c.get("homeAway")
        if side in ("home", "away"):
            teams[side] = {"name": c.get("team", {}).get("displayName"),
                           "score": c.get("score")}
    status = event.get("status", {}).get("type", {})
    raw_id = event.get("id")
    return {"espnEventId": str(raw_id) if raw_id is not None else "", "kickoffUTC": event.get("date"),
            "home": teams.get("home"), "away": teams.get("away"),
            "completed": status.get("completed"), "state": status.get("state")}

def valid_score(value):
    return isinstance(value, (str, int)) and str(value).isdigit() and int(value) >= 0

def valid_kickoff(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0)
    except ValueError:
        return False

def main():
    report = {"mode": "READ_ONLY_RESEARCH", "season": YEAR, "seasonType": 2,
              "published": False, "weeks": [], "status": "BLOCKED"}
    complete = True
    for week, expected in WEEKS.items():
        urls = {
            "site": f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={YEAR}&seasontype=2&week={week}&limit=100",
            "cdn": f"https://cdn.espn.com/core/nfl/scoreboard?xhr=1&year={YEAR}&seasontype=2&week={week}",
        }
        entry = {"week": week, "expectedGames": expected, "sources": {}}
        successful = []
        for name, url in urls.items():
            response = fetch(url)
            payload = response.pop("payload", None)
            games = events(payload)
            if games is not None:
                response["eventCount"] = len(games)
                try:
                    response["games"] = [normalize(g) for g in games]
                except (TypeError, ValueError, AttributeError, KeyError) as e:
                    response["games"] = []
                    response["error"] = "MALFORMED_EVENT_DATA_" + type(e).__name__
                ids = [g["espnEventId"] for g in response["games"]]
                response["valid"] = (len(games) == expected and len(response["games"]) == expected and len(set(ids)) == expected
                    and all(g["espnEventId"].isdigit() and valid_kickoff(g["kickoffUTC"]) and g["completed"] is True
                            and g["state"] == "post" and g["home"] and g["away"]
                            and g["home"]["name"] and g["away"]["name"]
                            and valid_score(g["home"]["score"]) and valid_score(g["away"]["score"])
                            for g in response["games"]))
                if response["valid"]:
                    successful.append((name, response["games"]))
            else:
                response["valid"] = False
                response["error"] = response.get("error", "NO_EVENTS_IN_PAYLOAD")
            entry["sources"][name] = response
        if len(successful) == 2:
            a = {g["espnEventId"]: g for g in successful[0][1]}
            b = {g["espnEventId"]: g for g in successful[1][1]}
            entry["sourceAgreement"] = a == b
        else:
            entry["sourceAgreement"] = False
        entry["status"] = "PASS_TWO_SOURCE_AGREEMENT" if entry["sourceAgreement"] else "BLOCKED_INCOMPLETE_OR_CONFLICT"
        complete = complete and entry["sourceAgreement"]
        report["weeks"].append(entry)
    report["status"] = "RESEARCH_SOURCE_CHECK_PASS_NOT_ARCHIVE_APPROVAL" if complete else "BLOCKED"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if complete else 2

if __name__ == "__main__":
    sys.exit(main())
