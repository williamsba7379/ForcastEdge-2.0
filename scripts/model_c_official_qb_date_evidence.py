#!/usr/bin/env python3
"""Read-only, bounded depth-chart-specific date evidence; never grants eligibility."""
import json
import re
import urllib.request
from html.parser import HTMLParser

SOURCES = {
    "BAL": "https://www.baltimoreravens.com/team/depth-chart",
    "BUF": "https://www.buffalobills.com/team/depth-chart",
    "PIT": "https://www.steelers.com/team/depth-chart/",
}
DATE = r"(?:\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})"
EXPLICIT = re.compile(r"\b(?:depth\s*chart\s+)?(?:updated|last\s+updated|as\s+of)\s*(?:as\s+of|:|-)?\s*(" + DATE + r")\b", re.I)

class VisibleText(HTMLParser):
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

def evidence(html):
    """Only explicitly labeled dates in a small visible depth-chart heading region.
    Never infer a date from page metadata, footer, or unrelated news."""
    parser = VisibleText()
    parser.feed(html)
    visible = " ".join(" ".join(parser.parts).split())
    heading = re.search(r"\bdepth\s+chart\b", visible, re.I)
    if not heading:
        return {"status": "NO_DEPTH_CHART_HEADING", "dates": []}
    # Only the first 450 visible characters following the heading; not a full-page date scan.
    region = visible[heading.end():heading.end() + 450]
    region = re.split(r"\b(?:Offense|Defense|Special Teams|Latest News|Related Articles)\b", region, maxsplit=1, flags=re.I)[0]
    dates = list(dict.fromkeys(m.group(1) for m in EXPLICIT.finditer(region)))
    return {"status": "EXPLICIT_HEADING_DATE" if len(dates) == 1 else "NO_UNAMBIGUOUS_HEADING_DATE", "dates": dates[:2]}

def main():
    results = {}
    for team, url in SOURCES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ForecastEdge-QB-Validation/1.0"})
            with urllib.request.urlopen(req, timeout=18) as response:
                if response.geturl() != url:
                    raise ValueError("Unexpected redirect")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Page too large")
            results[team] = evidence(raw.decode("utf-8", errors="strict"))
        except (OSError, ValueError, UnicodeError) as exc:
            results[team] = {"status": "UNVERIFIED", "reason": type(exc).__name__, "dates": []}
    print(json.dumps({"status": "READ_ONLY_DATE_EVIDENCE_NOT_ELIGIBILITY", "teams": results}, indent=2))
    # Diagnostic failures cannot confer freshness.
if __name__ == "__main__":
    main()
