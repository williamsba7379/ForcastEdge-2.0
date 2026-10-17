"""Read-only GitHub Actions monitoring. Writes status report, never changes predictions."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

NOW = dt.datetime.now(dt.timezone.utc)
REPO = os.environ["GH_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
WORKFLOWS = [
    ("NFL scoreboard", "forecastedge-scoreboard.yml", 3, 9),
    ("NFL schedule", "forecastedge-schedule.yml", 24, 48),
    ("Weekly prediction draft", "forecastedge-draft.yml", 168, 192),
]

def latest_run(filename):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{filename}/runs?per_page=10"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ForecastEdge-health-monitor",
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response).get("workflow_runs", [])

checks = []
for label, filename, cadence, stale_after in WORKFLOWS:
    entry = {"name": label, "workflow": filename, "cadenceHours": cadence,
             "staleAfterHours": stale_after}
    try:
        runs = latest_run(filename)
        completed = [r for r in runs if r.get("status") == "completed"]
        newest = runs[0] if runs else None
        last_success = next((r for r in completed if r.get("conclusion") == "success"), None)
        entry["latestConclusion"] = newest.get("conclusion") if newest else None
        entry["latestRunUrl"] = newest.get("html_url") if newest else None
        entry["latestRunStatus"] = newest.get("status") if newest else None
        entry["lastSuccessAt"] = last_success.get("created_at") if last_success else None
        if newest and newest.get("status") == "completed" and newest.get("conclusion") not in ("success", "skipped", "neutral"):
            entry["status"] = "failed"
            entry["reason"] = "Most recent workflow run failed."
        elif not last_success:
            entry["status"] = "delayed"
            entry["reason"] = "No successful workflow run found in recent history."
        else:
            timestamp = dt.datetime.fromisoformat(last_success["created_at"].replace("Z", "+00:00"))
            age = (NOW - timestamp).total_seconds() / 3600
            entry["ageHours"] = round(age, 1)
            if age > stale_after:
                entry["status"] = "delayed"
                entry["reason"] = f"Last successful run was {age:.1f} hours ago."
            else:
                entry["status"] = "healthy"
                entry["reason"] = f"Last successful run {age:.1f} hours ago."
    except (urllib.error.URLError, ValueError, KeyError) as exc:
        entry["status"] = "unknown"
        entry["reason"] = f"Could not inspect GitHub workflow: {exc}"
    checks.append(entry)
out = {"checkedAt": NOW.isoformat(), "checks": checks,
       "note": "Workflow run checks, not a guarantee that published content is current."}
path = Path("data/forecastedge-health.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
