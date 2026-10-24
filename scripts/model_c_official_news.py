#!/usr/bin/env python3
"""Conservative official-team news link discovery; human review only.

Pilot uses explicitly reviewed official team domains. A discovered link is
NOT evidence that a quarterback will start. Never writes starter declarations.
"""
import datetime as dt
import html.parser
import json
import pathlib
import re
import urllib.parse
import urllib.request

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
OFFICIAL_TEAM_NEWS={
    "Baltimore Ravens":"https://www.baltimoreravens.com/news/",
    "Philadelphia Eagles":"https://www.philadelphiaeagles.com/news/",
    "Buffalo Bills":"https://www.buffalobills.com/news/",
    "Carolina Panthers":"https://www.panthers.com/news/",
    "Green Bay Packers":"https://www.packers.com/news/",
    "Kansas City Chiefs":"https://www.chiefs.com/news/",
    "Seattle Seahawks":"https://www.seahawks.com/news/",
    "Washington Commanders":"https://www.commanders.com/news/",
}
TERMS=("quarterback","qb ","starter","starting","injury","inactive","lamar","hurts","mckee")

class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.href=None
        self.parts=[]
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href")
            self.parts=[]
    def handle_data(self,data):
        if self.href is not None:
            self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            self.links.append((self.href," ".join(self.parts).strip()))
            self.href=None

def extract_candidates(page,base,limit=20):
    parsed=Links()
    parsed.feed(page)
    host=urllib.parse.urlparse(base).hostname
    seen=set()
    found=[]
    for href,label in parsed.links:
        url=urllib.parse.urljoin(base,href).split("#")[0]
        p=urllib.parse.urlparse(url)
        if p.scheme!="https" or p.hostname!=host or "/news/" not in p.path:
            continue
        if url in seen or not any(term in (label+" "+p.path.replace("-"," ")).lower() for term in TERMS):
            continue
        seen.add(url)
        found.append({"url":url,"headline":re.sub(r"\s+"," ",label)[:220],"status":"UNVERIFIED_LINK_FOR_HUMAN_REVIEW"})
        if len(found)>=limit:
            break
    return found

def collect(fetch=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-Research/1.0"})
            with urllib.request.urlopen(req,timeout=12) as response:
                if urllib.parse.urlparse(response.url).hostname!=urllib.parse.urlparse(url).hostname:
                    raise ValueError("Unexpected host redirect")
                return response.read(1500000).decode("utf-8","replace")
    results=[]
    for team,url in OFFICIAL_TEAM_NEWS.items():
        try:
            candidates=extract_candidates(fetch(url),url)
            results.append({"team":team,"officialNewsIndex":url,"fetchStatus":"OK","candidates":candidates})
        except Exception as exc:
            results.append({"team":team,"officialNewsIndex":url,"fetchStatus":"ERROR",
                            "error":str(exc)[:180],"candidates":[]})
    return {"status":"DISCOVERY_ONLY_NOT_STARTER_CONFIRMATION",
            "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "automaticConfirmations":0,"teams":results}

def main():
    result=collect()
    (DATA/"model-c-official-qb-discovery.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Official news discovery:",sum(len(t["candidates"]) for t in result["teams"]),
          "links; confirmed starters: 0")

if __name__=="__main__":main()
