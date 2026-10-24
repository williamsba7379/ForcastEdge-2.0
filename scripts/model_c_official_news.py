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
    "Arizona Cardinals":"https://www.azcardinals.com/news/",
    "Atlanta Falcons":"https://www.atlantafalcons.com/news/",
    "Cincinnati Bengals":"https://www.bengals.com/news/",
    "Cleveland Browns":"https://www.clevelandbrowns.com/news/",
    "Dallas Cowboys":"https://www.dallascowboys.com/news/",
    "Denver Broncos":"https://www.denverbroncos.com/news/",
    "Detroit Lions":"https://www.detroitlions.com/news/",
    "Houston Texans":"https://www.houstontexans.com/news/",
    "Chicago Bears":"https://www.chicagobears.com/news/",
    "Indianapolis Colts":"https://www.colts.com/news/",
    "Jacksonville Jaguars":"https://www.jaguars.com/news/",
    "Las Vegas Raiders":"https://www.raiders.com/news/",
    "Los Angeles Chargers":"https://www.chargers.com/news/",
    "Los Angeles Rams":"https://www.therams.com/news/",
    "Miami Dolphins":"https://www.miamidolphins.com/news/",
    "Minnesota Vikings":"https://www.vikings.com/news/",
    "New England Patriots":"https://www.patriots.com/news/",
    "New Orleans Saints":"https://www.neworleanssaints.com/news/",
    "New York Giants":"https://www.giants.com/news/",
    "New York Jets":"https://www.newyorkjets.com/news/",
    "Pittsburgh Steelers":"https://www.steelers.com/news/",
    "San Francisco 49ers":"https://www.49ers.com/news/",
    "Tampa Bay Buccaneers":"https://www.buccaneers.com/news/",
    "Tennessee Titans":"https://www.tennesseetitans.com/news/",
}
TERMS=("quarterback","qb ","starter","starting","injury","inactive","practice","questionable","doubtful","ruled out")

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

def extract_candidates(page,base,limit=30,quarterback_names=()):
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
        text=(label+" "+p.path.replace("-"," ")).lower()
        names=tuple(n.lower() for n in quarterback_names if n)
        relevant=any(term in text for term in TERMS) or any(n in text for n in names)
        if url in seen or not relevant:
            continue
        seen.add(url)
        found.append({"url":url,"headline":re.sub(r"\s+"," ",label)[:220],"status":"UNVERIFIED_LINK_FOR_HUMAN_REVIEW"})
        if len(found)>=limit:
            break
    return found

def collect(fetch=None,quarterbacks_by_team=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-Research/1.0"})
            with urllib.request.urlopen(req,timeout=12) as response:
                if urllib.parse.urlparse(response.url).hostname!=urllib.parse.urlparse(url).hostname:
                    raise ValueError("Unexpected host redirect")
                return response.read(1500000).decode("utf-8","replace")
    results=[]
    quarterbacks_by_team=quarterbacks_by_team or {}
    for team,url in OFFICIAL_TEAM_NEWS.items():
        try:
            candidates=extract_candidates(fetch(url),url,quarterback_names=quarterbacks_by_team.get(team,()))
            results.append({"team":team,"officialNewsIndex":url,"fetchStatus":"OK","candidates":candidates})
        except Exception as exc:
            results.append({"team":team,"officialNewsIndex":url,"fetchStatus":"ERROR",
                            "error":str(exc)[:180],"candidates":[]})
    return {"status":"DISCOVERY_ONLY_NOT_STARTER_CONFIRMATION",
            "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "automaticConfirmations":0,"teams":results}

def main():
    quarterbacks_by_team={}
    queue_file=DATA/"model-c-qb-review-queue.json"
    if queue_file.exists():
        queue=json.loads(queue_file.read_text())
        for item in queue.get("items",[]):
            names=quarterbacks_by_team.setdefault(item["team"],set())
            for key in ("recentPrimaryPasserCandidate","depthChartCandidate"):
                if item.get(key):names.add(item[key])
    result=collect(quarterbacks_by_team=quarterbacks_by_team)
    (DATA/"model-c-official-qb-discovery.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Official news discovery:",sum(len(t["candidates"]) for t in result["teams"]),
          "links; confirmed starters: 0")

if __name__=="__main__":main()
