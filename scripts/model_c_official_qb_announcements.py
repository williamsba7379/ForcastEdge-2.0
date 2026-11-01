#!/usr/bin/env python3
"""Read-only, allowlisted official QB announcement evidence; never confirms starters."""
import datetime as dt
import json
import re
import urllib.request
from html.parser import HTMLParser

SOURCES = {
    "BAL": ("https://www.baltimoreravens.com/news/lamar-jackson-ravens-bills-set-to-play-2026", "Lamar Jackson", "Buffalo Bills"),
    "BUF": ("https://www.buffalobills.com/news/buffalo-bills-injury-report-vs-ravens-week-8", "Josh Allen", "Baltimore Ravens"),
    "PIT": ("https://www.steelers.com/news/week-8-injury-report-browns-x7058", "Aaron Rodgers", "Cleveland Browns"),
}
class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def classify(team, html):
    """Evidence is contextual and informational, not a production eligibility flag."""
    if team not in SOURCES:
        raise ValueError("Unapproved team")
    parser = Text()
    parser.feed(html)
    visible = " ".join(" ".join(parser.parts).split())
    # Only a date displayed in the article text; no JSON-LD, metadata, or crawl time.
    match = re.search(r"\\b(Oct\\s+\\d{1,2},\\s+2026)\\s+at\\s+\\d{1,2}:\\d{2}\\s+[AP]M\\b", visible)
    date = match.group(1) if match else None
    if not date:
        return {"status": "UNVERIFIED_ARTICLE_DATE", "articleDate": None, "evidence": "NONE"}
    if team == "BAL" and re.search(r"Head Coach Jesse Minter announced Friday that Jackson will play against the Buffalo Bills", visible, re.I):
        evidence = "COACH_ANNOUNCED_AVAILABLE_FOR_MATCHUP"
    else:
        evidence = "DATED_REPORT_NO_DIRECT_QB_STARTER_ANNOUNCEMENT"
    return {"status": "DATED_OFFICIAL_REPORT", "articleDate": date, "evidence": evidence,
            "starterConfirmed": False, "depthChartFreshnessAffected": False}

def main():
    results = {}
    for team, (url, player, opponent) in SOURCES.items():
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ForecastEdge-QB-Validation/1.0"})
            with urllib.request.urlopen(request, timeout=18) as response:
                if response.geturl() != url:
                    raise ValueError("Unexpected redirect")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Page too large")
            results[team] = {"source": url, "subject": player, "opponent": opponent,
                             **classify(team, raw.decode("utf-8", errors="strict"))}
        except (OSError, ValueError, UnicodeError) as exc:
            results[team] = {"source": url, "status": "UNVERIFIED", "reason": type(exc).__name__,
                             "starterConfirmed": False, "depthChartFreshnessAffected": False}
    print(json.dumps({"status": "READ_ONLY_OFFICIAL_QB_ANNOUNCEMENT_DIAGNOSTIC", "teams": results}, indent=2))
if __name__ == "__main__":
    main()
