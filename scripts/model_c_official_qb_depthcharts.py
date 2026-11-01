#!/usr/bin/env python3
"""Read-only official team depth-chart QB1 evidence. Never confirms a game starter."""
import datetime as dt
import json
import re
import urllib.request
from html.parser import HTMLParser

SOURCES = {
    "SF": "https://www.49ers.com/team/depth-chart",
    "BAL": "https://www.baltimoreravens.com/team/depth-chart",
}
class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

def extract_first_string_qb(html):
    """Require a labeled first-string column and exactly one nonempty QB row."""
    parser = TableReader()
    parser.feed(html)
    candidates = []
    for table in parser.tables:
        headers = None
        for row in table:
            normalized = [x.strip().lower() for x in row]
            if normalized and normalized[0] in ("position", "pos") and "1st" in normalized:
                headers = normalized
                continue
            if headers is None or not normalized or normalized[0] != "qb":
                continue
            if len(row) != len(headers):
                raise ValueError("Ambiguous QB table columns")
            qb = row[headers.index("1st")].strip()
            if not qb or qb in ("-", "—") or not re.fullmatch(r"[A-Za-zÀ-ÿ.' -]{3,90}(?: Jr\\.| Sr\\.| II| III| IV)?", qb):
                raise ValueError("Missing or invalid first-string QB")
            candidates.append(qb)
    if len(candidates) != 1:
        raise ValueError("Require exactly one explicitly labeled first-string QB row")
    return candidates[0]

def inspect_source(team, url):
    if team not in SOURCES or url != SOURCES[team]:
        raise ValueError("Unapproved official source")
    request = urllib.request.Request(url, headers={"User-Agent": "ForecastEdge-QB-Validation/1.0"})
    with urllib.request.urlopen(request, timeout=18) as response:
        final_url = response.geturl()
        if final_url != url:
            raise ValueError("Unexpected redirect")
        html = response.read(2_000_001)
        if len(html) > 2_000_000:
            raise ValueError("Page too large")
    text = html.decode("utf-8", errors="strict")
    qb = extract_first_string_qb(text)
    updated = re.search(r"Updated as of\\s+(\\d{1,2}/\\d{1,2}/\\d{2,4})", text, re.I)
    source_date = updated.group(1) if updated else None
    return {"team": team, "qb1DepthChartCandidate": qb, "source": url,
            "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sourceUpdatedAt": source_date,
            "verification": "DEPTH_CHART_ONLY_NOT_CONFIRMED",
            "freshness": "DATED" if source_date else "UNKNOWN",
            "note": "First-string depth chart does not confirm next-game starter."}

def main():
    # Diagnostic only: no production files are read or written.
    results = {}
    for team, url in SOURCES.items():
        try:
            results[team] = inspect_source(team, url)
        except (OSError, ValueError, UnicodeError) as exc:
            results[team] = {"source": url, "status": "UNVERIFIED", "reason": type(exc).__name__}
    print(json.dumps({"status": "READ_ONLY_OFFICIAL_DEPTH_CHART_DIAGNOSTIC", "teams": results}, indent=2))
    if any("qb1DepthChartCandidate" not in value for value in results.values()):
        raise RuntimeError("Official source validation incomplete; no snapshot modified")

if __name__ == "__main__":
    main()
