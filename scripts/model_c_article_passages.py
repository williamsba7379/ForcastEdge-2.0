#!/usr/bin/env python3
"""Extract own-team quarterback status passages for human review only."""
import html.parser
import json
import pathlib
import re
from model_c_article_metadata import fetch_official

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
STATUS=("injury","injured","questionable","doubtful","practice","inactive","ruled out","named starter","will start")

class Reader(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=False
        self.parts=[]
        self.paragraphs=[]
    def handle_starttag(self,tag,attrs):
        if tag=="p":
            self.inside=True
            self.parts=[]
    def handle_data(self,data):
        if self.inside:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="p" and self.inside:
            self.paragraphs.append(re.sub(r"\s+"," "," ".join(self.parts)).strip())
            self.inside=False

def extract(page,names):
    parser=Reader()
    parser.feed(page)
    return [p[:350] for p in parser.paragraphs
            if any(n and n.lower() in p.lower() for n in names)
            and any(t in p.lower() for t in STATUS)][:3]

def collect(discovery,ranked,queue,fetch=fetch_official):
    teams={t["team"]:t for t in discovery["teams"]}
    games={(g["gameId"],g["team"]):g for g in queue["items"]}
    rows=[]
    for entry in ranked["items"]:
        game=games.get((entry["gameId"],entry["team"]),{})
        names=[game.get("recentPrimaryPasserCandidate"),game.get("depthChartCandidate")]
        names += [x.get("name") for x in game.get("reportedInjuryFlags",[])]
        for link in entry["rankedLinks"][:2]:
            row={"team":entry["team"],"gameId":entry["gameId"],"url":link["url"],
                 "status":"UNVERIFIED_PASSAGES_FOR_HUMAN_REVIEW",
                 "starterConfirmed":False,"passages":[]}
            try:
                base=teams[entry["team"]]["officialNewsIndex"]
                row["passages"]=extract(fetch(link["url"],base),names)
                row["fetchStatus"]="OK"
            except Exception as exc:
                row["fetchStatus"]="ERROR"
                row["error"]=str(exc)[:150]
            rows.append(row)
    return {"status":"PASSAGES_ONLY_NOT_STARTER_CONFIRMATION",
            "automaticConfirmations":0,"items":rows}

if __name__=="__main__":
    discovery=json.loads((DATA/"model-c-official-qb-discovery.json").read_text())
    ranked=json.loads((DATA/"model-c-qb-ranked-news.json").read_text())
    queue=json.loads((DATA/"model-c-qb-review-queue.json").read_text())
    output=collect(discovery,ranked,queue)
    (DATA/"model-c-qb-article-passages.json").write_text(json.dumps(output,indent=2)+"\n")
    print("Review-only passages:",sum(len(x["passages"]) for x in output["items"]))
