"""Offline-only, fail-closed evidence gate. No network or production integration."""
import datetime as dt
import hashlib
import json
import threading
from urllib.parse import urlsplit

def _time(value):
    t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None: raise ValueError("timezone required")
    return t.astimezone(dt.timezone.utc)

class MemoryAppendOnlyEvidence:
    """Test double only; not durable storage or a production collector."""
    def __init__(self):
        self._records={}
        self._lock=threading.Lock()
    def submit(self, record, schedule):
        try:
            if not isinstance(record,dict) or not isinstance(schedule,dict):
                return False,"INVALID_INPUT"
            gid=record["gameId"]
            if not isinstance(gid,str) or not gid.isdecimal() or gid!=schedule["gameId"]:
                return False,"GAME_ID_MISMATCH"
            raw=record["rawResponse"]
            if not isinstance(raw,str) or hashlib.sha256(raw.encode("utf-8")).hexdigest()!=record["contentSha256"]:
                return False,"CONTENT_HASH_MISMATCH"
            u=urlsplit(record["source"])
            if (u.scheme,u.hostname,u.path)!=("https","site.api.espn.com","/apis/site/v2/sports/football/nfl/scoreboard") or u.username or u.password or u.port:
                return False,"INVALID_SOURCE"
            kickoff=_time(schedule["kickoffAt"])
            if _time(record["kickoffAt"])!=kickoff:
                return False,"KICKOFF_MISMATCH"
            observed=_time(record["observedFinalAt"])
            retrieved=_time(record["retrievedAt"])
            if not (kickoff<observed<=retrieved):
                return False,"INCONSISTENT_TIMESTAMPS"
            if (retrieved-observed)>dt.timedelta(minutes=5):
                return False,"OBSERVATION_DELAY_UNVERIFIED"
            payload=json.loads(raw)
            matches=[e for e in payload["events"] if str(e.get("id"))==gid]
            if len(matches)!=1: return False,"GAME_ID_NOT_UNIQUE"
            event=matches[0]
            if not isinstance(event,dict): return False,"INVALID_EVENT"
            if int(event["season"]["year"])!=int(schedule["season"]) or int(event["week"]["number"])!=int(schedule["week"]):
                return False,"SEASON_WEEK_MISMATCH"
            if _time(event["date"])!=kickoff:
                return False,"EVENT_KICKOFF_MISMATCH"
            if event["status"]["type"]["completed"] is not True:
                return False,"NOT_FINAL"
            comps=event["competitions"]
            if len(comps)!=1: return False,"INVALID_COMPETITION"
            teams=comps[0]["competitors"]
            if len(teams)!=2 or {t["homeAway"] for t in teams}!={"home","away"}:
                return False,"INVALID_COMPETITORS"
            actual={t["homeAway"]:str(t["team"]["id"]) for t in teams}
            if actual!={"home":str(schedule["homeTeamId"]),"away":str(schedule["awayTeamId"])}:
                return False,"TEAM_MISMATCH"
            if any(not isinstance(t.get("score"),str) or not t["score"].isdecimal() for t in teams):
                return False,"INVALID_SCORE"
            with self._lock:
                if gid in self._records:
                    return False,"EXISTING_FIRST_OBSERVATION_IMMUTABLE"
                # Deep-copy through JSON, so caller mutation cannot change stored evidence.
                self._records[gid]=json.loads(json.dumps(record))
            return True,"FIRST_FINAL_OBSERVED"
        except (KeyError,ValueError,TypeError,AttributeError,IndexError,OverflowError,UnicodeError):
            return False,"UNVERIFIABLE_EVIDENCE"
    def get(self,gid):
        with self._lock:
            return json.loads(json.dumps(self._records[gid])) if gid in self._records else None
