"""Read-only Model C/C-QB delivery monitor. Consumes captured GitHub job and saved-file evidence."""
import datetime as dt
import hashlib
import json
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REQUIRED = ("Generate independent Model C review draft",
            "Generate separate Model C-QB experimental shadow",
            "Validate generated Model C review draft", "Commit draft only")

def _time(value):
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone required")
    return t.astimezone(dt.timezone.utc)

def evaluate(*, target_wednesday, runs, artifacts, deadline_minutes=30):
    """Fail closed. artifacts maps C/C-QB to {content: raw saved bytes as text, sha256, committedAt}.
    The caller must supply repository-read evidence, never uncommitted workspace output.
    """
    day = dt.date.fromisoformat(target_wednesday)
    if day.weekday() != 2:
        raise ValueError("target_wednesday must be Wednesday")
    cutoff = dt.datetime.combine(day, dt.time(11), ET).astimezone(dt.timezone.utc)
    deadline = cutoff + dt.timedelta(minutes=deadline_minutes)
    early, eligible, late = [], [], []
    for run in runs:
        if run.get("event") != "schedule":
            continue
        try:
            start = _time(run["startedAt"])
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if start < cutoff:
            early.append(run)
        elif start <= deadline:
            eligible.append(run)
        else:
            late.append(run)
    if not eligible:
        return {"status":"FAIL", "reason":"LATE_DELIVERY_ATTEMPT" if late else "MISSING_REQUIRED_DELIVERY", "earlyChecks":len(early), "lateChecks":len(late)}
    # A valid delivery requires one fully successful scheduled run; later runs cannot mask failed attempts.
    reasons = []
    for run in eligible:
        if run.get("timeGateRun") is not True:
            reasons.append("SKIPPED_REQUIRED_DELIVERY")
            continue
        if run.get("conclusion") != "success":
            reasons.append("FAILED_REQUIRED_JOB")
            continue
        if any(run.get("steps", {}).get(step) != "success" for step in REQUIRED):
            reasons.append("SKIPPED_OR_FAILED_REQUIRED_STEP")
            continue
        missing = []
        for model in ("C", "C-QB"):
            item = artifacts.get(model)
            if not isinstance(item, dict):
                missing.append(model + ":MISSING_SAVED_ARTIFACT")
                continue
            try:
                raw = item["content"]
                payload = json.loads(raw)
                valid_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest() == item["sha256"]
                committed = _time(item["committedAt"])
                valid = (valid_hash and payload.get("season") == day.year
                         and payload.get("week") == run.get("week")
                         and cutoff <= committed <= deadline
                         and payload.get("generatedAt") is not None
                         and _time(payload["generatedAt"]) <= committed
                         and payload.get("status") in ("AUTOMATED_REVIEW_ONLY","EXPERIMENTAL_SHADOW_ONLY"))
                if not valid:
                    missing.append(model + ":INVALID_PROVENANCE")
            except (KeyError, ValueError, TypeError, AttributeError, UnicodeError):
                missing.append(model + ":INVALID_PROVENANCE")
        if not missing:
            return {"status":"PASS", "reason":"SAVED_MODEL_DRAFTS_VERIFIED", "earlyChecks":len(early)}
        reasons.extend(missing)
    return {"status":"FAIL", "reason":";".join(sorted(set(reasons))), "earlyChecks":len(early)}

if __name__ == "__main__":
    import sys
    request = json.load(sys.stdin)
    result = evaluate(**request)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)
